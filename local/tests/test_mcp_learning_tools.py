"""`record_learning` MCP 툴 — 종단 경로가 처음 닫힌다.

툴 호출이 DB 행이 되고, 데몬이 꺼져 있어도 유실되지 않는다.
힌트 3종(missing_fields · example_call · similar_slugs)은 SPOOL 에서도 채워진다 —
정규화와 결손 판정이 입력만으로 답이 나오는 순수 함수이기 때문이다.
"""

from datetime import datetime, timezone

import pytest

from warruru_local import spool, topics
from warruru_local.clock import FixedClock
from warruru_local.mcp.client import Outcome
from warruru_local.mcp.server import ToolService

START = datetime(2026, 8, 18, 9, 0, 0, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.sent = []
        self._client_instance_id = "cli_FAKE00000000000000000000"

    def send(self, kind, path, payload):
        self.sent.append((kind, path, payload))
        return self.outcomes.pop(0) if self.outcomes else Outcome({}, "DAEMON", "ok")

    def query(self, path, params):
        return Outcome({}, "DAEMON", "ok")


def _service(*outcomes):
    client = FakeClient(*outcomes)
    return ToolService(client, "codex", FixedClock(START)), client


DAEMON_BODY = {
    "record_id": "rec_서버가정한값아님",
    "work_id": "wrk_A",
    "work_origin": "INFERRED",
    "attached_by": "NEW",
    "topic_slug": "connection-pool",
    "project": None,
    "missing_fields": ["rationale", "outcome", "limitation", "interview"],
    "example_call": "record_learning(...)",
    "similar_slugs": ["connection-pool"],
    "git": None,
    "duplicate": False,
    "filled_fields": [],
}


def _call(service, **extra):
    values = dict(kind="EXPERIMENT", topic="connection pool",
                  title="풀 크기 10→30", body="p95 320ms→90ms")
    values.update(extra)
    return service.record_learning(**values)


# ── 온라인 경로 ─────────────────────────────────────────────────────

def test_기록하면_record_id_가_온다():
    service, client = _service(Outcome(DAEMON_BODY, "DAEMON", "기록했습니다."))
    result = _call(service)
    assert result["ok"] is True
    assert result["record_id"].startswith("rec_")
    assert result["record_id"] == client.sent[0][2]["record_id"]


def test_봉투_kind_는_상수다():
    """툴 이름(record_learning)이 아니라 spool.KIND_LEARNING_RECORD 다.

    오타 하나면 봉투 버전 매핑이 빗나가 구버전 데몬 방어가 통째로 무력화된다.
    """
    service, client = _service(Outcome(DAEMON_BODY, "DAEMON", "ok"))
    _call(service)
    assert client.sent[0][0] == spool.KIND_LEARNING_RECORD
    assert client.sent[0][1] == "/v1/records"


def test_결손_필드_목록이_응답에_들어_있다():
    service, _ = _service(Outcome(DAEMON_BODY, "DAEMON", "ok"))
    assert "outcome" in _call(service)["missing_fields"]


def test_예시_재호출_문자열에_결손_필드가_들어_있다():
    service, _ = _service(Outcome(DAEMON_BODY, "DAEMON", "ok"))
    assert "record_learning(" in _call(service)["example_call"]


def test_유사_슬러그_힌트가_응답에_들어_있다():
    service, _ = _service(Outcome(DAEMON_BODY, "DAEMON", "ok"))
    assert _call(service)["similar_slugs"] == ["connection-pool"]


def test_보강_호출은_받은_record_id_를_그대로_쓴다():
    """매번 새 id 를 만들면 힌트를 따라도 채울 수 없고
    거의 같은 기록만 하나 더 생긴다(명세 §4.1.1).
    """
    service, client = _service(Outcome(DAEMON_BODY, "DAEMON", "ok"))
    _call(service, record_id="rec_이전에받은것", outcome="p95 가 90ms")
    assert client.sent[0][2]["record_id"] == "rec_이전에받은것"


# ── SPOOL 경로 ─────────────────────────────────────────────────────

def test_데몬이_꺼져있어도_기록이_spool에_남는다():
    service, client = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service)
    assert result["ok"] is True
    assert result["storage"] == "SPOOL"
    assert result["record_id"].startswith("rec_")


def test_SPOOL_이어도_topic_slug_와_결손_필드는_채워진다():
    """순수 함수라 어댑터가 혼자 계산할 수 있다. 그래서 topics 가 최상위에 있다."""
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service, topic="  Connection Pool  ")
    assert result["topic_slug"] == "connection-pool"
    assert "outcome" in result["missing_fields"]
    assert "record_learning(" in result["example_call"]


def test_SPOOL_이면_유사_슬러그는_권장_상수만_본다():
    """DB 는 못 보지만 상수는 임포트 한 번이면 읽힌다. 빈 목록이 아니어야 한다."""
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service, topic="jpa n plus")
    assert "jpa-n-plus-one" in result["similar_slugs"]


def test_SPOOL_에서_겹치는_후보가_없으면_빈_목록이지_None_이_아니다():
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    assert _call(service, topic="전혀 관련 없는 무엇")["similar_slugs"] == []


def test_SPOOL_이면_데몬만_아는_값은_None_이다():
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service)
    assert result["work_id"] is None
    assert result["git"] is None


# ── 공통 ───────────────────────────────────────────────────────────

def test_내부_오류가_예외로_새어나가지_않는다():
    class Boom:
        _client_instance_id = "cli_FAKE00000000000000000000"

        def send(self, *args, **kwargs):
            raise RuntimeError("터졌다")

    import json

    import anyio

    from warruru_local.mcp.server import build_server

    server = build_server(ToolService(Boom(), "codex", FixedClock(START)))
    # build_server 의 래퍼가 예외를 {ok: False} 로 바꾸는 것까지가 계약이다.

    async def call():
        return await server.call_tool("record_learning", {
            "kind": "EXPERIMENT", "topic": "t", "title": "t", "body": "b",
        })

    content = anyio.run(call)
    result = json.loads(content[0].text)
    assert result["ok"] is False
    assert "기록 실패" in result["message"]


def test_기존_툴_4개의_동작이_그대로다():
    """새 툴이 붙어도 기존 넷의 이름과 등록이 달라지면 안 된다."""
    import anyio

    from warruru_local.mcp.server import build_server

    server = build_server(ToolService(FakeClient(), "codex", FixedClock(START)))
    names = {tool.name for tool in anyio.run(server.list_tools)}
    assert {"start_work", "record_checkpoint", "finish_work",
            "get_today_context"} <= names
    assert "record_learning" in names
