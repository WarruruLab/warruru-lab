from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"

COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _start(client, work_id=WORK, title="제목"):
    return client.post(
        "/v1/works",
        json={"work_id": work_id, "title": title, "goal": "목표", **COMMON},
    )


def _checkpoint(client, checkpoint_id=CKP, work_id=None, ckp_type="PROBLEM", **extra):
    payload = {
        "checkpoint_id": checkpoint_id,
        "work_id": work_id,
        "type": ckp_type,
        "title": "체크포인트 제목",
        "body": "본문",
        **COMMON,
        **extra,
    }
    return client.post("/v1/checkpoints", json=payload)


def test_작업을_시작하면_200_이고_식별자를_돌려준다(client):
    response = _start(client)
    assert response.status_code == 200
    body = response.json()
    assert body["work_id"] == WORK
    assert body["duplicate"] is False


def test_같은_식별자로_두_번_시작하면_중복이라고_알린다(client):
    _start(client, title="처음")
    body = _start(client, title="나중").json()
    assert body["duplicate"] is True
    assert body["title"] == "처음"


def test_체크포인트를_기록하면_귀속_경로를_알려준다(client):
    _start(client)
    body = _checkpoint(client, work_id=WORK).json()
    assert body["work_id"] == WORK
    assert body["attached_by"] == "REQUEST"
    assert body["work_origin"] == "EXPLICIT"


def test_식별자를_빼면_같은_대화의_작업에_붙는다(client):
    _start(client)
    body = _checkpoint(client).json()
    assert body["work_id"] == WORK
    assert body["attached_by"] == "CLIENT_INSTANCE"


def test_작업_없이_체크포인트만_보내도_저장된다(client):
    body = _checkpoint(client).json()
    assert body["attached_by"] == "NEW"
    assert body["work_origin"] == "INFERRED"


def test_자동_생성된_세션은_첫_체크포인트_제목을_물려받는다(client):
    work_id = _checkpoint(client).json()["work_id"]
    row = client.app.state.ctx.repo.get_work(work_id)
    assert row["title"] == "체크포인트 제목"
    assert row["title_origin"] == "DERIVED"


def test_모르는_식별자를_주면_그_식별자로_세션을_만든다(client):
    body = _checkpoint(client, work_id="wrk_늦게도착").json()
    assert body["work_id"] == "wrk_늦게도착"
    assert body["work_origin"] == "INFERRED"


def test_같은_체크포인트를_두_번_보내면_중복이라고_알린다(client):
    _checkpoint(client, ckp_type="PROBLEM")
    body = _checkpoint(client, ckp_type="RESULT").json()
    assert body["duplicate"] is True


def test_모르는_유형은_NOTE_로_바꾸고_태그에_남긴다(client):
    body = _checkpoint(client, ckp_type="THINKING").json()
    row = client.app.state.ctx.repo.get_checkpoint(CKP)
    assert row["type"] == "NOTE"
    assert "type:THINKING" in row["tags_json"]
    assert body["duplicate"] is False


def test_긴_본문은_자르고_잘림을_표시한다(client):
    _checkpoint(client, body="가" * 70000)
    row = client.app.state.ctx.repo.get_checkpoint(CKP)
    assert len(row["body"]) == 65536
    assert row["body_truncated"] == 1


def test_제목이_필수다(client):
    response = client.post(
        "/v1/checkpoints",
        json={"checkpoint_id": CKP, "type": "NOTE", **COMMON},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert "title" in body["error"]["detail"]["fields"]


def test_마감하면_결과가_남는다(client):
    _start(client)
    _checkpoint(client, work_id=WORK)
    body = client.post(
        f"/v1/works/{WORK}/finish",
        json={"result": "됐다", "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] == WORK
    assert body["checkpoint_count"] == 1
    assert body["duration_seconds"] == 0


def test_auto_로_마감하면_대화의_최근_작업을_고른다(client):
    _start(client)
    body = client.post(
        "/v1/works/auto/finish",
        json={"result": None, "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] == WORK


def test_마감할_작업이_없으면_200_이고_사유를_준다(client):
    body = client.post(
        "/v1/works/auto/finish",
        json={"result": None, "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] is None
    assert body["reason"] == "NO_ACTIVE_WORK"


def test_대화가_끝나면_진행중_작업이_자동_마감된다(client):
    _start(client)
    response = client.post(f"/v1/clients/{CLIENT}/closed")
    assert response.status_code == 200
    row = client.app.state.ctx.repo.get_work(WORK)
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "CLIENT_EXIT"


def test_없는_대화를_닫아도_200_이다(client):
    assert client.post("/v1/clients/cli_없음/closed").status_code == 200
