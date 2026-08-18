"""MCP stdio 어댑터. 툴은 예외를 밖으로 던지지 않는다."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from warruru_local import config, logging_setup
from warruru_local.clock import Clock, SystemClock, to_iso
from warruru_local.ids import new_id
from warruru_local.mcp.client import DaemonClient, Outcome

SERVER_NAME = "warruru-local"


def _common(outcome: Outcome) -> dict:
    return {
        "ok": outcome.storage != "NONE" and not (
            outcome.storage == "DAEMON" and outcome.body is None
        ),
        "storage": outcome.storage,
        "message": outcome.message,
    }


class ToolService:
    """툴 4개의 순수 구현. FastMCP 와 분리해 테스트할 수 있게 둔다."""

    def __init__(self, client, tool: str, clock: Clock) -> None:
        self._client = client
        self._tool = tool
        self._clock = clock

    def _base(self, repo_path: str | None = None) -> dict:
        return {
            # 대화 귀속의 핵심 값이다. 없으면 조용히 None 을 보내는 대신
            # 배선이 잘못됐다는 신호로 크게 실패해야 한다.
            "client_instance_id": self._client._client_instance_id,  # noqa: SLF001
            "tool": self._tool,
            "cwd": os.getcwd(),
            "repo_path": repo_path,
        }

    def start_work(
        self, title: str, goal: str | None = None, repo_path: str | None = None
    ) -> dict:
        work_id = new_id("wrk")
        now = to_iso(self._clock.now())
        payload = {
            "work_id": work_id,
            "title": title,
            "goal": goal,
            "started_at": now,
            **self._base(repo_path),
        }
        outcome = self._client.send("start_work", "/v1/works", payload)
        body = outcome.body or {}
        return {
            "work_id": work_id,
            "started_at": body.get("started_at", now),
            "git": body.get("git"),
            **_common(outcome),
        }

    def record_checkpoint(
        self,
        type: str,
        title: str,
        body: str | None = None,
        work_id: str | None = None,
        files: list[str] | None = None,
        error_excerpt: str | None = None,
        tags: list[str] | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
    ) -> dict:
        checkpoint_id = new_id("ckp")
        payload = {
            "checkpoint_id": checkpoint_id,
            "work_id": work_id,
            "type": type,
            "title": title,
            "body": body,
            "files": files,
            "error_excerpt": error_excerpt,
            "tags": tags,
            "occurred_at": occurred_at or to_iso(self._clock.now()),
            **self._base(repo_path),
        }
        outcome = self._client.send("record_checkpoint", "/v1/checkpoints", payload)
        result = outcome.body or {}
        return {
            "checkpoint_id": checkpoint_id,
            "work_id": result.get("work_id", work_id),
            "work_origin": result.get("work_origin"),
            "attached_by": result.get("attached_by"),
            "git": result.get("git"),
            **_common(outcome),
        }

    def finish_work(
        self,
        work_id: str | None = None,
        result: str | None = None,
        limitations: str | None = None,
        next_steps: str | None = None,
    ) -> dict:
        payload = {
            # work_id 는 경로에도 들어가지만 봉투는 본문만 담는다(IF-6).
            # 여기 넣지 않으면 오프라인 마감이 흡수될 때 대상 작업을 잃고
            # `find_active_by_client` 로 떨어져 **엉뚱한 작업이 마감된다**
            # (OUTSTANDING K1). 그 사이 새 작업을 시작했으면 그 작업이 남의
            # 결과 텍스트를 달고 닫히고, 원래 작업은 영영 열린 채로 남는다.
            "work_id": work_id,
            "result": result,
            "limitations": limitations,
            "next_steps": next_steps,
            "ended_at": to_iso(self._clock.now()),
            **self._base(),
        }
        path = f"/v1/works/{work_id or 'auto'}/finish"
        outcome = self._client.send("finish_work", path, payload)
        body = outcome.body or {}
        common = _common(outcome)
        if body.get("reason") == "NO_ACTIVE_WORK":
            common["message"] = "마감할 작업이 없었습니다."
        return {
            "work_id": body.get("work_id"),
            "ended_at": body.get("ended_at"),
            "checkpoint_count": body.get("checkpoint_count", 0),
            "duration_seconds": body.get("duration_seconds", 0),
            "git": body.get("git"),
            **common,
        }

    def get_today_context(
        self, date: str | None = None, tool: str | None = None, limit: int = 10
    ) -> dict:
        params = {"limit": limit}
        if date:
            params["date"] = date
        if tool:
            params["tool"] = tool
        outcome = self._client.query("/v1/context", params)
        body = outcome.body or {}
        return {
            "date": body.get("date", date),
            "summary_markdown": body.get("summary_markdown", ""),
            "works": body.get("works", []),
            **_common(outcome),
        }


def _detect_tool(settings: config.Settings) -> str:
    return settings.tool or "unknown"


def build_server(service: ToolService | None = None) -> FastMCP:
    resolved = service or _build_service()
    server = FastMCP(SERVER_NAME)

    @server.tool()
    def start_work(
        title: str, goal: str | None = None, repo_path: str | None = None
    ) -> dict:
        """작업을 시작한다. 무엇을 하려는지 title 에 한 줄로 적는다."""
        try:
            return resolved.start_work(title=title, goal=goal, repo_path=repo_path)
        except Exception as error:  # 툴은 예외를 밖으로 던지지 않는다
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def record_checkpoint(
        type: str,
        title: str,
        body: str | None = None,
        work_id: str | None = None,
        files: list[str] | None = None,
        error_excerpt: str | None = None,
        tags: list[str] | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
    ) -> dict:
        """작업 중 의미 있는 순간을 기록한다.

        type: PROBLEM ATTEMPT FAILED_ATTEMPT ERROR TEST_RESULT
              DECISION RESULT LIMITATION NOTE
        """
        try:
            return resolved.record_checkpoint(
                type=type, title=title, body=body, work_id=work_id, files=files,
                error_excerpt=error_excerpt, tags=tags, occurred_at=occurred_at,
                repo_path=repo_path,
            )
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def finish_work(
        work_id: str | None = None,
        result: str | None = None,
        limitations: str | None = None,
        next_steps: str | None = None,
    ) -> dict:
        """작업을 마감한다. 결과와 남은 한계, 다음 작업을 적는다."""
        try:
            return resolved.finish_work(
                work_id=work_id, result=result, limitations=limitations,
                next_steps=next_steps,
            )
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def get_today_context(
        date: str | None = None, tool: str | None = None, limit: int = 10
    ) -> dict:
        """이 머신에서 오늘(또는 지정한 날짜) 기록한 작업 요약을 읽는다."""
        try:
            return resolved.get_today_context(date=date, tool=tool, limit=limit)
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"조회 실패: {error}"}

    return server


def _build_service() -> ToolService:
    settings = config.load_settings()
    logger = logging_setup.setup_logging(settings.home, "mcp", settings.log_level)
    clock = SystemClock()
    client = DaemonClient(settings, new_id("cli"), logger, clock)
    return ToolService(client, _detect_tool(settings), clock)


def main() -> None:
    service = _build_service()
    build_server(service).run("stdio")
    # 표준 입력이 닫히면 대화가 끝난 것이다. 진행 중 세션을 마감하게 알린다.
    try:
        service._client.close()  # noqa: SLF001
    except Exception:
        logging.getLogger("warruru.mcp").exception("대화 종료를 알리지 못했다")
