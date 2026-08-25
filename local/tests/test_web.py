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


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _seed(client, work_id="wrk_A", tool="codex", title="작업 제목"):
    payload = dict(COMMON, tool=tool)
    client.post("/v1/works", json={"work_id": work_id, "title": title, **payload})
    client.post(
        "/v1/checkpoints",
        json={
            "checkpoint_id": f"ckp_{work_id}",
            "work_id": work_id,
            "type": "FAILED_ATTEMPT",
            "title": "체크포인트 제목",
            "body": "첫 줄\n둘째 줄",
            **payload,
        },
    )


def test_루트는_오늘로_보낸다(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == f"/d/{TODAY}"


def test_날짜_화면이_열린다(client):
    response = client.get(f"/d/{TODAY}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_작업_제목과_상태가_보인다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "작업 제목" in body
    assert "ACTIVE" in body


def test_도구별로_묶여_보인다(client):
    _seed(client, work_id="wrk_A", tool="codex")
    _seed(client, work_id="wrk_B", tool="claude-code")
    body = client.get(f"/d/{TODAY}").text
    assert "codex" in body
    assert "claude-code" in body


def test_체크포인트_유형과_제목이_보인다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "FAILED_ATTEMPT" in body
    assert "체크포인트 제목" in body


def test_본문의_줄바꿈이_보존된다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "첫 줄\n둘째 줄" in body


def test_기록이_없는_날짜는_비어_있다고_알린다(client):
    body = client.get("/d/2020-01-01").text
    assert "기록이 없습니다" in body


def test_기록이_없으면_최근_날짜_링크를_준다(client):
    _seed(client)
    body = client.get("/d/2030-01-01").text
    assert f"/d/{TODAY}" in body


def test_이전과_다음_날짜_링크가_있다(client):
    body = client.get("/d/2026-07-22").text
    assert "/d/2026-07-21" in body
    assert "/d/2026-07-23" in body


def test_Git_정보가_없으면_없다고_표시한다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "Git 정보 없음" in body


def test_잘못된_날짜_형식은_400_이다(client):
    assert client.get("/d/2026-7-22").status_code == 400


def test_화면은_외부_주소를_불러오지_않는다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "http://" not in body.replace('http://127.0.0.1', '')
    assert "https://" not in body


# ── 학습 기록 섹션 (Task 11) ───────────────────────────────────────

def test_날짜_화면에_그날의_학습_기록이_보인다(client, home):
    """작업·체크포인트와 학습 기록은 성격이 다르지만 같은 하루에 속한다.

    날짜 화면은 '그날 무엇을 했나' 를 보는 자리라 둘 다 있어야 한다.
    """
    client.post("/v1/records", json={
        "record_id": "rec_A", "client_instance_id": CLIENT, "tool": "codex",
        "kind": "EXPERIMENT", "topic": "connection pool",
        "title": "풀 크기 10→30", "body": "p95 320ms→90ms",
        "occurred_at": "2026-07-22T09:00:00.000Z",
    })
    page = client.get("/d/2026-07-22").text
    assert "학습 기록" in page
    assert "풀 크기 10→30" in page
    assert 'href="/t/connection-pool"' in page


def test_학습_기록이_없는_날에는_그_섹션이_없다(client):
    assert "학습 기록" not in client.get("/d/2026-07-22").text


def test_다른_날_학습_기록은_안_보인다(client):
    client.post("/v1/records", json={
        "record_id": "rec_A", "client_instance_id": CLIENT, "tool": "codex",
        "kind": "EXPERIMENT", "topic": "connection pool",
        "title": "어제 것", "body": "본문",
        "occurred_at": "2026-07-21T09:00:00.000Z",
    })
    assert "어제 것" not in client.get("/d/2026-07-22").text
