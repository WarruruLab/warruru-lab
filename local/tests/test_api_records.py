"""`POST /v1/records` · `GET /v1/records` — 라우트는 얇고 판단은 아래에 있다."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 8, 18, 9, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _body(**extra):
    values = {
        "record_id": "rec_A",
        "client_instance_id": CLIENT,
        "tool": "codex",
        "kind": "EXPERIMENT",
        "topic": "connection pool",
        "title": "풀 크기 10→30",
        "body": "p95 320ms→90ms",
    }
    values.update(extra)
    return values


def test_토큰이_없으면_401(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        assert bare.post("/v1/records", json=_body()).status_code == 401


def test_기록하면_record_id_와_topic_slug_가_온다(client):
    payload = client.post("/v1/records", json=_body()).json()
    assert payload["record_id"] == "rec_A"
    assert payload["topic_slug"] == "connection-pool"
    assert payload["work_id"].startswith("wrk_")


def test_결손_필드와_예시가_함께_온다(client):
    payload = client.post("/v1/records", json=_body()).json()
    assert "outcome" in payload["missing_fields"]
    assert "record_learning(" in payload["example_call"]


def test_필수_필드가_공백뿐이어도_거절하지_않는다(client):
    """거절은 '기록 안 하기'를 가장 안전한 선택으로 만든다 (명세 §4.1).

    대신 결손으로 보고해 에이전트가 곧바로 채우게 한다.
    """
    response = client.post("/v1/records", json=_body(title="   "))
    assert response.status_code == 200
    assert "title" in response.json()["missing_fields"]


def test_같은_record_id_는_한_건이다(client):
    client.post("/v1/records", json=_body())
    client.post("/v1/records", json=_body(title="나중"))
    assert len(client.get("/v1/records").json()["records"]) == 1


def test_목록을_돌려준다(client):
    client.post("/v1/records", json=_body())
    payload = client.get("/v1/records").json()
    assert [r["record_id"] for r in payload["records"]] == ["rec_A"]


def test_topic_slug_로_거른다(client):
    client.post("/v1/records", json=_body())
    client.post("/v1/records", json=_body(record_id="rec_B", topic="jvm gc"))
    found = client.get("/v1/records", params={"topic_slug": "jvm-gc"}).json()
    assert [r["record_id"] for r in found["records"]] == ["rec_B"]


def test_잘못된_날짜_파라미터는_400(client):
    assert client.get("/v1/records", params={"since": "어제"}).status_code == 400
    assert client.get("/v1/records", params={"until": "2026-13-40"}).status_code == 400


def test_until_은_그날을_포함한다(client):
    """'8월 18일까지' 라고 적은 사람은 18일 기록을 보고 싶어 한다."""
    client.post("/v1/records", json=_body(occurred_at="2026-08-18T14:00:00.000Z"))
    found = client.get(
        "/v1/records", params={"since": "2026-08-18", "until": "2026-08-18"}
    ).json()
    assert [r["record_id"] for r in found["records"]] == ["rec_A"]


def test_그_다음날은_안_들어온다(client):
    client.post("/v1/records", json=_body(occurred_at="2026-08-19T14:00:00.000Z"))
    found = client.get(
        "/v1/records", params={"since": "2026-08-18", "until": "2026-08-18"}
    ).json()
    assert found["records"] == []


def test_limit_을_넘겨도_상한에서_잘린다(client):
    for i in range(3):
        client.post("/v1/records", json=_body(record_id=f"rec_{i}"))
    assert len(client.get("/v1/records", params={"limit": 2}).json()["records"]) == 2


def test_사람이_읽는_주제로_걸러도_동작한다(client):
    """쓰기는 원문을 슬러그로 바꾸는데 읽기만 정확한 슬러그를 요구하면,
    빈 목록이 돌아오고 왜 비었는지 알 방법이 없다.
    """
    client.post("/v1/records", json=_body())
    found = client.get("/v1/records", params={"topic_slug": "Connection Pool"}).json()
    assert [r["record_id"] for r in found["records"]] == ["rec_A"]


def test_같은_기록을_다시_보내면_빈칸이_채워진다(client):
    """힌트가 '다시 불러 채우라' 고 말하는 그 경로다."""
    client.post("/v1/records", json=_body())
    payload = client.post("/v1/records", json=_body(outcome="p95 가 90ms")).json()
    assert payload["duplicate"] is True
    assert payload["filled_fields"] == ["outcome"]
    assert "outcome" not in payload["missing_fields"]
