from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock, local_date_of, local_day_bounds
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _seed(client, work_id="wrk_A", tool="codex"):
    payload = dict(COMMON, tool=tool)
    client.post("/v1/works", json={"work_id": work_id, "title": "제목", **payload})
    for index, kind in enumerate(["PROBLEM", "ATTEMPT", "ATTEMPT", "RESULT"]):
        client.post(
            "/v1/checkpoints",
            json={
                "checkpoint_id": f"ckp_{work_id}_{index}",
                "work_id": work_id,
                "type": kind,
                "title": f"{kind} 제목",
                **payload,
            },
        )


def test_하루_경계는_로컬_시간대를_따른다():
    start, end = local_day_bounds("2026-07-22")
    assert local_date_of(start) == "2026-07-22"
    assert local_date_of(end) == "2026-07-23"
    assert start < end


def test_날짜_형식이_잘못되면_INVALID_REQUEST_400_이다(client):
    response = client.get("/v1/context", params={"date": "그저께"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_숫자만_있어도_자릿수가_안_맞으면_INVALID_REQUEST_400_이다(client):
    response = client.get("/v1/context", params={"date": "2026-7-22"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_입력과_무관한_ValueError는_STORAGE_ERROR_500_이다(client, monkeypatch):
    """저장소 계층에서 난 ValueError 를 잘못된 날짜 입력으로 오인해서는 안 된다."""

    def _boom(*args, **kwargs):
        raise ValueError("예상치 못한 저장소 오류")

    monkeypatch.setattr(client.app.state.ctx.repo, "list_works_between", _boom)
    # 앱이 등록한 500 핸들러가 실제로 응답을 만드는지 보려면 TestClient 가
    # 예외를 그대로 다시 던지지 않게 해야 한다(기본값은 디버깅을 돕기 위해
    # 서버 예외를 호출자 쪽으로 재전파한다).
    no_raise = TestClient(client.app, raise_server_exceptions=False)
    no_raise.headers.update(client.headers)
    response = no_raise.get("/v1/context", params={"date": "2026-07-22"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "STORAGE_ERROR"


def test_기록이_없으면_빈_목록과_안내를_준다(client):
    body = client.get("/v1/context", params={"date": "2020-01-01"}).json()
    assert body["works"] == []
    assert "기록 없음" in body["summary_markdown"]


def test_그_날짜의_작업을_준다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get("/v1/context", params={"date": today}).json()
    assert [work["work_id"] for work in body["works"]] == ["wrk_A"]


def test_유형별_개수를_센다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    work = client.get("/v1/context", params={"date": today}).json()["works"][0]
    assert work["type_counts"] == {"PROBLEM": 1, "ATTEMPT": 2, "RESULT": 1}


def test_최근_체크포인트는_다섯_개까지다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    work = client.get("/v1/context", params={"date": today}).json()["works"][0]
    assert len(work["recent_checkpoints"]) <= 5
    assert set(work["recent_checkpoints"][0]) == {"type", "title", "occurred_at"}


def test_본문은_담지_않는다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get("/v1/context", params={"date": today}).text
    assert "본문" not in body


def test_도구로_거를_수_있다(client):
    _seed(client, work_id="wrk_A", tool="codex")
    _seed(client, work_id="wrk_B", tool="claude-code")
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get(
        "/v1/context", params={"date": today, "tool": "claude-code"}
    ).json()
    assert [work["work_id"] for work in body["works"]] == ["wrk_B"]


def test_상한을_넘기면_30개로_묶는다(client):
    today = local_date_of("2026-07-22T08:00:00.000Z")
    response = client.get("/v1/context", params={"date": today, "limit": 999})
    assert response.status_code == 200


def test_날짜를_빼면_오늘을_쓴다(client):
    _seed(client)
    body = client.get("/v1/context").json()
    assert body["date"] == local_date_of("2026-07-22T08:00:00.000Z")


def test_요약에_제목과_상태가_들어간다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    summary = client.get("/v1/context", params={"date": today}).json()[
        "summary_markdown"
    ]
    assert "제목" in summary
    assert "codex" in summary
