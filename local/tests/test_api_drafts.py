"""`POST /v1/drafts` 와 [초안 만들기] 폼 — 주제가 파일이 된다."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 8, 24, 9, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def client(home, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _record(client, record_id, **extra):
    body = {
        "record_id": record_id, "client_instance_id": CLIENT, "tool": "codex",
        "kind": "EXPERIMENT", "topic": "connection pool",
        "title": "풀 크기 10→30", "body": "p95 320ms→90ms",
    }
    body.update(extra)
    return client.post("/v1/records", json=body)


def test_초안을_만들면_파일과_행이_함께_생긴다(client, home):
    _record(client, "rec_A")
    payload = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()

    assert payload["draft_id"].startswith("drf_")
    assert payload["status"] == "DRAFT"

    path = home / "drafts" / "2026" / "08" / "2026-08-24-connection-pool.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "## 문제" in text and "## 한계" in text
    assert "rec_A" in text


def test_초안은_저장소_바깥에_쓰인다(client, home):
    _record(client, "rec_A")
    payload = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    assert str(home) in payload["file_path"]


def test_같은_주제로_다시_만들면_행이_늘지_않는다(client):
    """조립기와 save_draft 가 결국 여기로 모인다. upsert 다."""
    _record(client, "rec_A")
    first = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    _record(client, "rec_B", title="두 번째")
    second = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    assert first["draft_id"] == second["draft_id"]


def test_다시_만들면_새_기록이_반영된다(client, home):
    _record(client, "rec_A")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})
    _record(client, "rec_B", title="나중에 안 것")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})

    path = home / "drafts" / "2026" / "08" / "2026-08-24-connection-pool.md"
    assert "나중에 안 것" in path.read_text(encoding="utf-8")


def test_기록이_없는_주제로는_초안을_못_만든다(client):
    """재료 0건으로 빈 파일을 조용히 쓰면 나중에 왜 비었는지 아무도 모른다."""
    assert client.post("/v1/drafts", json={"topic_slug": "없는-주제"}).status_code == 404


def test_토큰이_없으면_401(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.post("/v1/drafts", json={"topic_slug": "connection-pool"})
        assert response.status_code == 401


# ── 웹 폼 ──────────────────────────────────────────────────────────

def test_초안_만들기는_폼_토큰이_없으면_401(client):
    _record(client, "rec_A")
    response = client.post("/web/topics/connection-pool/draft", data={})
    assert response.status_code == 401


def test_초안을_만들면_초안_화면으로_302(client):
    _record(client, "rec_A")
    settings = load_settings_from(client)
    response = client.post(
        "/web/topics/connection-pool/draft",
        data={"_token": settings.token}, follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"].startswith("/drafts/drf_")


def load_settings_from(client):
    return client.app.state.ctx.settings


def test_front_matter_의_기록_순서가_본문과_같다(client, home):
    """둘이 다르면 파일을 읽는 사람이 맞춰 보다 헷갈린다."""
    _record(client, "rec_먼저", occurred_at="2026-08-24T07:00:00.000Z")
    _record(client, "rec_나중", occurred_at="2026-08-24T09:00:00.000Z")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})

    text = (home / "drafts" / "2026" / "08" / "2026-08-24-connection-pool.md").read_text(
        encoding="utf-8"
    )
    front = text.split("---")[1]
    assert front.index("rec_먼저") < front.index("rec_나중")
    footer = text.split("조립에 쓴 기록")[1]
    assert footer.index("rec_먼저") < footer.index("rec_나중")
