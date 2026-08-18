"""데몬 조립. SQLite 의 유일한 writer 다."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from warruru_local import __version__, config, logging_setup, paths
from warruru_local.clock import Clock, SystemClock, to_iso
from warruru_local.daemon import auth
from warruru_local.gitinfo import GitCollector
from warruru_local.session import SessionService
from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository


@dataclass
class AppContext:
    settings: config.Settings
    conn: object
    repo: Repository
    sessions: SessionService
    git: GitCollector
    clock: Clock
    machine_id: str
    started_at: str
    schema_version: int
    logger: logging.Logger


def _build_context(settings: config.Settings, clock: Clock) -> AppContext:
    paths.ensure_layout(settings.home)
    logger = logging_setup.setup_logging(settings.home, "daemon", settings.log_level)

    conn = db.connect(paths.db_path(settings.home))
    now = to_iso(clock.now())
    # 실제로 어디까지 올라갔는지 받아 둔다. `migrate` 는 이미 최신이면 아무 일도
    # 하지 않으므로, 구버전 바이너리가 더 높은 버전의 DB 를 열면 조용히 넘어간다.
    # 그 상태를 health 가 상수로 보고하면 아무도 눈치채지 못한다.
    schema_version = migrations.migrate(conn, now)
    if schema_version != migrations.CURRENT_VERSION:
        logger.warning(
            "DB 스키마 버전이 %d 인데 이 데몬은 %d 를 기대한다",
            schema_version, migrations.CURRENT_VERSION,
        )

    repo = Repository(conn)
    machine = config.load_or_create_machine(settings.home)
    repo.ensure_machine(
        machine["machine_id"], machine["hostname"], machine["os"], machine["created_at"]
    )

    git = GitCollector(
        timeout_seconds=settings.git_timeout_seconds,
        cache_ttl_seconds=settings.git_cache_ttl_seconds,
        dirty_file_cap=settings.git_dirty_file_cap,
    )
    sessions = SessionService(repo, clock, settings)

    return AppContext(
        settings=settings,
        conn=conn,
        repo=repo,
        sessions=sessions,
        git=git,
        clock=clock,
        machine_id=machine["machine_id"],
        started_at=now,
        schema_version=schema_version,
        logger=logger,
    )


def create_app(
    settings: config.Settings,
    clock: Clock | None = None,
    start_background: bool = True,
) -> FastAPI:
    resolved_clock = clock or SystemClock()

    @contextlib.asynccontextmanager
    async def lifespan(instance: FastAPI):
        instance.state.ctx = _build_context(settings, resolved_clock)
        # 데몬이 몇 시간 꺼져 있었다면 그 사이 방치된 세션이 있다.
        instance.state.ctx.sessions.sweep_idle()

        from warruru_local.daemon import absorb

        absorb.absorb_all(instance.state.ctx)
        stop = None
        if start_background:
            from warruru_local.daemon.sweeper import start_sweeper

            stop = start_sweeper(instance.state.ctx)
        yield
        if stop is not None:
            await stop()
        instance.state.ctx.conn.close()

    app = FastAPI(title="Warruru Local Daemon", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def _auth_gate(request: Request, call_next):
        """`/v1/health` 를 뺀 모든 `/v1` 경로를 지킨다.

        라우트가 아직 없어도(예: Task 12 이전의 `/v1/works`) 미인증 요청은
        401 이어야 한다 — 존재 여부로 엔드포인트를 흘리지 않는다.
        """
        path = request.url.path
        if path.startswith("/v1/") and path != "/v1/health":
            expected = request.app.state.ctx.settings.token
            provided = request.headers.get(auth.HEADER)
            if not provided or provided != expected:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "INVALID_TOKEN",
                            "message": "토큰이 없거나 올바르지 않습니다",
                            "detail": {},
                        }
                    },
                )
        return await call_next(request)

    @app.exception_handler(FastAPIHTTPException)
    async def _http_error(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
        payload = exc.detail
        if not isinstance(payload, dict):
            payload = {"code": "INVALID_REQUEST", "message": str(payload)}
        payload.setdefault("detail", {})
        return JSONResponse(status_code=exc.status_code, content={"error": payload})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """pydantic 검증 실패도 표준 봉투를 따른다 — FastAPI 기본 422 를 쓰지 않는다."""
        fields = sorted(
            {".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()}
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "요청 값이 올바르지 않습니다",
                    "detail": {"fields": fields},
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.ctx.logger.exception("처리하지 못한 오류")
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "STORAGE_ERROR", "message": str(exc), "detail": {}}
            },
        )

    @app.get("/v1/health")
    async def health(request: Request) -> dict:
        ctx = request.app.state.ctx
        return {
            "status": "ok",
            "version": __version__,
            # 상수가 아니라 이 DB 가 실제로 올라간 버전이다.
            # 상수를 돌려주면 마이그레이션이 돌았는지 확인할 방법이 사라진다.
            "schema_version": ctx.schema_version,
            "machine_id": ctx.machine_id,
            "started_at": ctx.started_at,
        }

    from warruru_local.daemon import routes_api, routes_web

    app.include_router(routes_api.router)
    app.include_router(routes_web.router)
    return app


def main() -> None:
    import uvicorn

    from warruru_local.daemon.lock import SingleInstanceLock

    settings = config.load_settings()
    guard = SingleInstanceLock(paths.run_dir(settings.home) / "daemon.lock")
    if not guard.acquire():
        return  # 이미 다른 데몬이 돈다. 조용히 끝낸다.
    try:
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )
    finally:
        guard.release()


if __name__ == "__main__":
    main()
