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


def test_학습_기록만_있는_날에_없다고_말하지_않는다(client):
    """작업은 흡수한 날에 붙고 기록은 occurred_at 에 붙는다.

    데몬이 꺼진 채 어제 남긴 기록이 오늘 흡수되면, 어제 화면에는 기록만
    있고 작업은 없다(OUTSTANDING I4 — 받아들인 결함). 그때 '기록이
    없습니다' 를 기록 바로 아래 띄우면 화면이 스스로 모순된다.
    """
    client.post("/v1/records", json={
        "record_id": "rec_A", "client_instance_id": CLIENT, "tool": "codex",
        "kind": "CONCEPT", "topic": "connection pool",
        "title": "어제 남긴 기록", "body": "본문",
        "occurred_at": "2026-07-21T09:00:00.000Z",
    })
    page = client.get("/d/2026-07-21").text
    assert "어제 남긴 기록" in page
    assert "이 날짜에는 기록이 없습니다" not in page


# ── 불량 시각에 대한 내성 (OUTSTANDING I2) ─────────────────────────

def test_잘못된_occurred_at_은_현재_시각으로_대체된다(client):
    """`occurred_at` 은 에이전트에 노출되고 문자열로만 타입돼 있다.

    검증 없이 저장하면 잘못된 값 하나가 그 날짜 화면을 영구히 500 으로
    만든다. 삭제 폼이 그 화면 안에 있으므로 UI 로는 복구할 수 없다.
    기록을 거절하지 않기로 했으므로, 거절 대신 대체한다.
    """
    _seed(client)
    client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_BAD", "work_id": "wrk_A", "type": "NOTE",
        "title": "시각이 이상한 기록", "occurred_at": "어제 오후",
        **COMMON,
    })
    page = client.get(f"/d/{TODAY}")
    assert page.status_code == 200
    assert "시각이 이상한 기록" in page.text


def test_잘못된_started_at_도_대체된다(client):
    """`finish_work` 가 started_at 을 parse_iso 로 다시 읽는다.
    여기서 통과시키면 마감이 500 이 되고 그 작업은 영영 못 닫는다.
    """
    client.post("/v1/works", json={
        "work_id": "wrk_BAD", "title": "시작이 이상한 작업",
        "started_at": "언젠가", **COMMON,
    })
    assert client.get(f"/d/{TODAY}").status_code == 200
    done = client.post("/v1/works/wrk_BAD/finish", json={**COMMON})
    assert done.status_code == 200
    assert done.json()["duration_seconds"] >= 0


def test_이미_저장된_불량_시각이_있어도_화면이_뜬다(client, home):
    """대체는 앞으로 들어올 값만 막는다. 이미 들어간 행은 그대로 있다.

    그 행 하나 때문에 화면 전체가 500 이면 지울 수도 없다 —
    삭제 폼이 그 화면 안에 있다.
    """
    import sqlite3

    _seed(client)
    conn = sqlite3.connect(home / "warruru.db")
    conn.execute(
        "UPDATE checkpoint SET occurred_at = ? WHERE checkpoint_id = ?",
        ("망가진값", "ckp_wrk_A"),
    )
    conn.commit()
    conn.close()

    page = client.get(f"/d/{TODAY}")
    assert page.status_code == 200
    assert "체크포인트 제목" in page.text


def _망가뜨린다(home, table, column, key_column, key):
    import sqlite3

    conn = sqlite3.connect(home / "warruru.db")
    conn.execute(
        f"UPDATE {table} SET {column} = ? WHERE {key_column} = ?", ("망가진값", key)
    )
    conn.commit()
    conn.close()


def test_불량_시각이_주제_화면을_무너뜨리지_않는다(client, home):
    client.post("/v1/records", json={
        "record_id": "rec_A", "kind": "CONCEPT", "topic": "connection pool",
        "title": "기록 제목", "body": "본문", **COMMON,
    })
    _망가뜨린다(home, "learning_record", "occurred_at", "record_id", "rec_A")
    assert client.get("/t").status_code == 200
    assert client.get("/t/connection-pool").status_code == 200


def test_불량_시각이_달력을_무너뜨리지_않는다(client, home):
    """구간 **안**에 드는 불량 값이어야 실제로 읽힌다.

    한글 값은 사전순으로 ISO 문자열 뒤라 구간 질의에 아예 안 잡힌다 —
    그걸로는 통과해도 아무것도 증명하지 못한다.
    """
    import sqlite3

    _seed(client)
    conn = sqlite3.connect(home / "warruru.db")
    conn.execute(
        "UPDATE work_session SET started_at = ? WHERE work_id = ?",
        (f"{TODAY}T99:99:99.999Z", "wrk_A"),
    )
    conn.commit()
    conn.close()
    assert client.get(f"/c/{TODAY[:7]}").status_code == 200


def test_불량_시각이_있어도_작업을_마감할_수_있다(client, home):
    """`finish_work` 가 started_at 을 다시 파싱한다.
    여기서 터지면 그 작업은 영영 못 닫고, 열린 채로 매일 화면에 남는다.
    """
    _seed(client)
    _망가뜨린다(home, "work_session", "started_at", "work_id", "wrk_A")
    done = client.post("/v1/works/wrk_A/finish", json={**COMMON})
    assert done.status_code == 200
    assert done.json()["duration_seconds"] == 0
