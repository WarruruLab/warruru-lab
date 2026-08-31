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


# ── 비공개 저장소로 밀어 넣기 (2026-08-28) ──────────────────────────

def _with_repo(client, path):
    """frozen dataclass 라 갈아 끼운다. 설정이 바뀐 데몬을 흉내낸다."""
    import dataclasses

    ctx = client.app.state.ctx
    ctx.settings = dataclasses.replace(ctx.settings, publish_repo=path)
    return ctx


def test_설정이_없으면_밀어넣기_버튼이_없다(client):
    """WARRURU_PUBLISH_REPO 를 정하지 않으면 이 기능은 아예 없다.
    데몬이 어느 저장소가 비공개인지 짐작하지 않는다.
    """
    draft = _draft(client)
    assert "비공개 저장소" not in client.get(f"/drafts/{draft['draft_id']}").text


def test_설정하면_버튼이_생긴다(client, tmp_path):
    draft = _draft(client)
    _with_repo(client, tmp_path / "notes")
    page = client.get(f"/drafts/{draft['draft_id']}").text
    assert "비공개 저장소" in page
    assert f"/web/drafts/{draft['draft_id']}/push" in page


def test_밀어넣기도_토큰을_요구한다(client, tmp_path):
    draft = _draft(client)
    _with_repo(client, tmp_path / "notes")
    assert client.post(
        f"/web/drafts/{draft['draft_id']}/push", data={}
    ).status_code == 401


def test_비공개가_아니면_화면이_그렇게_말한다(client, tmp_path):
    """예외가 500 으로 새어 나가면 사용자는 무엇이 문제인지 모른다.
    이 실패는 고칠 수 있는 실패다 — 무엇을 고쳐야 하는지 말해야 한다.
    """
    draft = _draft(client)
    _with_repo(client, tmp_path / "notes")
    posted = client.post(
        f"/web/drafts/{draft['draft_id']}/push",
        data={"_token": client.app.state.ctx.settings.token},
        follow_redirects=False,
    )
    assert posted.status_code == 302
    page = client.get(posted.headers["location"]).text
    assert "비공개" in page


# ── 미리보기 · 고치기 · 붙여넣기 (2026-08-29) ────────────────────────────
#
# 다듬는 루프가 두 창을 오갔다. 화면에서 보고 고치고 복사하는 데까지를
# 한 자리에 모은다. **모델을 부르는 일은 여전히 에이전트가 한다** —
# MCP 는 에이전트가 데몬을 부르는 단방향이라 데몬이 반대로 갈 길이 없다.


def test_미리보기가_구조를_그린다(client):
    made = _draft(client)
    page = client.get(f"/drafts/{made['draft_id']}").text
    assert 'class="preview"' in page
    assert "<h2>문제</h2>" in page          # 6단 제목이 제목으로 그려진다


def test_미리보기는_꼬리말을_빼고_그린다(client):
    """꼬리말은 정본 파일에만 남는다. 독자에게 `rec_01M0…` 은 아무 뜻이 없다."""
    made = _draft(client)
    page = client.get(f"/drafts/{made['draft_id']}").text
    preview = page.split('class="preview"')[1].split("</article>")[0]
    assert "조립에 쓴 기록" not in preview


def test_못_그리는_문법을_숨기지_않는다(client):
    """조용히 문단으로 눕히면 '여기서 이렇게 보였는데' 가 생긴다.

    표·인용문·번호목록·가로줄·링크는 2026-08-31 에 그릴 수 있게 됐다.
    남은 것은 이미지 하나다 — 로컬 파일을 가리키면 붙여넣는 순간 깨지고,
    외부 호스팅은 이 프로젝트가 하지 않기로 한 일이다.
    """
    made = _draft(client)
    client.post("/v1/drafts", json={
        "topic_slug": "connection-pool",
        "markdown": "# 제목\n\n![그림](./a.png)\n",
    })
    page = client.get(f"/drafts/{made['draft_id']}").text
    assert "이미지" in page


def test_붙여넣기는_마크다운이다(client):
    """티스토리는 2019년부터 마크다운 모드를 지원한다.
    HTML 로 바꿔 넣으면 원본이 그 자리에서 사라진다.
    """
    made = _draft(client)
    page = client.get(f"/drafts/{made['draft_id']}").text
    붙여넣기 = page.split('id="paste"')[1].split("</textarea>")[0]
    assert "## 문제" in 붙여넣기
    assert "<h2>" not in 붙여넣기


def test_화면에서_고친_본문이_저장된다(client):
    made = _draft(client)
    token = client.app.state.ctx.settings.token

    saved = client.post(
        f"/web/drafts/{made['draft_id']}/edit",
        data={"_token": token, "markdown": "# 손으로 고친 제목\n\n손으로 쓴 문장\n"},
        follow_redirects=False,
    )

    assert saved.status_code == 302
    row = client.app.state.ctx.records.latest_draft_of("connection-pool")
    assert "손으로 쓴 문장" in row["markdown"]


def test_토큰_없이는_고치지_못한다(client):
    """`/web/*` 는 인증 미들웨어 바깥이라 폼 토큰이 유일한 방어선이다."""
    made = _draft(client)
    거절 = client.post(
        f"/web/drafts/{made['draft_id']}/edit",
        data={"markdown": "몰래 고친다"}, follow_redirects=False,
    )
    assert 거절.status_code == 401


def test_요청을_적으면_붙여넣을_한_줄에_얹힌다(client):
    """데몬은 모델을 부르지 않는다. 옮겨 적는 수고를 줄이는 데까지다."""
    made = _draft(client)
    page = client.get(
        f"/drafts/{made['draft_id']}", params={"ask": "측정 절에 수치를 앞뒤로"}
    ).text
    assert "측정 절에 수치를 앞뒤로" in page
    assert f"draft={made['draft_id']}" in page


def test_블로그를_모르면_링크를_만들지_않는다(client):
    """데몬이 어느 블로그인지 짐작하지 않는다. `publish_repo` 와 같은 규칙이다."""
    made = _draft(client)
    assert "manage/newpost" not in client.get(f"/drafts/{made['draft_id']}").text


def test_블로그를_설정하면_글쓰기_링크가_생긴다(client):
    import dataclasses

    ctx = client.app.state.ctx
    ctx.settings = dataclasses.replace(ctx.settings, tistory_blog="myblog.tistory.com")
    made = _draft(client)
    page = client.get(f"/drafts/{made['draft_id']}").text
    assert "https://myblog.tistory.com/manage/newpost/" in page
