"""주제 화면 `/t` — 하루치 기록이 주제로 묶여 한 줄이 된다.

Jinja2 서버 렌더링, JavaScript 없음. 조회는 토큰이 필요 없다.
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
    """UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다."""
    # KST 2026-08-24 00:30 = UTC 2026-08-23 15:30
    _record(client, "rec_오늘새벽", occurred_at="2026-08-23T15:30:00.000Z")
    # KST 2026-08-23 23:30 = UTC 2026-08-23 14:30
    _record(client, "rec_어제밤", topic="jvm gc",
            occurred_at="2026-08-23T14:30:00.000Z")
    page = client.get("/t").text
    assert "connection pool" in page
    assert "jvm gc" not in page


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


def test_초안_만들기는_아직_동작하지_않는다고_밝힌다(client):
    """자리만 만든다(Task 8 에서 붙는다). 눌러도 아무 일이 없으면
    고장난 것으로 오해한다.
    """
    _record(client, "rec_A")
    page = client.get("/t/connection-pool").text
    assert "준비 중" in page


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
