"""`POST /v1/drafts` 와 [초안 만들기] 폼 — 주제가 파일이 된다."""

import pathlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import drafting
from warruru_local.daemon.app import create_app

START = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)
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

    path = home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md"
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

    path = home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md"
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

    text = (home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md").read_text(
        encoding="utf-8"
    )
    front = text.split("---")[1]
    assert front.index("rec_먼저") < front.index("rec_나중")
    footer = text.split("조립에 쓴 기록")[1]
    assert footer.index("rec_먼저") < footer.index("rec_나중")


# ── 다듬은 글로 덮어쓰기 ───────────────────────────────────────────

def test_마크다운을_주면_그것을_저장한다(client, home):
    """save_draft 의 목적 자체다. 조립기로 다시 만들어 버리면
    에이전트가 다듬은 문장이 통째로 사라진다.
    """
    _record(client, "rec_A")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})

    polished = "# 다듬은 제목\n\n## 문제\n\n사람이 읽을 만한 문장.\n"
    payload = client.post("/v1/drafts", json={
        "topic_slug": "connection-pool", "title": "다듬은 제목",
        "markdown": polished,
    }).json()

    assert payload["status"] == "DRAFT"
    text = (home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md").read_text(
        encoding="utf-8"
    )
    assert "사람이 읽을 만한 문장" in text
    assert "TODO: 여기서 무엇을 판단했는가?" not in text


def test_마크다운을_주면_같은_행을_덮어쓴다(client):
    _record(client, "rec_A")
    first = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    second = client.post("/v1/drafts", json={
        "topic_slug": "connection-pool", "markdown": "# 다듬음\n",
    }).json()
    assert first["draft_id"] == second["draft_id"]


def test_미발행_초안이_없으면_새로_만든다(client):
    """save_draft 가 조립기보다 먼저 불릴 수도 있다."""
    _record(client, "rec_A")
    payload = client.post("/v1/drafts", json={
        "topic_slug": "connection-pool", "markdown": "# 처음부터 다듬음\n",
    }).json()
    assert payload["draft_id"].startswith("drf_")


def test_마크다운_없이_부르면_조립기가_돈다(client, home):
    _record(client, "rec_A")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})
    text = (home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md").read_text(
        encoding="utf-8"
    )
    assert "## 문제" in text and "## 한계" in text


# ── 고른 기록으로 만드는 초안 ───────────────────────────────────────

def test_고른_기록만으로_초안을_만든다(client):
    """주제 전체가 아니라 사람이 체크한 것만 재료가 된다.

    나중에 LLM 을 붙일 때 넘길 값이 이 목록이다 — 조립기 자리에
    모델 호출이 들어가도 재료를 고르는 방식은 그대로다.
    """
    _record(client, "rec_A", title="첫째", body="첫째 본문")
    _record(client, "rec_B", title="둘째", body="둘째 본문")
    _record(client, "rec_C", title="셋째", body="셋째 본문")

    made = drafting.create_from_records(client.app.state.ctx, ["rec_A", "rec_C"])
    text = pathlib.Path(made["file_path"]).read_text(encoding="utf-8")
    assert "첫째 본문" in text
    assert "셋째 본문" in text
    assert "둘째 본문" not in text
    assert made["source_record_count"] == 2


def test_고른_순서가_아니라_시간순으로_쓴다(client):
    """읽는 순서가 곧 서사 순서다. 체크한 순서는 서사가 아니다."""
    _record(client, "rec_늦은", title="늦은", body="늦은 본문",
            occurred_at="2026-08-20T09:00:00.000Z")
    _record(client, "rec_이른", title="이른", body="이른 본문",
            occurred_at="2026-08-18T09:00:00.000Z")
    made = drafting.create_from_records(client.app.state.ctx, ["rec_늦은", "rec_이른"])
    text = pathlib.Path(made["file_path"]).read_text(encoding="utf-8")
    assert text.index("이른 본문") < text.index("늦은 본문")


def test_없는_기록은_건너뛴다(client):
    """체크한 뒤 다른 곳에서 지웠을 수 있다. 그것 때문에 실패하지 않는다."""
    _record(client, "rec_A", title="첫째", body="첫째 본문")
    made = drafting.create_from_records(client.app.state.ctx, ["rec_A", "rec_없는것"])
    assert made["source_record_count"] == 1


def test_하나도_안_고르면_거절한다(client):
    """빈 파일을 조용히 쓰면 나중에 왜 비었는지 아무도 모른다."""
    with pytest.raises(drafting.NoRecordsError):
        drafting.create_from_records(client.app.state.ctx, [])


def test_재료_목록이_고른_것과_같다(client):
    """front matter 의 source_record_ids 가 화면에서 체크한 것과 달라지면
    파일만 열었을 때 재료를 되짚을 수 없다.
    """
    _record(client, "rec_A", title="첫째", body="본문")
    _record(client, "rec_B", title="둘째", body="본문")
    made = drafting.create_from_records(client.app.state.ctx, ["rec_B"])
    text = pathlib.Path(made["file_path"]).read_text(encoding="utf-8")
    assert "rec_B" in text
    assert "rec_A" not in text
