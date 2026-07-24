from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def test_health_는_토큰_없이도_열린다(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_는_스키마_버전과_머신을_알린다(client):
    payload = client.get("/v1/health").json()
    assert payload["schema_version"] == 1
    assert payload["machine_id"].startswith("mch_")
    assert payload["version"] == "0.1.0"


def test_토큰이_없으면_401_이다(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.post("/v1/works", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_토큰이_틀리면_401_이다(home):
    # httpx>=0.28 은 헤더 값을 ascii 로만 인코딩한다. 값 자체는 무엇이든
    # 상관없으니(그저 기대 토큰과 달라야 한다) ascii 문자열을 쓴다.
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.post(
            "/v1/works", json={}, headers={"X-Warruru-Token": "wrong-token"}
        )
    assert response.status_code == 401


def test_기동하면_머신_행이_생긴다(client):
    machine_id = client.get("/v1/health").json()["machine_id"]
    row = client.app.state.ctx.repo._conn.execute(  # noqa: SLF001
        "SELECT * FROM machine WHERE machine_id = ?", (machine_id,)
    ).fetchone()
    assert row is not None
