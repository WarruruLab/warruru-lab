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


# ── 리뷰 반영 (2026-08-24) ─────────────────────────────────────────

def test_SPOOL_슬러그는_자른_뒤에_만든다():
    """데몬은 TITLE_MAX 로 자른 뒤 슬러그를 만든다. 어댑터가 안 자르면
    긴 주제에서 힌트의 슬러그와 흡수 후 저장된 슬러그가 영영 어긋난다.
    """
    from warruru_local import limits

    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    long_topic = "가" * (limits.TITLE_MAX + 50)
    result = _call(service, topic=long_topic)
    clamped, _ = limits.clamp_text(long_topic, limits.TITLE_MAX)
    assert result["topic_slug"] == topics.slugify(clamped.strip())


def test_예시_재호출에_record_id_가_들어_있다():
    """예시의 유일한 용도는 복사해서 다시 부르는 것이다. record_id 가 빠지면
    복사한 순간 새 id 가 만들어져 보강 대신 중복 기록이 생긴다.
    """
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service)
    assert f'record_id="{result["record_id"]}"' in result["example_call"]


def test_오프라인_보강이면_힌트의_한계를_알린다():
    """SPOOL 보강 응답의 missing_fields 는 이번 호출 인자만 본 값이다.
    DB 에 이미 있는 값을 다시 물으러 가지 않게 메시지로 알린다.
    """
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다."))
    result = _call(service, record_id="rec_이전것", outcome="채움")
    assert "이번 호출" in result["message"]
