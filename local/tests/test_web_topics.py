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


def test_오늘_기록이_없으면_0건이_붉게_보인다(client):
    page = client.get("/t")
    assert page.status_code == 200
    assert "오늘 기록 0건" in page.text
    assert "empty-today" in page.text


def test_조회는_토큰이_필요_없다(home, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        assert bare.get("/t").status_code == 200


def test_슬러그별로_건수와_마지막_시각이_보인다(client):
    _record(client, "rec_A", occurred_at="2026-08-24T09:00:00.000Z")
    _record(client, "rec_B", occurred_at="2026-08-24T07:40:00.000Z")
    page = client.get("/t").text
    assert "2건" in page
    assert "18:00" in page          # KST 로 마지막 기록 시각


def test_kind_배지가_보인다(client):
    _record(client, "rec_A")
    _record(client, "rec_B", kind="TROUBLESHOOTING")
    page = client.get("/t").text
    assert "실험" in page and "트러블슈팅" in page


def test_topic_원문이_화면에_그대로_나온다(client):
    """화면이 보여줄 것은 슬러그가 아니라 사람이 적은 말이다."""
    _record(client, "rec_A", topic="  Connection Pool  ")
    page = client.get("/t").text
    assert "Connection Pool" in page


def test_1건짜리_슬러그는_미분류_구획에_모인다(client):
    """오타 교정 장치다. 병합 UI 는 만들지 않는다 — SQL 한 줄이 화면보다 싸다."""
    _record(client, "rec_A")
    _record(client, "rec_B")
    _record(client, "rec_C", topic="connectoin pool")   # 오타
    page = client.get("/t").text
    assert "미분류" in page
    body = page.split("미분류")[1]
    assert "connectoin pool" in body
    assert "connectoin pool" not in page.split("미분류")[0]


def test_오늘_경계는_로컬_자정_기준이다(client):
    """UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다.

    어제 것이 화면에서 사라지지는 않는다(명세 §2.2 개정). 확인할 것은
    **어느 구획에 앉느냐**다 — 새벽 기록이 '지난 주제' 로 밀리면 경계가 UTC 로
    잘린 것이다.
    """
    # KST 2026-08-24 00:30 = UTC 2026-08-23 15:30
    _record(client, "rec_오늘새벽", occurred_at="2026-08-23T15:30:00.000Z")
    # KST 2026-08-23 23:30 = UTC 2026-08-23 14:30
    _record(client, "rec_어제밤", topic="jvm gc",
            occurred_at="2026-08-23T14:30:00.000Z")
    page = client.get("/t").text
    오늘, 지난 = page.split("지난 주제")
    assert "connection pool" in 오늘
    assert "jvm gc" not in 오늘
    assert "jvm gc" in 지난


def test_홈의_날짜_화살표로_전날과_다음날을_본다(client):
    _record(client, "rec_전날", title="전날에만 한 일",
            occurred_at="2026-08-23T09:00:00.000Z")

    today = client.get("/t").text
    assert 'href="/t?date=2026-08-23"' in today
    assert 'href="/t?date=2026-08-25"' in today

    previous = client.get("/t?date=2026-08-23").text
    assert "2026-08-23" in previous
    assert "선택 날짜 기록 1건" in previous
    assert "전날에만 한 일" not in previous  # 홈은 제목이 아니라 주제로 묶는다
    assert "connection pool" in previous
    assert 'href="/t?date=2026-08-22"' in previous
    assert 'href="/t?date=2026-08-24"' in previous


def test_홈의_잘못된_날짜는_400이다(client):
    assert client.get("/t?date=2026-02-30").status_code == 400


# ── 지난 주제 ────────────────────────────────────────────────────────────
#
# 처음 이 화면을 오늘로 자른 전제는 "하루가 끝나는 시점에 열어본다" 였다.
# 바탕화면 실행 파일이 생기면서 그 전제가 깨졌다 — 기록하지 않은 날에도 이
# 화면을 연다. 그때 화면이 비어 있으면 **들어가는 문이 가진 것을 숨기는 것**이다.


def test_오늘_기록이_없어도_지난_주제가_보인다(client):
    """실제로 부딪힌 결함이다. DB 에 주제가 셋 있는데 화면은 비어 있었다."""
    _record(client, "rec_A", occurred_at="2026-08-20T09:00:00.000Z")
    page = client.get("/t").text
    assert "오늘 기록 0건" in page      # 오늘 신호는 그대로 남는다
    assert "connection pool" in page    # 그러나 가진 것을 숨기지 않는다


def test_지난_주제는_최근순이다(client):
    """오늘 만지지 않은 주제라면 '얼마나 많이' 보다 '언제가 마지막이었나' 다."""
    _record(client, "rec_옛날_1", topic="jvm gc", occurred_at="2026-08-10T09:00:00.000Z")
    _record(client, "rec_옛날_2", topic="jvm gc", occurred_at="2026-08-10T10:00:00.000Z")
    _record(client, "rec_최근", topic="net tcp", occurred_at="2026-08-22T09:00:00.000Z")
    지난 = client.get("/t").text.split("지난 주제")[1]
    # 건수는 jvm gc 가 많지만(2건) 최근인 net tcp 가 앞이다.
    assert 지난.index("net tcp") < 지난.index("jvm gc")


def test_오늘_주제는_지난_주제에_다시_나오지_않는다(client):
    """같은 주제가 두 구획에 겹쳐 보이면 건수가 두 배로 읽힌다."""
    _record(client, "rec_어제", occurred_at="2026-08-23T09:00:00.000Z")
    _record(client, "rec_오늘", occurred_at="2026-08-24T09:00:00.000Z")
    page = client.get("/t").text
    assert "connection pool" in page.split("지난 주제")[0]
    assert "지난 주제" not in page      # 겹치는 주제뿐이면 구획 자체가 없다


def test_지난_주제의_건수는_전체다(client):
    """구획은 '오늘이 아닌 주제' 로 가르지만, 건수까지 자르지는 않는다.

    `/t/{slug}` 가 보여주는 것도 그 주제의 전체 기록이다. 두 화면이 다른
    숫자를 말하면 어느 쪽을 믿을지 모르게 된다.
    """
    for i in range(3):
        _record(client, f"rec_{i}", topic="jvm gc",
                occurred_at=f"2026-08-2{i}T09:00:00.000Z")
    지난 = client.get("/t").text.split("지난 주제")[1]
    assert "3건" in 지난


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


def test_nav_로_날짜_화면과_오갈_수_있다(client):
    _record(client, "rec_A")
    for path in ("/t", "/t/connection-pool"):
        page = client.get(path).text
        assert "<nav>" in page
        assert 'href="/d/2026-08-24"' in page
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

def test_주제_목록이_재료가_얼마나_찼는지_보여준다(client):
    """이 화면의 질문은 '오늘 뭘 글로 쓸 수 있나' 다.
    건수만으로는 답이 안 나온다 — 3건이어도 재료가 비면 못 쓴다.
    """
    _record(client, "rec_A", rationale="골랐다", outcome="p95 90ms")
    _record(client, "rec_B")
    page = client.get("/t").text
    assert 'class="gauge"' in page
    assert "재료" in page


def test_막대는_주제마다_네_칸이다(client):
    """칸 수가 주제마다 다르면 눈으로 비교가 안 된다."""
    _record(client, "rec_A", rationale="골랐다")
    _record(client, "rec_B")
    page = client.get("/t").text
    assert page.count('class="seg') == 4


def test_상세도_같은_막대를_쓴다(client):
    _record(client, "rec_A", rationale="골랐다")
    assert 'class="gauge"' in client.get("/t/connection-pool").text


def test_지난_주제도_막대를_가진다(client):
    """지난 주제야말로 '이걸 글로 쓸 수 있나' 를 묻는 자리다.
    막대가 없으면 건수만 보고 눌러야 한다.
    """
    _record(client, "rec_A", occurred_at="2026-08-20T09:00:00.000Z",
            rationale="골랐다")
    지난 = client.get("/t").text.split("지난 주제")[1]
    assert 'class="gauge"' in 지난
    assert 지난.count('class="seg') == 4


def test_막대는_하루치가_아니라_주제_전체를_센다(client):
    """초안 조립기는 그 주제의 기록을 **전부** 재료로 쓴다.

    하루로 자르면 어제 채운 rationale 이 오늘 빈칸으로 보이고, 같은 주제인데
    `/t` 와 `/t/{slug}` 가 다른 막대를 그린다.
    """
    _record(client, "rec_어제", occurred_at="2026-08-23T09:00:00.000Z",
            rationale="골랐다")
    # 오늘 2건이어야 '미분류' 가 아니라 본 구획에 앉아 막대가 그려진다.
    _record(client, "rec_오늘_1", occurred_at="2026-08-24T09:00:00.000Z")
    _record(client, "rec_오늘_2", occurred_at="2026-08-24T10:00:00.000Z")

    오늘 = client.get("/t").text.split("지난 주제")[0]
    상세 = client.get("/t/connection-pool").text

    # 오늘치만 세면 rationale 이 빈칸이라 '재료 0/4' 가 된다.
    assert "재료 1/4" in 오늘
    # 두 화면이 같은 막대를 그린다. 이 둘이 갈리는 것이 원래 문제였다.
    assert "재료 1/4" in 상세
    # 채움 너비도 3건 중 1건이다 — 분모가 하루치(2건)면 0% 로 보인다.
    assert "width: 33%" in 오늘


# ── 면접 문장은 학습 화면에만 (2026-08-25) ──────────────────────────

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
    paste = page.split("<textarea", 1)[1].split("</textarea>")[0]
    assert "이렇게 말합니다" not in paste


def test_발행_본문에_내부_식별자가_없다(client):
    """꼬리말은 정본 파일에 남고 붙여넣기용에서는 빠진다."""
    _record(client, "rec_A")
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()
    page = client.get(f"/drafts/{draft['draft_id']}").text
    paste = page.split("<textarea", 1)[1].split("</textarea>")[0]
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
