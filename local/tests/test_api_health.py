from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app
from warruru_local.store import migrations

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
    assert payload["schema_version"] == migrations.CURRENT_VERSION
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


def test_health_는_상수가_아니라_실제_DB_버전을_보고한다(home, monkeypatch):
    """마이그레이션이 돌지 않은 DB 를 열면 health 가 그 사실을 말해야 한다.

    상수(`CURRENT_VERSION`)를 돌려주면 이 테스트가 통과할 수 없다 —
    마이그레이션을 통째로 막았는데도 최신 버전을 보고하게 되기 때문이다.
    구버전 바이너리가 더 높은 버전의 DB 를 여는 경우도 같은 이유로 안 보인다.
    """
    from warruru_local import paths
    from warruru_local.store import db

    settings = load_settings(home)
    paths.ensure_layout(home)
    conn = db.connect(paths.db_path(home))
    conn.executescript(migrations._V1)
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
        ("2026-07-22T08:00:00.000Z",),
    )
    conn.commit()
    conn.close()

    # 기동 중 마이그레이션을 막는다. DB 는 v1 에 머문다.
    monkeypatch.setattr(migrations, "migrate", lambda conn, now: 1)

    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        payload = made.get("/v1/health").json()

    assert payload["schema_version"] == 1
    # 상수였다면 위에서 최신 버전이 나왔을 것이다. 버전이 오를 때마다 이 줄을
    # 고쳐야 한다면 그건 테스트가 상수를 다시 베낀 것이다 — 비교만 한다.
    assert migrations.CURRENT_VERSION > 1


def test_스키마_버전이_어긋나면_경고를_남긴다(home, monkeypatch):
    """구버전 데몬이 새 DB 를 여는 상황은 조용히 지나가면 안 된다.

    데몬 로거는 `propagate = False` 라 caplog 로는 안 잡힌다. 직접 붙인다.
    """
    import logging

    from warruru_local import paths
    from warruru_local.store import db

    settings = load_settings(home)
    paths.ensure_layout(home)
    conn = db.connect(paths.db_path(home))
    conn.executescript(migrations._V1)
    conn.commit()
    conn.close()

    monkeypatch.setattr(migrations, "migrate", lambda conn, now: 1)

    messages: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    logger = logging.getLogger("warruru.daemon")
    handler = _Capture()
    logger.addHandler(handler)
    try:
        # 컨텍스트는 lifespan 에서 만들어진다. 앱만 만들면 아무 일도 일어나지 않는다.
        app = create_app(settings, clock=FixedClock(START), start_background=False)
        with TestClient(app):
            pass
    finally:
        logger.removeHandler(handler)

    assert any("스키마 버전" in message for message in messages)
