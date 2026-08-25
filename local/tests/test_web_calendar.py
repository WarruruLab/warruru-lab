"""달력 `/c/{YYYY-MM}`. 기록이 있는 날이 어디인지 달 단위로 보인다.

달력이 표시하는 것은 **날짜 화면에 무언가 있는 날**이다. 학습 기록만
세면, 작업 세션 5개가 있는 날이 빈칸으로 보이고 사용자는 그 날을
누르지 않는다. 달력의 유일한 일이 '어디를 누를지 고르는 것'이므로
그 거짓 빈칸은 기능 전체를 무력화한다.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _record(client, record_id, occurred_at, topic="connection pool"):
    return client.post("/v1/records", json={
        "record_id": record_id, "client_instance_id": CLIENT, "tool": "codex",
        "kind": "CONCEPT", "topic": topic, "title": "제목", "body": "본문",
        "occurred_at": occurred_at,
    })


def test_기록_있는_날만_진하게_칠해진다(client):
    _record(client, "rec_A", "2026-07-22T09:00:00.000Z")
    _record(client, "rec_B", "2026-07-22T10:00:00.000Z")
    view = client.get("/c/2026-07").text
    assert 'href="/d/2026-07-22"' in view
    # 같은 달의 기록 없는 날은 링크가 아니다.
    assert 'href="/d/2026-07-23"' not in view


def test_작업만_있는_날도_칠해진다(client):
    """학습 기록만 세면 작업 세션뿐인 날이 빈칸으로 보인다."""
    client.post("/v1/works", json={
        "work_id": "wrk_A", "title": "작업", "client_instance_id": CLIENT,
        "tool": "codex", "cwd": None,
    })
    assert 'href="/d/2026-07-22"' in client.get("/c/2026-07").text


def test_빈_달도_격자가_그려진다(client):
    view = client.get("/c/2026-09").text
    assert view.count("<td") >= 28
    assert 'href="/d/2026-09-' not in view


def test_날짜를_누르면_날짜_화면으로_간다(client):
    _record(client, "rec_A", "2026-07-22T09:00:00.000Z")
    assert client.get("/d/2026-07-22").status_code == 200


def test_달_경계는_로컬_자정_기준이다(client):
    """KST 기준 7월 1일 오전 9시 이전은 UTC 로 6월 30일이다.

    문자열을 직접 이어 `2026-07-01T00:00:00Z` 로 자르면 그 기록이
    통째로 6월로 샌다. local_day_bounds 만 쓴다.
    """
    _record(client, "rec_A", "2026-07-01T00:30:00.000Z")   # KST 07-01 09:30
    _record(client, "rec_B", "2026-06-30T23:30:00.000Z")   # KST 07-01 08:30
    view = client.get("/c/2026-07").text
    assert 'href="/d/2026-07-01"' in view
    assert 'href="/d/2026-06-30"' not in view


def test_한_달_전체가_한_번의_질의로_나온다(client):
    """날마다 질의하면 31번이다. 달 전체를 한 구간으로 훑는다."""
    from warruru_local.daemon import calendarview
    assert hasattr(calendarview, "build_month")


def test_잘못된_YYYY_MM_은_400(client):
    assert client.get("/c/2026-7").status_code == 400
    assert client.get("/c/2026-13").status_code == 400
    assert client.get("/c/26-07").status_code == 400


def test_앞뒤_달로_넘어갈_수_있다(client):
    view = client.get("/c/2026-01").text
    assert 'href="/c/2025-12"' in view
    assert 'href="/c/2026-02"' in view


def test_주제_화면에서_달력으로_갈_수_있다(client):
    """달력에 길이 없으면 주소를 외워야 열린다."""
    assert 'href="/c/' in client.get("/t").text
