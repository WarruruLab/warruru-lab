from datetime import datetime, timezone

import pytest

from warruru_local.clock import FixedClock
from warruru_local.mcp.client import Outcome
from warruru_local.mcp.server import ToolService

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.sent = []
        self.queried = []
        # 실제 DaemonClient 계약과 맞춘다: client_instance_id 를 갖는다.
        self._client_instance_id = "cli_FAKE00000000000000000000"

    def send(self, kind, path, payload):
        self.sent.append((kind, path, payload))
        return self.outcomes.pop(0) if self.outcomes else Outcome({}, "DAEMON", "ok")

    def query(self, path, params):
        self.queried.append((path, params))
        return self.outcomes.pop(0) if self.outcomes else Outcome({}, "DAEMON", "ok")


def _service(*outcomes):
    client = FakeClient(*outcomes)
    return ToolService(client, "codex", FixedClock(START)), client


def test_작업_시작은_식별자를_먼저_만든다():
    service, client = _service(
        Outcome({"work_id": "무시됨", "git": None}, "DAEMON", "ok")
    )
    result = service.start_work(title="제목", goal="목표")
    sent_payload = client.sent[0][2]
    assert result["work_id"] == sent_payload["work_id"]
    assert result["work_id"].startswith("wrk_")


def test_작업_시작_응답에_공통_필드가_있다():
    service, _ = _service()
    result = service.start_work(title="제목")
    assert result["ok"] is True
    assert result["storage"] == "DAEMON"
    assert isinstance(result["message"], str)


def test_데몬이_없으면_spool_이라고_알린다():
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다"))
    result = service.start_work(title="제목")
    assert result["ok"] is True
    assert result["storage"] == "SPOOL"
    assert result["work_id"].startswith("wrk_")


def test_잘못된_요청은_ok_가_False_다():
    service, _ = _service(Outcome(None, "DAEMON", "type 은 필수입니다"))
    result = service.record_checkpoint(type="NOTE", title="제목")
    assert result["ok"] is False
    assert "필수" in result["message"]


def test_체크포인트도_식별자를_먼저_만든다():
    service, client = _service()
    result = service.record_checkpoint(type="PROBLEM", title="제목")
    assert result["checkpoint_id"].startswith("ckp_")
    assert client.sent[0][2]["checkpoint_id"] == result["checkpoint_id"]


def test_체크포인트는_귀속_경로를_그대로_전달한다():
    service, _ = _service(
        Outcome(
            {"checkpoint_id": "ckp_A", "work_id": "wrk_A", "work_origin": "INFERRED",
             "attached_by": "CLIENT_INSTANCE", "git": None},
            "DAEMON", "ok",
        )
    )
    result = service.record_checkpoint(type="PROBLEM", title="제목")
    assert result["attached_by"] == "CLIENT_INSTANCE"
    assert result["work_origin"] == "INFERRED"


def test_발생_시각을_주지_않으면_지금으로_채운다():
    service, client = _service()
    service.record_checkpoint(type="NOTE", title="제목")
    assert client.sent[0][2]["occurred_at"] == "2026-07-22T08:00:00.000Z"


def test_마감은_auto_경로를_쓴다():
    service, client = _service()
    service.finish_work()
    assert client.sent[0][1] == "/v1/works/auto/finish"


def test_식별자를_주면_그_경로로_마감한다():
    service, client = _service()
    service.finish_work(work_id="wrk_A")
    assert client.sent[0][1] == "/v1/works/wrk_A/finish"


def test_마감_봉투_본문에도_work_id_가_들어간다():
    """경로에만 두면 오프라인 마감이 흡수될 때 대상 작업을 잃는다.

    봉투는 본문만 담으므로(IF-6) 흡수 시 `payload.get("work_id")` 가 None 이 되고
    `find_active_by_client` 로 떨어진다. 그 사이 새 작업을 시작했다면
    **그 작업이 남의 결과 텍스트를 달고 마감되고** 원래 작업은 열린 채 남는다
    (OUTSTANDING K1). 404 를 spool 로 돌리면서 이 경로의 트래픽이 늘었다.
    """
    service, client = _service()
    service.finish_work(work_id="wrk_A", result="끝")
    assert client.sent[0][2]["work_id"] == "wrk_A"


def test_마감할_작업이_없어도_ok_다():
    service, _ = _service(
        Outcome(
            {"work_id": None, "reason": "NO_ACTIVE_WORK", "ended_at": None,
             "checkpoint_count": 0, "duration_seconds": 0, "git": None},
            "DAEMON", "ok",
        )
    )
    result = service.finish_work()
    assert result["ok"] is True
    assert result["work_id"] is None
    assert "없" in result["message"]


def test_맥락_조회는_요약과_목록을_준다():
    service, _ = _service(
        Outcome(
            {"date": "2026-07-22", "summary_markdown": "# 요약", "works": []},
            "DAEMON", "ok",
        )
    )
    result = service.get_today_context()
    assert result["summary_markdown"] == "# 요약"
    assert result["works"] == []
    assert result["storage"] == "DAEMON"


def test_맥락_조회가_실패하면_storage_는_NONE_이다():
    service, _ = _service(Outcome(None, "NONE", "연결 실패"))
    result = service.get_today_context()
    assert result["ok"] is False
    assert result["storage"] == "NONE"
    assert result["works"] == []


def test_전송하는_payload_에_client_instance_id_가_담긴다():
    service, client = _service()
    service.start_work(title="제목")
    service.record_checkpoint(type="NOTE", title="제목")
    service.finish_work()
    assert client.sent, "전송된 payload 가 있어야 한다"
    for _, _, payload in client.sent:
        assert payload["client_instance_id"] == client._client_instance_id


def test_서버는_툴_일곱_개를_등록한다():
    import anyio

    from warruru_local.mcp.server import build_server

    server = build_server()
    names = {tool.name for tool in anyio.run(server.list_tools)}
    # 기존 4개 + 학습 기록 3개(기록 1 · 다듬기 2). MVP 범위에서는 여기까지다.
    assert names == {
        "start_work", "record_checkpoint", "finish_work", "get_today_context",
        "record_learning", "get_topic_records", "save_draft",
    }
