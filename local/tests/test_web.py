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
    # 주제로 가는 길은 **제목**이다. 종전에는 제목 아래 주제 이름이
    # 링크였는데, 눈이 먼저 가는 것은 제목이고 보고 싶은 것은
    # '그래서 무슨 이슈였나' 라 자리를 바꿨다(2026-08-25).
    # 이제 주제 이름은 체크박스를 켜는 라벨이다.
    assert 'href="/t/connection-pool#rec_A"' in page


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


# ── 제목 링크 · 체크박스 (사용자 요청 2026-08-25) ────────────────────

def _학습기록(client, record_id="rec_A", **extra):
    body = {"record_id": record_id, "kind": "CONCEPT", "topic": "connection pool",
            "title": "무엇을 알게 됐나", "body": "본문", **COMMON}
    body.update(extra)
    return client.post("/v1/records", json=body)


def test_제목을_눌러_그_기록으로_간다(client):
    """종전에는 아래 주제 이름만 눌렸다. 눈이 먼저 가는 것은 제목이고,
    보고 싶은 것은 '그래서 무슨 이슈였나' 다.
    """
    _학습기록(client)
    page = client.get(f"/d/{TODAY}").text
    assert 'href="/t/connection-pool#rec_A"' in page


def test_주제_상세에_기록마다_닻이_있다(client):
    """제목 링크가 데려다 놓을 자리가 없으면 목록 맨 위로만 간다."""
    _학습기록(client)
    assert 'id="rec_A"' in client.get("/t/connection-pool").text


def test_기록마다_체크박스가_있다(client):
    _학습기록(client, "rec_A")
    _학습기록(client, "rec_B", title="둘째")
    page = client.get(f"/d/{TODAY}").text
    assert page.count('name="record_id"') == 2
    assert 'value="rec_A"' in page
    assert 'value="rec_B"' in page


def test_고른_기록으로_초안을_만든다(client):
    _학습기록(client, "rec_A", title="첫째", body="첫째 본문")
    _학습기록(client, "rec_B", title="둘째", body="둘째 본문")
    made = client.post(
        "/web/drafts/from-records",
        data={"_token": client.app.state.ctx.settings.token, "record_id": ["rec_A"]},
        follow_redirects=False,
    )
    assert made.status_code == 302
    assert "/drafts/" in made.headers["location"]
    draft_id = made.headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/drafts/{draft_id}").text
    assert "첫째 본문" in page
    assert "둘째 본문" not in page


def test_아무것도_안_고르면_날짜_화면으로_돌려보낸다(client):
    """빈 초안을 만들지 않는다. 오류 화면 대신 하던 자리로 돌려보낸다."""
    _학습기록(client)
    back = client.post(
        "/web/drafts/from-records",
        data={"_token": client.app.state.ctx.settings.token, "date": TODAY},
        follow_redirects=False,
    )
    assert back.status_code == 302
    assert back.headers["location"] == f"/d/{TODAY}"


def test_초안_만들기도_토큰을_요구한다(client):
    _학습기록(client)
    assert client.post("/web/drafts/from-records",
                       data={"record_id": ["rec_A"]}).status_code == 401


def test_모든_화면이_내용을_한_컨테이너에_담는다(client, home):
    """가운데 정렬을 `body > *` 에 걸면 조용히 깨진다.

    직계 자식이 `margin` **단축**을 쓰는 순간 `margin-inline: auto` 가 0 으로
    덮여 그 요소만 왼쪽에 붙는다. 실제로 `/t/{slug}` 의 기록 목록이
    그렇게 됐다 — 위아래는 가운데인데 목록만 왼쪽이었다(2026-08-25 실측).
    폭은 그대로라 눈치채기도 어렵다.

    그래서 컨테이너 하나에 담는다. 안쪽에서 무슨 margin 을 쓰든 상관없다.
    """
    _seed(client)
    client.post("/v1/records", json={
        "record_id": "rec_M", "kind": "CONCEPT", "topic": "connection pool",
        "title": "제목", "body": "본문", **COMMON,
    })
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()

    for path in (f"/d/{TODAY}", f"/d/{TODAY}?deleted=1", "/t",
                 "/t/connection-pool", f"/c/{TODAY[:7]}",
                 f"/drafts/{draft['draft_id']}"):
        page = client.get(path).text
        assert "<main>" in page, path
        assert "</main>" in page, path


def test_모든_화면에서_주제_홈으로_돌아갈_수_있다(client, home):
    """세부 화면에 들어가도 주소를 고치지 않고 시작 화면으로 돌아간다."""
    _seed(client)
    client.post("/v1/records", json={
        "record_id": "rec_H", "kind": "CONCEPT", "topic": "connection pool",
        "title": "홈 버튼", "body": "본문", **COMMON,
    })
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()

    for path in (f"/d/{TODAY}", f"/d/{TODAY}?deleted=1", "/t",
                 "/t/connection-pool", f"/c/{TODAY[:7]}",
                 f"/drafts/{draft['draft_id']}"):
        page = client.get(path).text
        assert 'class="home-link" href="/t"' in page, path
        assert 'aria-label="홈으로"' in page, path


def test_모든_화면에서_일반_다크_모드를_바꿀_수_있다(client, home):
    """화면을 옮겨도 브라우저에 저장한 테마를 같은 토글로 바꾼다."""
    _seed(client)
    client.post("/v1/records", json={
        "record_id": "rec_T", "kind": "CONCEPT", "topic": "connection pool",
        "title": "테마 토글", "body": "본문", **COMMON,
    })
    draft = client.post("/v1/drafts", json={"topic_slug": "connection-pool"}).json()

    for path in (f"/d/{TODAY}", f"/d/{TODAY}?deleted=1", "/t",
                 "/t/connection-pool", f"/c/{TODAY[:7]}",
                 f"/drafts/{draft['draft_id']}"):
        page = client.get(path).text
        assert 'class="theme-toggle"' in page, path
        assert 'data-theme-toggle' in page, path

    base = client.get("/t").text
    assert '[data-theme="dark"]' in base
    assert 'localStorage.getItem("warruru-theme")' in base
    assert 'localStorage.setItem("warruru-theme", next)' in base


def test_고른_적_없으면_운영체제_설정을_따른다(client, home):
    """저장값이 없을 때만 시스템을 본다. 한 번 고르면 그 선택이 이긴다."""
    base = client.get("/t").text

    # CSS 앞에서 정해야 첫 그림에 흰 화면이 안 낀다.
    head = base.split("<style>", 1)[0]
    assert '(prefers-color-scheme: dark)' in head
    assert 'savedTheme !== "light" && prefersDark' in head

    # 켜 둔 채로 시스템이 밤 모드로 넘어가도 따라간다.
    assert 'media.addEventListener' in base
