"""초안 화면 `/drafts/{id}` — 남은 TODO 와 다듬기 프롬프트를 보여준다.

다듬기는 **관문이 아니라 선택지다.** 붙여넣지 않고 자도 초안 파일은 이미 있다.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
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


def _draft(client):
    _record(client, "rec_A")
    return client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()


def test_초안_화면이_본문을_보여준다(client):
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "connection pool" in page
    assert "## 문제" in page


def test_초안_화면에_남은_TODO_가_보인다(client):
    """빈 자리가 곧 '면접에서 대답 못 할 부분' 목록이다. 눈에 띄어야 한다."""
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "TODO" in page
    assert "남은 TODO" in page


def test_다_채운_초안은_TODO_가_0개라고_말한다(client):
    # outcome 은 두 줄이어야 한다. 숫자가 든 줄은 '측정' 으로, 나머지는
    # '결과' 로 가므로 한 줄만 적으면 다른 절이 비어 TODO 가 남는다.
    # 그 빈칸은 "수치는 적었지만 그게 무슨 뜻인지는 안 적었다" 는 진단이다.
    _record(client, "rec_A", rationale="근거",
            outcome="p95 90ms 로 내려갔다\n대기 병목이 사라졌다",
            limitation="한계")
    draft = client.post("/v1/drafts",
                        json={"topic_slug": "connection-pool"}).json()
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "남은 TODO 0개" in page


def test_프롬프트_한_줄에_주제와_초안_id_가_들어_있다(client):
    """에이전트가 어느 글을 다듬는지 읽는 용도다. save_draft 의 인자가 아니다."""
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert f"polish topic=connection-pool draft={draft['draft_id']}" in page


def test_초안_파일_경로가_보인다(client):
    """마크다운이 정본이다. 어디 있는지 알아야 에디터로 열 수 있다."""
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "drafts/2026/08" in page


def test_없는_초안_id_는_404(client):
    assert client.get("/drafts/drf_없는것").status_code == 404


def test_조회는_토큰이_필요_없다(client, home):
    draft = _draft(client)
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        assert bare.get(f"/drafts/{draft['draft_id']}").status_code == 200


def test_주제_화면으로_돌아갈_수_있다(client):
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert 'href="/t/connection-pool"' in page


def test_수치만_적으면_결과_절이_TODO_로_남는다(client):
    """어림짐작이 만드는 진단이다 — "숫자는 적었는데 그게 무슨 뜻인지는 안 적었다"."""
    _record(client, "rec_A", rationale="근거", outcome="p95 90ms", limitation="한계")
    draft = client.post("/v1/drafts",
                        json={"topic_slug": "connection-pool"}).json()
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "남은 TODO 1개" in page


# ── 붙여넣기 발행 ──────────────────────────────────────────────────

def test_붙여넣기용_HTML_이_textarea_에_들어_있다(client):
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "<textarea" in page
    assert "&lt;h1&gt;" in page          # HTML 이 escape 되어 그대로 보인다


def test_스크립트_없이도_전체_선택으로_복사할_수_있다(client):
    """이 프로젝트의 유일한 JS 예외가 경로를 끊으면 안 된다."""
    draft = _draft(client)
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "readonly" in page
    assert "전체 선택" in page


def test_발행함_폼은_토큰이_없으면_401(client):
    draft = _draft(client)
    response = client.post(
        f"/web/drafts/{draft['draft_id']}/published",
        data={"published_url": "https://example.tistory.com/1"},
    )
    assert response.status_code == 401


def test_URL_을_넣으면_status_가_PUBLISHED_가_된다(client):
    draft = _draft(client)
    token = client.app.state.ctx.settings.token
    response = client.post(
        f"/web/drafts/{draft['draft_id']}/published",
        data={"_token": token, "published_url": "https://example.tistory.com/1"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "PUBLISHED" in page
    assert "example.tistory.com/1" in page


def test_발행하면_초안_파일의_status_도_바뀐다(client, home):
    """파일이 정본이다. DB 만 바꾸면 파일을 여는 사람이 옛 상태를 본다."""
    draft = _draft(client)
    token = client.app.state.ctx.settings.token
    client.post(
        f"/web/drafts/{draft['draft_id']}/published",
        data={"_token": token, "published_url": "https://example.tistory.com/1"},
        follow_redirects=False,
    )
    text = (home / "drafts" / "2026" / "08" / "2026-08-25-connection-pool.md").read_text(
        encoding="utf-8"
    )
    assert "status: PUBLISHED" in text


def test_발행해도_저장소_안에는_파일이_생기지_않는다(client, home):
    draft = _draft(client)
    token = client.app.state.ctx.settings.token
    client.post(
        f"/web/drafts/{draft['draft_id']}/published",
        data={"_token": token, "published_url": "https://example.tistory.com/1"},
        follow_redirects=False,
    )
    repo = client.app.state.ctx.settings.repo_root
    assert repo is None or not list(repo.rglob("2026-08-25-connection-pool.md"))
