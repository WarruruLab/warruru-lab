"""주제 화면 `/t` — 하루치 기록이 주제로 묶여 한 줄이 된다.

Jinja2 서버 렌더링. 조회는 토큰이 필요 없고 JS 는 테마 전환에만 쓴다.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

# KST 로 2026-08-24 18:00. 로컬 자정 경계를 시험하기 좋은 시각이다.
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
        "record_id": record_id,
        "client_instance_id": CLIENT,
        "tool": "codex",
        "kind": "EXPERIMENT",
        "topic": "connection pool",
        "title": "풀 크기 10→30",
        "body": "p95 320ms→90ms",
    }
    body.update(extra)
    return client.post("/v1/records", json=body)


def test_그날_전달된_것이_없으면_그렇게_말한다(client):
    """**화면이 비지는 않는다.** 그날 것이 없어도 '만든 글' 은 남는다 —
    홈이 `/d/{오늘}` 로 보내던 때와 같은 실패를 되풀이하지 않는다."""
    page = client.get("/t")
    assert page.status_code == 200
    assert "<h2>오늘의 기록</h2>" in page.text
    assert "record_learning" in page.text
    assert "<h2>만든 글</h2>" in page.text

def test_조회는_토큰이_필요_없다(home, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        assert bare.get("/t").status_code == 200


def test_기록을_제목으로_읽는다(client):
    """**205건이 다 제목을 갖고 있는데 화면에는 하나도 없었다**(2026-09-08).

    전에는 슬러그와 숫자만 있었다 — `db-index 9건 개념1 실험6 재료 4/4`.
    무엇을 알게 됐는지가 화면 어디에도 없으면 그 목록은 읽을 것이 없다.
    """
    _record(client, "rec_A", title="풀 크기를 30 이상 못 올린 이유")
    page = client.get("/t").text
    assert "풀 크기를 30 이상 못 올린 이유" in page
    assert "실험" in page                     # 종류도 사람 말로

def test_kind_배지가_보인다(client):
    _record(client, "rec_A")
    _record(client, "rec_B", kind="TROUBLESHOOTING")
    page = client.get("/t").text
    assert "실험" in page and "트러블슈팅" in page


def test_주제_슬러그도_같이_보인다(client):
    """제목이 주인공이고 슬러그는 어느 묶음인지 말한다."""
    _record(client, "rec_A", topic="  Connection Pool  ")
    page = client.get("/t").text
    assert "connection-pool" in page

def test_면접_문장이_비었으면_그_자리에_표시된다(client):
    """205건 중 43건뿐이다. 목록에서 안 드러나면 영영 안 채운다."""
    _record(client, "rec_A")
    page = client.get("/t").text
    assert "면접 —" in page
    assert "면접 문장 0/1" in page

def test_그날_경계는_로컬_자정_기준이다(client):
    """UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다."""
    # KST 2026-08-24 00:30 = UTC 2026-08-23 15:30
    _record(client, "rec_오늘새벽", title="새벽에 한 것",
            occurred_at="2026-08-23T15:30:00.000Z")
    # KST 2026-08-23 23:30 = UTC 2026-08-23 14:30
    _record(client, "rec_어제밤", topic="jvm gc", title="어젯밤에 한 것",
            occurred_at="2026-08-23T14:30:00.000Z")
    page = client.get("/t").text
    assert "새벽에 한 것" in page
    assert "어젯밤에 한 것" not in page
    assert "어젯밤에 한 것" in client.get("/t?date=2026-08-23").text

def test_기록도_미래로는_못_간다(client):
    """홈과 같은 규칙이다 — 아직 안 온 날에 전달된 것이 있을 리 없다."""
    _record(client, "rec_더전날", title="더 앞에 한 일",
            occurred_at="2026-08-20T09:00:00.000Z")
    _record(client, "rec_전날", title="전날에만 한 일",
            occurred_at="2026-08-23T09:00:00.000Z")

    today = client.get("/t").text
    assert 'href="/t?date=2026-08-23"' in today
    assert 'href="/t?date=2026-08-25"' not in today
    assert "전날에만 한 일" not in today

    previous = client.get("/t?date=2026-08-23").text
    assert "전날에만 한 일" in previous
    assert 'href="/t?date=2026-08-22"' in previous
    assert 'href="/t?date=2026-08-24"' in previous

def test_홈의_잘못된_날짜는_400이다(client):
    assert client.get("/t?date=2026-02-30").status_code == 400


# ── 지난 주제 ────────────────────────────────────────────────────────────
#
# 처음 이 화면을 오늘로 자른 전제는 "하루가 끝나는 시점에 열어본다" 였다.
# 바탕화면 실행 파일이 생기면서 그 전제가 깨졌다 — 기록하지 않은 날에도 이
# 화면을 연다. 그때 화면이 비어 있으면 **들어가는 문이 가진 것을 숨기는 것**이다.


def test_그날_것이_없어도_만든_글은_남는다(client):
    """날짜로만 자르면 0건인 날에 화면이 통째로 빈다.
    초안 목록은 날짜와 무관하다."""
    _record(client, "rec_A", occurred_at="2026-08-20T09:00:00.000Z")
    client.post("/v1/drafts", json={"topic_slug": "connection-pool"})
    page = client.get("/t").text
    assert "오늘의 기록" in page and ">0</b>건" in page   # 그날 신호는 그대로
    assert "connection-pool" in page                      # 만든 글이 남는다

def test_만든_글이_최근순으로_선다(client):
    """만든 것을 못 찾으면 만든 적이 없는 것과 같다."""
    _record(client, "rec_A", topic="jvm gc")
    _record(client, "rec_B", topic="net tcp")
    client.post("/v1/drafts", json={"topic_slug": "jvm-gc"})
    client.post("/v1/drafts", json={"topic_slug": "net-tcp"})
    만든글 = client.get("/t").text.split("<h2>만든 글</h2>")[1]
    assert 만든글.index("net-tcp") < 만든글.index("jvm-gc")

def test_이미_발행한_주제는_뒤로_간다(client):
    """이미 낸 글을 먼저 보여줄 이유가 없다."""
    from warruru_local.daemon import today as todayview

    _record(client, "rec_A", topic="jvm gc")
    _record(client, "rec_B", topic="net tcp")
    ctx = client.app.state.ctx
    draft = client.post("/v1/drafts", json={"topic_slug": "jvm-gc"}).json()
    client.post(f"/web/drafts/{draft['draft_id']}/published",
                data={"_token": ctx.settings.token,
                      "published_url": "https://example.com/a"},
                follow_redirects=False)
    글감 = [row["slug"] for row in todayview.writable(ctx)]
    assert 글감[-1] == "jvm-gc"

def test_기록을_골라_글로_만든다(client):
    """**주제가 아니라 기록 단위로 고른다** — 한 주제 안에서도 이번 글에
    넣을 것과 뺄 것이 갈린다."""
    _record(client, "rec_A")
    _record(client, "rec_B")
    page = client.get("/t").text
    # JS 안에도 같은 이름이 나오므로 **체크박스만** 센다.
    assert page.count('type="checkbox" name="record_id"') == 2
    assert 'action="/web/drafts/compose"' in page
    assert "글로 만들기" in page

def test_주제_한_줄에서_상세로_간다(client):
    _record(client, "rec_A")
    assert '/t/connection-pool' in client.get("/t").text


# ── /t/{slug} 상세 ─────────────────────────────────────────────────

def test_주제_상세는_기록을_시간순으로_보여준다(client):
    """읽는 순서가 곧 서사 순서다. 목록과 달리 오래된 것부터 펼친다."""
    _record(client, "rec_먼저", title="먼저 한 것",
            occurred_at="2026-08-24T07:00:00.000Z")
    _record(client, "rec_나중", title="나중 한 것",
            occurred_at="2026-08-24T09:00:00.000Z")
    page = client.get("/t/connection-pool").text
    assert page.index("먼저 한 것") < page.index("나중 한 것")


def test_상세도_topic_원문을_보여준다(client):
    _record(client, "rec_A", topic="  Connection Pool  ")
    assert "Connection Pool" in client.get("/t/connection-pool").text


def test_부족한_필드_목록이_초안_만들기_옆에_보인다(client):
    """초안 품질이 낮은 이유가 조립기가 아니라 재료라는 사실을
    누르기 전에 보여줘야 다음 기록이 나아진다.
    """
    _record(client, "rec_A")
    _record(client, "rec_B", outcome="결과 있음")
    page = client.get("/t/connection-pool").text
    assert "초안 만들기" in page
    assert "부족한 필드" in page
    assert "limitation" in page
    assert "2건 중 2건" in page      # limitation 은 둘 다 비었다
    assert "2건 중 1건" in page      # outcome 은 하나만 비었다


def test_다_채운_주제는_부족한_필드가_없다고_말한다(client):
    _record(client, "rec_A", rationale="근거", outcome="결과",
            limitation="한계", interview="문장")
    page = client.get("/t/connection-pool").text
    assert "부족한 필드 없음" in page


def test_초안_만들기는_폼이고_토큰을_싣는다(client):
    """Task 7 에서는 disabled 자리표시자였고, Task 8 에서 동작이 붙었다.

    상태를 바꾸는 요청이므로 폼 토큰을 함께 보낸다 —
    다른 출처의 페이지가 내 데몬을 조작하지 못하게 하는 유일한 방어선이다.
    """
    _record(client, "rec_A")
    page = client.get("/t/connection-pool").text
    assert 'action="/web/topics/connection-pool/draft"' in page
    assert 'name="_token"' in page
    assert "준비 중" not in page


def test_기록이_없는_슬러그는_404(client):
    assert client.get("/t/그런-주제-없다").status_code == 404


def test_상세는_그_주제의_전체_기간을_보여준다(client):
    """목록은 오늘이지만 상세는 전체다. 글 한 편의 재료는 하루치가 아니다."""
    _record(client, "rec_어제", occurred_at="2026-08-20T09:00:00.000Z")
    _record(client, "rec_오늘", occurred_at="2026-08-24T09:00:00.000Z")
    page = client.get("/t/connection-pool").text
    assert "2건" in page


def test_기록_갈래_안에서_날짜_화면과_오갈_수_있다(client):
    """탭은 갈래끼리만 잇는다. 그날 기록과 달력은 **기록 갈래 안**이라
    그 화면에서 간다 — 전에는 둘 다 네비에 있었다(2026-09-08 재편)."""
    _record(client, "rec_A")
    page = client.get("/t").text
    assert 'class="tabs"' in page
    assert 'href="/d/2026-08-24"' in page
    page = client.get("/t/connection-pool").text
    assert 'href="/t"' in page


def test_발행한_주제에는_체크_표시가_붙는다(client):
    """무엇을 이미 글로 냈는지 목록에서 한눈에 보여야 한다."""
    _record(client, "rec_A")
    _record(client, "rec_B")
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    token = client.app.state.ctx.settings.token
    client.post(
        f"/web/drafts/{draft['draft_id']}/published",
        data={"_token": token, "published_url": "https://example.tistory.com/1"},
        follow_redirects=False,
    )
    assert "발행함" in client.get("/t").text


# ── 초안으로 돌아가는 길 ────────────────────────────────────────────

def test_이미_만든_초안으로_돌아갈_수_있다(client):
    """초안 화면에는 붙여넣기용 HTML 과 발행 폼이 있다 — 한 바퀴의 마지막
    두 걸음이다. 만든 뒤 그 화면을 떠나면 돌아갈 길이 주소 기억뿐이라면,
    다음 날 이어서 하려는 사람은 다시 만들거나 포기한다.
    """
    _record(client, "rec_A")
    made = client.post(
        "/web/topics/connection-pool/draft",
        data={"_token": client.app.state.ctx.settings.token},
        follow_redirects=False,
    )
    draft_id = made.headers["location"].rsplit("/", 1)[-1]

    page = client.get("/t/connection-pool").text
    assert f'href="/drafts/{draft_id}"' in page


def test_초안이_없으면_그_링크도_없다(client):
    _record(client, "rec_A")
    assert "/drafts/" not in client.get("/t/connection-pool").text


def test_주제_상세의_날짜는_로컬_기준이다(client):
    """UTC 문자열 앞 10자를 자르면 KST 오전 9시 이전 기록이 앞날로 적힌다.
    날짜 경계는 예외 없이 clock 을 거친다.
    """
    # KST 2026-08-25 09:30. UTC 로는 00:30 이라 앞 10자를 자르면 같은 날이지만,
    # 자정 직후 한 시간은 UTC 로 전날이 된다 — 그 자리를 시험한다.
    _record(client, "rec_A", occurred_at="2026-08-24T16:30:00.000Z")
    page = client.get("/t/connection-pool").text
    assert "2026-08-25" in page      # KST 25일 01:30


# ── 재료 막대 ──────────────────────────────────────────────────────

def test_재료가_얼마나_찼는지_보여준다(client):
    """건수만으로는 '뭘 글로 쓸 수 있나' 에 답이 안 나온다 —
    3건이어도 재료가 비면 못 쓴다. 막대는 주제 화면에 있다."""
    _record(client, "rec_A", rationale="골랐다", outcome="p95 90ms")
    _record(client, "rec_B")
    page = client.get("/t/connection-pool").text
    assert 'class="gauge"' in page
    assert "재료" in page

def test_막대는_주제마다_네_칸이다(client):
    """칸 수가 주제마다 다르면 눈으로 비교가 안 된다."""
    _record(client, "rec_A", rationale="골랐다")
    _record(client, "rec_B")
    page = client.get("/t/connection-pool").text
    assert page.count('class="seg') == 4

def test_상세도_같은_막대를_쓴다(client):
    _record(client, "rec_A", rationale="골랐다")
    assert 'class="gauge"' in client.get("/t/connection-pool").text


def test_막대에_뜻을_적어_둔다(client):
    """전에는 `재료 3/4` 라고만 있고 **그게 무슨 뜻인지 어디에도 없었다.**
    화면이 안 읽히는 이유가 그것이었다(2026-09-08 사용자 지적)."""
    _record(client, "rec_A", rationale="골랐다")
    page = client.get("/t/connection-pool").text
    assert 'class="gauge"' in page
    for 말 in ("왜 그렇게 판단했나", "그래서 어떻게 됐나",
              "어디까지만 맞나", "면접에서 어떻게 말할까"):
        assert 말 in page, 말

def test_막대는_하루치가_아니라_주제_전체를_센다(client):
    """초안 조립기는 그 주제의 기록을 **전부** 재료로 쓴다.

    하루로 자르면 어제 채운 rationale 이 오늘 빈칸으로 보인다.
    """
    _record(client, "rec_어제", occurred_at="2026-08-23T09:00:00.000Z",
            rationale="골랐다")
    _record(client, "rec_오늘", occurred_at="2026-08-24T09:00:00.000Z")
    assert "재료 1/4" in client.get("/t/connection-pool").text

def test_주제_화면이_면접_문장을_보여준다(client):
    """읽는 사람이 둘이라 화면도 둘이다. 티스토리는 독자용,
    /t/{slug} 는 되짚어 읽는 본인용이다.
    """
    _record(client, "rec_A", interview="이렇게 말합니다")
    assert "이렇게 말합니다" in client.get("/t/connection-pool").text


def test_면접_문장은_발행_본문에_안_들어간다(client):
    """독자가 '면접에서는 이렇게 말합니다' 를 읽을 이유가 없다."""
    _record(client, "rec_A", interview="이렇게 말합니다")
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    page = client.get(f"/drafts/{draft['draft_id']}").text
    # **붙여넣기 칸을 이름으로 집는다.** 첫 `<textarea>` 로 집으면 화면에
    # 칸이 하나 늘 때마다 이 테스트가 엉뚱한 곳을 본다 — 다듬기 칸이
    # 위에 생기면서 실제로 그렇게 됐다(2026-09-08).
    paste = page.split('id="paste"', 1)[1].split("</textarea>")[0]
    assert "이렇게 말합니다" not in paste


def test_발행_본문에_내부_식별자가_없다(client):
    """꼬리말은 정본 파일에 남고 붙여넣기용에서는 빠진다."""
    _record(client, "rec_A")
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    page = client.get(f"/drafts/{draft['draft_id']}").text
    paste = page.split('id="paste"', 1)[1].split("</textarea>")[0]
    assert "조립에 쓴 기록" not in paste
    assert "rec_A" not in paste
    assert "문제" in paste          # 본문은 그대로다


def test_정본_파일에는_꼬리말이_남는다(client):
    """파일만 열어도 재료를 되짚을 수 있어야 한다."""
    import pathlib

    _record(client, "rec_A")
    made = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    assert "조립에 쓴 기록" in pathlib.Path(made["file_path"]).read_text(encoding="utf-8")


def test_채울_수_없는_절을_누르기_전에_알려준다(client):
    """재료 막대가 4/4 여도 CONCEPT 한 건이면 '구현' 절은 빈다."""
    _record(client, "rec_A", kind="CONCEPT", rationale="근거",
            outcome="p95 90ms", limitation="한계", interview="문장")
    page = client.get("/t/connection-pool").text
    assert "재료 4/4" in page
    assert "구현" in page


# ── 기록이 없는 주제 (2026-08-31) ────────────────────────────────────

def test_아는_주제는_기록이_없어도_열린다(client):
    """기술스택 화면의 배지가 전부 이리로 온다. 404 면 목록 전체가 죽은 링크다."""
    response = client.get("/t/ds-hash")
    assert response.status_code == 200
    assert "해시" in response.text
    assert "아직 기록이 없다" in response.text


def test_모르는_슬러그는_404_그대로(client):
    """오타를 알 수 있어야 한다."""
    assert client.get("/t/없는주제").status_code == 404
    assert client.get("/t/ds-hashh").status_code == 404


def test_빈_화면이_채우는_방법을_준다(client):
    page = client.get("/t/ds-hash").text
    assert "record topic=ds-hash" in page
    assert 'href="/career/stack/ds"' in page      # 어느 묶음인지


def test_빈_화면이_요구하는_곳을_보여준다(client, home):
    """왜 이 주제가 목록에 있는지가 곧 공부할 이유다."""
    from warruru_local import paths

    root = paths.career_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / "hyundai-autoever.md").write_text(
        "---\ncompany: 현대오토에버\nrequired:\n  - RDBMS | db-index\n---\n# 메모\n",
        encoding="utf-8",
    )
    page = client.get("/t/db-index").text
    assert "현대오토에버" in page          # 회사
    assert "SQLD" in page                  # 자격증


def test_기록이_생기면_원래_화면으로_돌아간다(client):
    client.post("/v1/records", json={
        "record_id": "rec_A", "client_instance_id": CLIENT, "tool": "codex",
        "kind": "CONCEPT", "topic": "ds-hash",
        "title": "해시 충돌", "body": "체이닝과 개방주소법",
    })
    page = client.get("/t/ds-hash").text
    assert "아직 기록이 없다" not in page
    assert "해시 충돌" in page


def _note(home, slug, text):
    from warruru_local import paths

    root = paths.topic_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{slug}.md").write_text(text, encoding="utf-8")


NOTE = """---
label: 해시
refs:
  - Hash | https://github.com/gyoogle/tech-interview-for-developer/blob/master/x.md
  - 나쁜 링크 | javascript:alert(1)
---

# 확인할 것

- 해시 충돌을 어떻게 해결하나?
"""


def test_참고_자료가_빈_주제_화면에_붙는다(client, home):
    _note(home, "ds-hash", NOTE)
    page = client.get("/t/ds-hash").text
    assert "참고" in page
    assert "해시 충돌을 어떻게 해결하나" in page
    assert "github.com/gyoogle" in page


def test_기록이_생겨도_참고는_남는다(client, home):
    """면접 준비로 되읽을 때 필요하다."""
    _note(home, "ds-hash", NOTE)
    client.post("/v1/records", json={
        "record_id": "rec_H", "client_instance_id": CLIENT, "tool": "codex",
        "kind": "CONCEPT", "topic": "ds-hash", "title": "충돌", "body": "본문",
    })
    page = client.get("/t/ds-hash").text
    assert "충돌" in page
    assert "해시 충돌을 어떻게 해결하나" in page


def test_노트가_없어도_주제_화면은_열린다(client):
    """노트는 있으면 좋은 것이지 관문이 아니다."""
    assert client.get("/t/algo-dp").status_code == 200


def test_참고_링크도_수상하면_안_건다(client, home):
    _note(home, "ds-hash", NOTE)
    page = client.get("/t/ds-hash").text
    assert "javascript:alert" not in page


# ── 물어보고 받은 답 (2026-09-01) ────────────────────────────────────

def _answer(home, slug, name, text):
    from warruru_local import paths

    root = paths.answer_dir(home) / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.md").write_text(text, encoding="utf-8")


def test_물어보기_한_줄이_주제_화면에_있다(client):
    page = client.get("/t/ds-hash").text
    assert "ask topic=ds-hash" in page


def test_받은_답이_최신순으로_쌓인다(client, home):
    _answer(home, "ds-hash", "2026-09-01",
            "---\nasked: 충돌 해결법\ntool: claude-code\n---\n\n체이닝과 개방주소법.\n")
    _answer(home, "ds-hash", "2026-08-30", "---\nasked: 리해싱\n---\n\n부하율.\n")
    page = client.get("/t/ds-hash").text
    지난 = page[page.index('id="chat-past-view"'):]
    지난 = 지난[:지난.index("</div>", 지난.index("</ul>"))]
    assert "2026-09-01" in 지난 and "2026-08-30" in 지난
    assert 지난.index("충돌 해결법") < 지난.index("리해싱")   # 최신이 위


def test_답은_기록이_아니라고_말한다(client, home):
    """기록은 '내 말로 정리했다' 다. 받은 답을 기록으로 세면 숫자가 거짓말이 된다."""
    _answer(home, "ds-hash", "2026-09-01", "---\nasked: 충돌\n---\n\n답.\n")
    page = client.get("/t/ds-hash").text
    assert "기록이 아니다" in page
    assert "0건" in page          # 기록은 그대로 0


def test_답이_없어도_주제_화면은_열린다(client):
    assert client.get("/t/algo-dp").status_code == 200


# ── 주제 화면에서 묻는다 (명세 §2.6 · §3.7, 2026-09-06) ─────────────

import json as _json
import stat as _stat


def _fake_cli(tmp_path, lines):
    """JSONL 을 뱉는 가짜. **진짜 CLI 를 부르는 테스트는 만들지 않는다** —
    네트워크와 구독 한도에 기대면 아침마다 다르게 실패한다."""
    path = tmp_path / "fake-cli"
    body = "\n".join(_json.dumps(line, ensure_ascii=False) for line in lines)
    path.write_text(f"#!/bin/sh\ncat <<'EOF'\n{body}\nEOF\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | _stat.S_IEXEC)
    return str(path)


ANSWER = [
    {"type": "thread.started", "thread_id": "th_0001"},
    {"type": "item.completed",
     "item": {"type": "agent_message", "text": "B+트리는 범위 검색 때문이다."}},
    {"type": "turn.completed", "usage": {"input_tokens": 900, "output_tokens": 100}},
]


@pytest.fixture
def fake_ask(monkeypatch, tmp_path):
    """`Ask` 가 언제나 가짜를 부르게 한다."""
    from warruru_local.daemon import asking

    program = _fake_cli(tmp_path, ANSWER)
    real = asking.Ask.argv

    def argv(self):
        object.__setattr__(self, "program", program)
        return real(self)

    monkeypatch.setattr(asking.Ask, "argv", argv)
    return program


def _ask(client, slug, prompt="B+트리를 왜 쓰나", **extra):
    body = {"prompt": prompt, "_token": client.app.state.ctx.settings.token}
    body.update(extra)
    return client.post(f"/web/topics/{slug}/ask", data=body)


def _events(text):
    made = []
    for block in text.split("\n\n"):
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            if line.startswith("data: "):
                data = _json.loads(line[6:])
        if name:
            made.append((name, data))
    return made


def test_물으면_답이_이벤트로_흐른다(client, fake_ask):
    res = _ask(client, "db-index")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in _events(res.text)]
    assert names == ["started", "message", "done"]


def test_답이_주제별_파일에_이어_쓰인다(client, fake_ask, home):
    from warruru_local import paths

    _ask(client, "db-index", "첫 질문")
    _ask(client, "db-index", "두 번째 질문")
    files = list((paths.answer_dir(home) / "db-index").glob("*.md"))
    # 같은 날 여러 번 물으면 **파일이 늘어나는 것이 아니라** 한 장이 길어진다.
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "asked: 첫 질문" in text
    assert "## 두 번째 질문" in text


def test_두_번째_질문은_같은_스레드로_간다(client, fake_ask):
    _ask(client, "db-index")
    again = _events(_ask(client, "db-index").text)
    started = dict(again)["started"]
    assert started["resumed"] is True
    assert client.app.state.ctx.records.ask_thread("db-index")["turns"] == 2


def test_주제가_다르면_대화도_다르다(client, fake_ask):
    _ask(client, "db-index")
    assert dict(_events(_ask(client, "algo-dp").text))["started"]["resumed"] is False


def test_새_대화로_체크하면_스레드를_버린다(client, fake_ask):
    _ask(client, "db-index")
    again = _events(_ask(client, "db-index", fresh=1).text)
    assert dict(again)["started"]["resumed"] is False


def test_빈_질문은_거절한다(client, fake_ask):
    assert _ask(client, "db-index", prompt="   ").status_code == 400


def test_토큰이_없으면_묻지_못한다(client, fake_ask):
    res = client.post("/web/topics/db-index/ask", data={"prompt": "질문"})
    assert res.status_code == 401


def test_답을_못_받으면_스레드를_붙잡지_않는다(client, monkeypatch, tmp_path):
    """실패한 왕복까지 세면 다음 질문이 없는 대화를 이어받으려 한다."""
    from warruru_local.daemon import asking

    # 스레드는 열렸는데 답이 없는 경우다.
    program = _fake_cli(tmp_path, [{"type": "thread.started", "thread_id": "th_9"}])
    real = asking.Ask.argv

    def argv(self):
        object.__setattr__(self, "program", program)
        return real(self)

    monkeypatch.setattr(asking.Ask, "argv", argv)
    events = _events(_ask(client, "db-index").text)
    assert dict(events)["done"]["saved"] == ""
    assert client.app.state.ctx.records.ask_thread("db-index") is None


def test_화면에_챗봇이_있다(client, fake_ask):
    """카드 안에 접혀 있으면 '공부하다 물어본다' 가 아니라
    '화면을 찾아가서 쓴다' 가 된다(2026-09-08 확정)."""
    page = client.get("/t/db-index").text
    assert 'id="chat-panel"' in page and 'id="chat-open"' in page
    # 터미널용 한 줄도 남는다 — JS 가 꺼져도 물어볼 길은 있어야 한다.
    assert "ask topic=db-index" in page


def test_초안_조립기는_여전히_LLM_을_안_부른다():
    """이 경로를 열면서 지키려던 경계다(명세 §2.4 · §6).

    조립기가 `asking` 이나 `subprocess` 를 알게 되는 순간 '결정적'이라는
    말이 거짓이 된다.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "warruru_local"
    text = (src / "daemon" / "draft.py").read_text(encoding="utf-8")
    for 금지 in ("asking", "subprocess", "openai", "anthropic"):
        assert 금지 not in text, 금지


def test_여러_줄_질문이_앞머리를_깨지_않는다(client, fake_ask, home):
    """줄바꿈이나 `---` 가 앞머리에 그대로 들어가면 거기서 닫히고,
    그 파일은 다음에 읽을 때 본문을 통째로 잃는다."""
    from warruru_local import paths
    from warruru_local.daemon import careerview

    _ask(client, "db-index", prompt="첫 줄\n---\n둘째 줄")
    path = next((paths.answer_dir(home) / "db-index").glob("*.md"))
    meta, body = careerview.parse_front_matter(path.read_text(encoding="utf-8"))
    assert meta["asked"] == "첫 줄 --- 둘째 줄"
    assert "B+트리는 범위 검색" in body


def test_경로_탈출을_거부한다(client, fake_ask, home):
    """이 값이 그대로 디렉터리 이름이 된다 — `..` 하나로 답 파일이
    홈 밖에 앉는다. 회사 노트가 같은 이유로 이미 같은 검사를 한다."""
    for 나쁜값 in ("..", "../secret", "UPPER", "빈칸 있음", "-앞이대시"):
        res = client.post(f"/web/topics/{나쁜값}/ask", data={
            "prompt": "질문", "_token": client.app.state.ctx.settings.token})
        assert res.status_code in (404, 400), 나쁜값


def test_모르는_CLI_는_거절한다(client, fake_ask):
    assert _ask(client, "db-index", cli="gpt5").status_code == 400


def test_CLI_를_바꾸면_대화를_잇지_않는다(client, fake_ask):
    """스레드 id 는 그 CLI 안에서만 뜻이 있다. codex 의 id 를 claude 에
    넘기면 조용히 새 대화가 열리거나 실패한다."""
    _ask(client, "db-index", cli="codex")
    다시 = _events(_ask(client, "db-index", cli="claude").text)
    assert dict(다시)["started"]["resumed"] is False
    assert client.app.state.ctx.records.ask_thread("db-index")["cli"] == "claude"


def test_정리는_정해진_프롬프트로_간다(client, fake_ask, home):
    """정리 문장을 화면에서 만들면 버전도 테스트도 안 붙고,
    두 화면이 조금씩 다른 문장을 보내기 시작한다."""
    from warruru_local import paths
    from warruru_local.daemon.routes_web import SUMMARY_PROMPT

    assert "지어내" in SUMMARY_PROMPT or "대화에 나온 것만" in SUMMARY_PROMPT
    _ask(client, "db-index", prompt="B+트리가 뭐야")
    res = _ask(client, "db-index", prompt="", mode="summary")
    assert res.status_code == 200
    text = next((paths.answer_dir(home) / "db-index").glob("*.md")).read_text(encoding="utf-8")
    assert "## 오늘 정리" in text


# ── 기록으로 승격 (명세 §2.8, 2026-09-08) ────────────────────────

def _promote(client, key, **extra):
    body = {
        "topic": "db-index", "kind": "CONCEPT",
        "title": "인덱스는 B+트리다", "body": "범위 검색 때문이다.",
        "_token": client.app.state.ctx.settings.token,
    }
    body.update(extra)
    return client.post(f"/web/topics/{key}/promote", data=body, follow_redirects=False)


def test_정리를_기록으로_올린다(client):
    """받은 답은 참고 자료이고 기록은 '내 말로 정리했다' 인데, 그 사이를
    건너는 다리가 없어서 답이 쌓이는 동안 기록은 따로 남겨야 했다."""
    res = _promote(client, "book-kafka-practice")
    assert res.status_code == 303
    assert res.headers["location"] == "/t/db-index"

    rows = client.get("/v1/records", params={"topic_slug": "db-index"}).json()["records"]
    assert [r["title"] for r in rows] == ["인덱스는 B+트리다"]
    assert rows[0]["tool"] == "web"       # 어디서 왔는지 남는다


def test_주제를_고르게_한다(client):
    """책 하나가 주제 열한 개를 덮는다. 임의로 고르면 틀린 자리에 쌓이고,
    틀린 자리에 쌓인 기록은 아무 화면에서도 안 보인다."""
    page = client.get("/career/book/kafka-practice").text
    폼 = page[page.index('id="chat-promote"'):]
    폼 = 폼[:폼.index("</form>")]
    assert 폼.count("<option value=") >= 11      # 그 책이 덮는 주제들
    assert "kafka-basics" in 폼


def test_면접_문장도_같이_받는다(client):
    """비우면 면접에 들고 갈 문장이 하나 덜 생긴다 — 지금 15% 인 그 필드다."""
    _promote(client, "db-index", interview="범위 검색 때문이라고 답했습니다")
    rows = client.get("/v1/records", params={"topic_slug": "db-index"}).json()["records"]
    assert rows[0]["interview"] == "범위 검색 때문이라고 답했습니다"


def test_빈_기록은_거절한다(client):
    assert _promote(client, "db-index", title=" ").status_code == 400
    assert _promote(client, "db-index", body="").status_code == 400


def test_토큰_없이는_못_올린다(client):
    res = client.post("/web/topics/db-index/promote", data={
        "topic": "db-index", "title": "제목", "body": "본문"})
    assert res.status_code == 401


def test_지난_대화는_읽기만_한다(client, home):
    """이어가려면 CLI 세션 id 를 날짜별로 들어야 해서 스키마가 는다.
    읽기만 하기로 정했다(2026-09-08)."""
    _answer(home, "ds-hash", "2026-09-01", "---\nasked: 충돌\n---\n\n답.\n")
    지난 = client.get("/t/ds-hash").text
    지난 = 지난[지난.index('id="chat-past-view"'):]
    지난 = 지난[:지난.index("</div>", 지난.index("</ul>"))]
    assert "읽기만 한다" in 지난
    assert "ask" not in 지난.lower() or "form" not in 지난.lower()
