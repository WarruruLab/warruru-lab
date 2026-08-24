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
