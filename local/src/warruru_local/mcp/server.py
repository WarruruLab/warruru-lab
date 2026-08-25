"""MCP stdio 어댑터. 툴은 예외를 밖으로 던지지 않는다."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from warruru_local import config, limits, logging_setup, spool, topics
from warruru_local.clock import Clock, SystemClock, to_iso
from warruru_local.ids import new_id
from warruru_local.mcp.client import DaemonClient, Outcome

SERVER_NAME = "warruru-local"


def _clamped(value, limit: int):
    """어댑터가 데몬과 같은 모양으로 값을 다듬는다. 힌트 판단에만 쓴다."""
    if value is None:
        return None
    text = str(value)[:limit].strip()
    return text or None


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

    def record_learning(
        self,
        kind: str,
        topic: str,
        title: str,
        body: str,
        rationale: str | None = None,
        outcome: str | None = None,
        limitation: str | None = None,
        interview: str | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
        record_id: str | None = None,
    ) -> dict:
        # 보강 호출은 응답으로 받았던 record_id 를 그대로 넘긴다.
        # 새 id 를 만들면 빈칸이 채워지는 대신 거의 같은 기록이 하나 더 생긴다.
        resolved_id = record_id or new_id("rec")
        payload = {
            "record_id": resolved_id,
            "kind": kind,
            "topic": topic,
            "title": title,
            "body": body,
            "rationale": rationale,
            "outcome": outcome,
            "limitation": limitation,
            "interview": interview,
            "occurred_at": occurred_at or to_iso(self._clock.now()),
            **self._base(repo_path),
        }
        # 봉투 kind 는 툴 이름이 아니라 상수다. 오타 하나면 봉투 버전 매핑이
        # 빗나가 구버전 데몬 방어(파일째 건너뛰기)가 통째로 무력화된다.
        outcome_ = self._client.send(
            spool.KIND_LEARNING_RECORD, "/v1/records", payload
        )
        result = outcome_.body or {}

        if outcome_.body is not None:
            # 데몬이 저장까지 마쳤다. 힌트는 저장된 값 기준으로 이미 계산돼 있다.
            hints = {
                "topic_slug": result.get("topic_slug"),
                "missing_fields": result.get("missing_fields", []),
                "example_call": result.get("example_call", ""),
                "similar_slugs": result.get("similar_slugs", []),
                # 데몬은 저장된 행을 보고 판단했다.
                "missing_fields_scope": "stored",
            }
        else:
            # SPOOL(또는 거절). 정규화·결손 판정은 순수 함수라 여기서도 채운다 —
            # 그래서 topics 가 최상위에 있고, mcp/ 는 daemon/ 을 임포트하지 않는다.
            #
            # 자르고 → 다듬고 → 슬러그. 데몬도 **같은 함수**를 부른다.
            # 각자 같은 두 줄을 손으로 적으면 한쪽만 바뀌었을 때
            # 힌트의 슬러그와 흡수 후 저장된 슬러그가 조용히 어긋난다.
            normalized_topic, slug = topics.normalize_topic(topic, limits.TITLE_MAX)

            # 데몬이 저장할 모양 그대로 판단한다. 원본 인자로 판단하면 예시가
            # 다듬기 전 값을 되돌려 주고, 같은 호출의 힌트가 데몬 생사에 따라 달라진다.
            stored_shape = {
                "kind": (kind or "").strip().upper(),
                "topic": normalized_topic,
                "title": _clamped(title, limits.TITLE_MAX),
                "body": _clamped(body, limits.BODY_MAX),
                "rationale": _clamped(rationale, limits.TEXT_MAX),
                "outcome": _clamped(outcome, limits.TEXT_MAX),
                "limitation": _clamped(limitation, limits.TEXT_MAX),
                "interview": _clamped(interview, limits.TEXT_MAX),
            }
            missing = topics.missing_fields(stored_shape)
            hints = {
                "topic_slug": slug,
                "missing_fields": missing,
                "example_call": topics.example_call(
                    stored_shape, missing, record_id=resolved_id
                ),
                # DB 갈래는 못 보지만 권장 상수는 임포트 한 번이면 읽힌다.
                "similar_slugs": topics.similar_recommended(slug),
                # 보강 호출이면 이 목록은 **이번 호출 인자만** 본 값이다 —
                # DB 에 이미 채워 둔 필드도 비어 보인다. 산문이 아니라 값으로
                # 알려야 읽는 쪽이 프로그램적으로 분기할 수 있다.
                "missing_fields_scope": "call_args" if record_id else "stored",
            }

        common = _common(outcome_)
        if hints.get("missing_fields_scope") == "call_args":
            # 사람이 읽을 자리에도 한 줄 남긴다. 판단은 위의 값으로 한다.
            common["message"] += (
                " (보강 호출 — missing_fields 는 이번 호출 인자만 본 값입니다."
                " 이미 채워 둔 필드는 다시 묻지 않아도 됩니다.)"
            )
        return {
            "record_id": resolved_id,
            "work_id": result.get("work_id"),
            "work_origin": result.get("work_origin"),
            "attached_by": result.get("attached_by"),
            "git": result.get("git"),
            "duplicate": result.get("duplicate", False),
            "filled_fields": result.get("filled_fields", []),
            **hints,
            **common,
        }

    def get_topic_records(
        self, topic_slug: str, since: str | None = None
    ) -> dict:
        params = {"topic_slug": topic_slug}
        if since:
            params["since"] = since
        outcome = self._client.query("/v1/records", params)
        body = outcome.body or {}
        records = body.get("records", [])
        return {
            "topic_slug": topic_slug,
            "topic": body.get("topic"),
            "records": records,
            # 무엇이 비었는지 함께 준다. 다듬는 에이전트가 빈 '한계' 를
            # 지어내지 않고 **되묻게** 하는 것이 이 툴의 목적이다.
            # 계산은 화면과 같은 함수(topics.shortages)를 쓴다.
            "missing_summary": topics.shortages(records),
            **_common(outcome),
        }

    def save_draft(
        self,
        topic_slug: str,
        title: str,
        markdown: str,
        source_record_ids: list[str] | None = None,
    ) -> dict:
        payload = {
            "topic_slug": topic_slug,
            "title": title,
            "markdown": markdown,
            "source_record_ids": source_record_ids,
        }
        # 새 초안을 하나 더 만들지 않는다. POST /v1/drafts 가 upsert 다 —
        # 조립기와 이 툴이 같은 행을 덮어쓴다.
        outcome = self._client.send("save_draft", "/v1/drafts", payload)
        body = outcome.body or {}
        return {
            "draft_id": body.get("draft_id"),
            "topic_slug": topic_slug,
            "status": body.get("status"),
            "file_path": body.get("file_path"),
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
            #
            # 다만 이건 **호출자가 work_id 를 준 경우만** 막는다. 생략하면
            # 여기도 None 이라 흡수 시점의 활성 작업이 마감된다 — K1 은 여전히 열려 있다.
            # "auto" 는 경로용 센티널이라 본문에 넣지 않는다. 라우트는 그것을
            # None 으로 정규화하는데 흡수 경로는 그러지 않아, 넣으면 없는 작업을 찾는다.
            "work_id": None if work_id == "auto" else work_id,
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


def _never_raises(prefix: str):
    """툴은 예외를 밖으로 던지지 않는다 — 이 관례를 복사-붙여넣기가 아니라
    한 곳에서 강제한다. 다음 툴을 붙이는 사람이 try/except 를 빼먹으면
    그 툴만 날 예외가 MCP 클라이언트로 새고, 기록 실패가 개발을 멈춘다.
    """
    import functools

    def decorate(fn):
        @functools.wraps(fn)
        def guarded(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as error:
                return {
                    "ok": False,
                    "storage": "NONE",
                    "message": f"{prefix}: {error}",
                }

        return guarded

    return decorate


def build_server(service: ToolService | None = None) -> FastMCP:
    resolved = service or _build_service()
    server = FastMCP(SERVER_NAME)

    @server.tool()
    @_never_raises("기록 실패")
    def start_work(
        title: str, goal: str | None = None, repo_path: str | None = None
    ) -> dict:
        """작업을 시작한다. 무엇을 하려는지 title 에 한 줄로 적는다."""
        return resolved.start_work(title=title, goal=goal, repo_path=repo_path)

    @server.tool()
    @_never_raises("기록 실패")
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
        return resolved.record_checkpoint(
            type=type, title=title, body=body, work_id=work_id, files=files,
            error_excerpt=error_excerpt, tags=tags, occurred_at=occurred_at,
            repo_path=repo_path,
        )

    @server.tool()
    @_never_raises("기록 실패")
    def record_learning(
        kind: str,
        topic: str,
        title: str,
        body: str,
        rationale: str | None = None,
        outcome: str | None = None,
        limitation: str | None = None,
        interview: str | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
        record_id: str | None = None,
    ) -> dict:
        """무언가를 배우거나 고치거나 고른 순간을 남긴다.

        kind: EXPERIMENT TROUBLESHOOTING TECH_CHOICE CONCEPT
        필수는 kind · topic · title · body 넷뿐이다. 나머지가 비어도
        거절하지 않는다 — 대신 응답이 무엇이 비었는지 알려준다.
        모르는 것을 지어내지 말고 비워 둔 채 부른 뒤, 사용자에게 되물어
        답을 얻으면 응답의 record_id 를 그대로 넘겨 같은 툴을 다시 불러 채운다.
        topic 은 원문 그대로 적는다. 정규화는 시스템이 한다.
        """
        return resolved.record_learning(
            kind=kind, topic=topic, title=title, body=body,
            rationale=rationale, outcome=outcome, limitation=limitation,
            interview=interview, occurred_at=occurred_at,
            repo_path=repo_path, record_id=record_id,
        )

    @server.tool()
    @_never_raises("조회 실패")
    def get_topic_records(topic_slug: str, since: str | None = None) -> dict:
        """한 주제의 기록을 시간순으로 읽는다. 초안을 다듬기 전에 재료를 확인한다.

        since 는 로컬 날짜(YYYY-MM-DD). 생략하면 그 주제의 전체 기록.
        응답의 missing_summary 가 비어 있는 필드를 알려준다 —
        **그 자리를 지어내지 말고 사용자에게 되물어라.**
        """
        return resolved.get_topic_records(topic_slug=topic_slug, since=since)

    @server.tool()
    @_never_raises("저장 실패")
    def save_draft(
        topic_slug: str,
        title: str,
        markdown: str,
        source_record_ids: list[str] | None = None,
    ) -> dict:
        """다듬은 초안으로 덮어쓴다. 그 주제의 미발행 초안이 대상이다.

        새 글을 하나 더 만들지 않는다. 없으면 그때 만든다.
        """
        return resolved.save_draft(
            topic_slug=topic_slug, title=title, markdown=markdown,
            source_record_ids=source_record_ids,
        )

    @server.tool()
    @_never_raises("기록 실패")
    def finish_work(
        work_id: str | None = None,
        result: str | None = None,
        limitations: str | None = None,
        next_steps: str | None = None,
    ) -> dict:
        """작업을 마감한다. 결과와 남은 한계, 다음 작업을 적는다."""
        return resolved.finish_work(
            work_id=work_id, result=result, limitations=limitations,
            next_steps=next_steps,
        )

    @server.tool()
    @_never_raises("조회 실패")
    def get_today_context(
        date: str | None = None, tool: str | None = None, limit: int = 10
    ) -> dict:
        """이 머신에서 오늘(또는 지정한 날짜) 기록한 작업 요약을 읽는다."""
        return resolved.get_today_context(date=date, tool=tool, limit=limit)

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
