from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock, local_date_of
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
TODAY = local_date_of("2026-07-22T08:00:00.000Z")
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}
WORK = "wrk_A"
CKP = "ckp_wrk_A"


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        made.token = settings.token
        yield made


@pytest.fixture
def seeded(client):
    client.post("/v1/works", json={"work_id": WORK, "title": "작업 제목", **COMMON})
    client.post(
        "/v1/checkpoints",
        json={"checkpoint_id": CKP, "work_id": WORK, "type": "NOTE",
              "title": "체크포인트 제목", "body": "본문", **COMMON},
    )
    return client


def _form(client, extra=None):
    data = {"_token": client.token, "date": TODAY}
    data.update(extra or {})
    return data


def test_체크포인트를_삭제하면_화면에서_사라진다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    assert "체크포인트 제목" not in seeded.get(f"/d/{TODAY}").text


def test_삭제하면_날짜_화면으로_돌려보낸다(seeded):
    response = seeded.post(
        f"/web/checkpoints/{CKP}/delete", data=_form(seeded), follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == f"/d/{TODAY}"


def test_삭제한_체크포인트는_삭제_목록에_나온다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}?deleted=1").text


def test_체크포인트를_복구하면_다시_보인다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    seeded.post(f"/web/checkpoints/{CKP}/restore", data=_form(seeded))
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}").text


def test_세션을_삭제하면_하위_체크포인트도_사라진다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}").text
    assert "작업 제목" not in body
    assert "체크포인트 제목" not in body


def test_세션을_복구하면_하위_체크포인트도_돌아온다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    seeded.post(f"/web/works/{WORK}/restore", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}").text
    assert "작업 제목" in body
    assert "체크포인트 제목" in body


def test_삭제한_기록은_맥락_조회에_안_나온다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    payload = seeded.get("/v1/context", params={"date": TODAY}).json()
    assert payload["works"] == []


def test_토큰이_없으면_401_이다(seeded):
    response = seeded.post(
        f"/web/checkpoints/{CKP}/delete", data={"date": TODAY}
    )
    assert response.status_code == 401


def test_토큰이_틀리면_401_이고_삭제되지_않는다(seeded):
    seeded.post(
        f"/web/checkpoints/{CKP}/delete",
        data={"_token": "틀린값", "date": TODAY},
    )
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}").text


def test_삭제_화면에_복구_버튼이_있다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}?deleted=1").text
    assert "/restore" in body
    assert "복구" in body


def test_삭제_항목이_없으면_비어_있다고_알린다(client):
    assert "삭제한 기록이 없습니다" in client.get(f"/d/{TODAY}?deleted=1").text
