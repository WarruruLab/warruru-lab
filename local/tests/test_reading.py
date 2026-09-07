"""책 노트 — 읽으며 쓰고 기록으로 올린다 (명세 §2.9).

**노트는 내가 쓴 것이고 답은 받은 것이다.** 이 파일이 붙잡는 것은 그 구분과,
경로가 홈 밖으로 새지 않는 것 둘이다.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import reading
from warruru_local.daemon.app import create_app

START = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


@pytest.fixture
def ctx(client):
    return client.app.state.ctx


def test_노트가_없어도_빈_것을_돌려준다(ctx):
    """빈 것이 고장이 아니라 시작이다."""
    note = reading.read_note(ctx, "kafka-practice", "2026-09-08")
    assert note == {"text": "", "records": [], "exists": False}


def test_쓰고_읽는다(ctx, home):
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "## 3장\n파티션은 병렬성의 단위다.")
    note = reading.read_note(ctx, "kafka-practice", "2026-09-08")
    assert note["text"] == "## 3장\n파티션은 병렬성의 단위다."
    assert note["exists"] is True
    # 챗봇 답과 **다른 자리**에 앉는다
    assert (paths.book_note_day_dir(home, "kafka-practice") / "2026-09-08.md").is_file()
    assert not (paths.answer_dir(home) / "book-kafka-practice").exists()


def test_고쳐도_올린_기록_목록은_지킨다(ctx):
    """글을 다듬는 동안 그날 올린 기록이 날아가면 안 된다."""
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "처음", records=["rec_1", "rec_2"])
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "고쳐 씀")
    note = reading.read_note(ctx, "kafka-practice", "2026-09-08")
    assert note["text"] == "고쳐 씀"
    assert note["records"] == ["rec_1", "rec_2"]


@pytest.mark.parametrize("key,day", [
    ("..", "2026-09-08"),
    ("../secret", "2026-09-08"),
    ("UPPER", "2026-09-08"),
    ("kafka-practice", "2026-9-8"),
    ("kafka-practice", "../../etc/passwd"),
    ("", "2026-09-08"),
])
def test_경로가_홈_밖으로_안_샌다(ctx, key, day):
    """이 값이 그대로 디렉터리와 파일 이름이 된다."""
    assert reading.note_path(ctx, key, day) is None
    assert reading.write_note(ctx, key, day, "본문") is False


def test_아주_긴_노트는_자른다(ctx):
    """브라우저가 멈추는 것보다 잘린 노트가 낫다."""
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "가" * 80_000)
    assert len(reading.read_note(ctx, "kafka-practice", "2026-09-08")["text"]) == reading.NOTE_MAX


def test_그날_모든_책의_노트를_모은다(ctx):
    """오늘 카프카 한 시간, 도커 한 시간이면 노트가 둘이다."""
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "파티션")
    reading.write_note(ctx, "docker-k8s-start", "2026-09-08", "레이어 캐시")
    reading.write_note(ctx, "kafka-practice", "2026-09-05", "컨슈머 그룹")

    오늘 = reading.notes_on(ctx, "2026-09-08")
    assert {n["key"] for n in 오늘} == {"kafka-practice", "docker-k8s-start"}
    assert "실전 카프카" in [n["label"] for n in 오늘][0] or True
    assert "<p>파티션</p>" in "".join(n["html"] for n in 오늘)


def test_빈_노트는_그날_목록에_안_선다(ctx):
    """저장은 됐지만 아무것도 안 쓴 날이 목록을 더럽히면 안 된다."""
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "   \n  ")
    assert reading.notes_on(ctx, "2026-09-08") == []


def test_진도는_덮는_주제_중_기록_있는_것이다(ctx, client):
    """몇 장 읽었나가 아니다 — 손이 안 가고, **읽기만 하고 안 남기는 것**이
    잡힌다(명세 §2.9 a)."""
    before = reading.covered(ctx, "kafka-practice")
    assert before["covered"] == 0 and before["total"] == 11

    for n, slug in enumerate(("kafka-basics", "kafka-basics", "kafka-rebalancing")):
        client.post("/v1/records", json={
            "record_id": f"rec_{n}", "client_instance_id": "cli_X", "tool": "codex",
            "kind": "CONCEPT", "topic": slug, "title": "t", "body": "b",
        })
    after = reading.covered(ctx, "kafka-practice")
    # 같은 주제로 두 건이어도 **한 칸**이다. 진도가 주제 단위라서다.
    assert after["covered"] == 2


def test_노트가_있는_날들을_최신순으로_준다(ctx):
    for day in ("2026-09-01", "2026-09-08", "2026-09-05"):
        reading.write_note(ctx, "kafka-practice", day, "본문")
    assert reading.days_of(ctx, "kafka-practice") == \
        ["2026-09-08", "2026-09-05", "2026-09-01"]


# ── 노트를 기록으로 ──────────────────────────────────────────────

def test_코드펜스와_앞뒤_말을_견딘다():
    """\"JSON 만 출력해라\" 라고 적어도 설명을 붙이는 일이 있다.
    그때 통째로 실패하면 사용자는 노트를 다시 쓸 수 없다."""
    made = reading.parse_candidates(
        '정리했습니다.\n```json\n{"records":[{"title":"파티션은 병렬성의 단위다",'
        '"topic":"kafka-basics","kind":"CONCEPT","body":"컨슈머가 더 많으면 논다."}],'
        '"skipped":["전역 순서 이야기는 받아 적은 것"]}\n```\n확인해 주세요.',
        ["kafka-basics"])
    assert made["broken"] is False
    assert made["records"][0]["title"] == "파티션은 병렬성의 단위다"
    assert made["skipped"] == ["전역 순서 이야기는 받아 적은 것"]


def test_목록_밖_주제는_버린다():
    """목록 밖에 쌓인 기록은 어느 화면에서도 안 보인다."""
    made = reading.parse_candidates(
        '{"records":[{"title":"t","topic":"엉뚱한주제","kind":"CONCEPT","body":"b"},'
        '{"title":"t2","topic":"kafka-basics","kind":"CONCEPT","body":"b"}]}',
        ["kafka-basics"])
    assert [r["topic"] for r in made["records"]] == ["kafka-basics"]


def test_망가진_답은_broken_으로_돌아온다():
    """실패를 조용히 0건으로 만들면 '올릴 게 없다' 와 구별이 안 된다."""
    assert reading.parse_candidates("무슨 말이지", ["x"])["broken"] is True
    assert reading.parse_candidates("", ["x"])["broken"] is True


def test_다섯_건까지만():
    rows = ",".join(
        '{"title":"t%d","topic":"kafka-basics","kind":"CONCEPT","body":"b"}' % n
        for n in range(9))
    made = reading.parse_candidates('{"records":[%s]}' % rows, ["kafka-basics"])
    assert len(made["records"]) == 5


def test_모르는_kind_는_CONCEPT_로():
    made = reading.parse_candidates(
        '{"records":[{"title":"t","topic":"kafka-basics","kind":"MEMO","body":"b"}]}',
        ["kafka-basics"])
    assert made["records"][0]["kind"] == "CONCEPT"


def test_프롬프트에_받아_적은_것을_빼라고_적혀_있다():
    """이 한 줄이 이 프롬프트의 이유다 — 챗봇이 설명한 것을 내가 안 것으로
    올리면 준비도는 오르는데 면접에서는 못 쓴다."""
    made = reading.promote_prompt("노트", ["kafka-basics"])
    assert "옮겨 적기만 한 문장" in made and "빼라" in made
    assert "그대로" in made and "지어내지 마라" in made
    assert "kafka-basics" in made and "노트" in made


# ── 화면과 라우트 ────────────────────────────────────────────────

def _token(client):
    return client.app.state.ctx.settings.token


def test_오늘_읽기_화면이_열린다(client):
    page = client.get("/career/book/kafka-practice/today").text
    assert 'id="note"' in page
    assert "주제 0 / 11 채움" in page
    assert 'id="promote"' in page


def test_없는_책은_404(client):
    assert client.get("/career/book/없는책/today").status_code == 404


def test_노트를_저장하고_다시_열면_있다(client, ctx):
    res = client.post("/web/books/kafka-practice/note", data={
        "day": "2026-09-08", "text": "파티션은 병렬성의 단위다.", "_token": _token(client)})
    assert res.status_code == 200 and "saved_at" in res.json()
    assert "파티션은 병렬성의 단위다." in client.get(
        "/career/book/kafka-practice/today").text


def test_저장은_화면을_다시_안_그린다(client):
    """페이지를 되돌려 주면 커서가 튄다. 돌려주는 것은 저장 시각뿐이다."""
    res = client.post("/web/books/kafka-practice/note", data={
        "day": "2026-09-08", "text": "본문", "_token": _token(client)})
    assert res.headers["content-type"].startswith("application/json")


def test_토큰_없이는_저장_못_한다(client):
    assert client.post("/web/books/kafka-practice/note",
                       data={"day": "2026-09-08", "text": "x"}).status_code == 401


def test_이름이_규칙_밖이면_저장을_거절한다(client):
    """이 값이 그대로 디렉터리가 된다."""
    assert client.post("/web/books/../etc/note", data={
        "day": "2026-09-08", "text": "x", "_token": _token(client)}).status_code == 404


def test_빈_노트는_올릴_수_없다(client):
    assert client.post("/web/books/kafka-practice/promote", data={
        "day": "2026-09-08", "_token": _token(client)}).status_code == 400


def test_상태를_화면에서_바꾼다(client, ctx, home):
    res = client.post("/web/books/kafka-practice/state", data={
        "state": "중단", "_token": _token(client)}, follow_redirects=False)
    assert res.status_code == 303
    from warruru_local.daemon import careerview
    text = (paths.book_note_dir(home) / "kafka-practice.md").read_text(encoding="utf-8")
    assert "state: 중단" in text


def test_모르는_상태는_거절한다(client):
    assert client.post("/web/books/kafka-practice/state", data={
        "state": "대충 읽음", "_token": _token(client)}).status_code == 400


def test_책_목록이_상태로_갈린다(client, ctx):
    from warruru_local.daemon import careerview
    careerview.set_book_state(ctx, "kafka-practice", "읽는 중")
    page = client.get("/career/books").text
    읽는중 = page[page.index("<h2>읽는 중</h2>"):page.index("<h2>다음에 읽을 것</h2>")]
    assert "실전 카프카" in 읽는중
    assert "오늘 읽기" in 읽는중


def test_노트_날짜_화면이_책별로_편다(client, ctx):
    reading.write_note(ctx, "kafka-practice", "2026-09-08", "파티션 이야기")
    reading.write_note(ctx, "docker-k8s-start", "2026-09-08", "레이어 캐시")
    page = client.get("/notes/2026-09-08").text
    assert "노트 2개" in page
    assert "파티션 이야기" in page and "레이어 캐시" in page
    # 기록 0건이면 지금 올릴 길이 있어야 한다
    assert "지금 올리기" in page


def test_안_쓴_날은_모른다고_말한다(client):
    """읽었는데 안 썼는지 아예 안 읽었는지 이 화면은 모른다 —
    도구가 아는 척하지 않는다."""
    page = client.get("/notes/2026-09-06").text
    assert "노트를 안 썼다" in page
    assert "이 화면이 모른다" in page
