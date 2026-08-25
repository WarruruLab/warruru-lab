"""다듬기 툴 둘 — `get_topic_records` 로 재료를 읽고 `save_draft` 로 덮어쓴다.

다듬기 중 에이전트가 빈 '한계' 를 **지어내지 않고 되묻는 것**이 이 경로의 핵심이다.
그래서 `get_topic_records` 는 무엇이 비었는지를 함께 돌려준다.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import topics
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app
from warruru_local.mcp.client import Outcome
from warruru_local.mcp.server import ToolService

START = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.sent = []
        self.queried = []
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


# ── get_topic_records ──────────────────────────────────────────────

def test_주제_기록을_조회한다():
    body = {"topic_slug": "connection-pool", "topic": "connection pool",
            "records": [], "missing_summary": []}
    service, client = _service(Outcome(body, "DAEMON", "조회했습니다."))
    result = service.get_topic_records(topic_slug="connection-pool")
    assert result["ok"] is True
    assert client.queried[0][0] == "/v1/records"
    assert client.queried[0][1]["topic_slug"] == "connection-pool"


def test_데몬이_꺼져있으면_조회_툴은_NONE_이다():
    """조회는 폴백할 대상이 없다. 빈손으로 오되 그 사실이 응답에 보인다."""
    service, _ = _service(Outcome(None, "NONE", "데몬에 연결하지 못했습니다"))
    result = service.get_topic_records(topic_slug="connection-pool")
    assert result["storage"] == "NONE"
    assert result["records"] == []


def test_since_를_넘기면_그대로_전달한다():
    service, client = _service(Outcome({"records": []}, "DAEMON", "ok"))
    service.get_topic_records(topic_slug="connection-pool", since="2026-08-20")
    assert client.queried[0][1]["since"] == "2026-08-20"


# ── save_draft ─────────────────────────────────────────────────────

def test_save_draft_는_drafts_라우트를_탄다():
    """새 초안을 하나 더 만들지 않는다. POST /v1/drafts 가 upsert 다."""
    service, client = _service(
        Outcome({"draft_id": "drf_A", "status": "DRAFT"}, "DAEMON", "저장했습니다.")
    )
    result = service.save_draft(
        topic_slug="connection-pool", title="제목", markdown="# 본문\n"
    )
    assert result["ok"] is True
    assert client.sent[0][1] == "/v1/drafts"
    assert client.sent[0][2]["markdown"] == "# 본문\n"


def test_save_draft_는_예외를_밖으로_던지지_않는다():
    class Boom:
        _client_instance_id = "cli_X"

        def send(self, *args, **kwargs):
            raise RuntimeError("터졌다")

    import json

    import anyio

    from warruru_local.mcp.server import build_server

    server = build_server(ToolService(Boom(), "codex", FixedClock(START)))

    async def call():
        return await server.call_tool("save_draft", {
            "topic_slug": "x", "title": "t", "markdown": "m",
        })

    content = anyio.run(call)
    assert json.loads(content[0].text)["ok"] is False


def test_툴이_일곱_개가_된다():
    import anyio

    from warruru_local.mcp.server import build_server

    names = {tool.name for tool in anyio.run(build_server().list_tools)}
    assert names == {
        "start_work", "record_checkpoint", "finish_work", "get_today_context",
        "record_learning", "get_topic_records", "save_draft",
    }


# ── 화면과 같은 값인가 ─────────────────────────────────────────────

def test_missing_summary_가_화면의_부족한_필드와_같다(home, monkeypatch):
    """같은 사실을 두 곳에서 따로 계산하면 두 문구가 갈라진다."""
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        for i in (1, 2):
            made.post("/v1/records", json={
                "record_id": f"rec_{i}", "client_instance_id": "cli_X",
                "tool": "codex", "kind": "EXPERIMENT",
                "topic": "connection pool", "title": f"제목 {i}",
                "body": "본문", **({"outcome": "결과 있음"} if i == 1 else {}),
            })
        api = made.get("/v1/records",
                       params={"topic_slug": "connection-pool"}).json()
        view = made.app.state.ctx
        from warruru_local.daemon import topicview

        screen = topicview.build_detail(view, "connection-pool")["shortages"]

    assert screen == topics.shortages(api["records"])
