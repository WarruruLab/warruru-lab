"""`RecordRepository` — 기록 저장과 조회.

기존 `repository.py`(483줄·메서드 28개)에 넣지 않고 옆 파일로 둔다.
`insert` 멱등 · 구간 조회 · soft delete 패턴은 그대로 복사한다.
"""

import pytest

from warruru_local.store import db, migrations
from warruru_local.store.records import RecordRepository

NOW = "2026-08-18T09:00:00.000Z"
MACHINE = "mch_테스트"
WORK = "wrk_테스트"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    conn.execute(
        "INSERT INTO machine (machine_id, hostname, os, created_at)"
        " VALUES (?, ?, ?, ?)",
        (MACHINE, "host", "macOS", NOW),
    )
    conn.execute(
        "INSERT INTO work_session (work_id, machine_id, tool, status, origin,"
        " started_at, last_activity_at, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (WORK, MACHINE, "codex", "ACTIVE", "EXPLICIT", NOW, NOW, NOW, NOW),
    )
    conn.commit()
    return RecordRepository(conn)


def _record(repo, record_id="rec_A", *, topic="connection pool",
            slug="connection-pool", kind="EXPERIMENT", title="제목",
            body="본문", occurred_at=NOW, **extra):
    values = dict(
        record_id=record_id, work_id=WORK, machine_id=MACHINE, tool="codex",
        kind=kind, topic=topic, topic_slug=slug, title=title, body=body,
        body_truncated=False, rationale=None, outcome=None, limitation=None,
        interview=None, project=None, occurred_at=occurred_at, recorded_at=NOW,
        source="MCP", repo_path=None, repo_name=None, branch=None,
        commit_sha=None, dirty=None, dirty_file_count=None,
        dirty_count_capped=False,
    )
    values.update(extra)
    return repo.insert_record(**values)


def test_기록이_저장되고_다시_읽힌다(repo):
    row, duplicated = _record(repo)
    assert duplicated is False
    assert row["record_id"] == "rec_A"
    assert repo.get_record("rec_A")["title"] == "제목"


def test_원문_topic_이_슬러그로_덮이지_않는다(repo):
    """화면에 보여야 하는 것은 사람이 적은 말이다."""
    _record(repo, topic="  Connection Pool  ", slug="connection-pool")
    assert repo.get_record("rec_A")["topic"] == "  Connection Pool  "
    assert repo.get_record("rec_A")["topic_slug"] == "connection-pool"


def test_같은_record_id_를_다시_보내면_중복으로_저장되지_않는다(repo):
    """spool 을 두 번 흡수해도 중복이 생기지 않아야 한다."""
    _record(repo, title="처음")
    row, duplicated = _record(repo, title="나중")
    assert duplicated is True
    assert row["title"] == "처음"
    assert len(repo.list_records()) == 1


def test_topic_slug_로_거른다(repo):
    _record(repo, "rec_A", slug="connection-pool")
    _record(repo, "rec_B", slug="jvm-gc")
    assert [r["record_id"] for r in repo.list_records(topic_slug="jvm-gc")] == ["rec_B"]


def test_기간으로_거른다(repo):
    _record(repo, "rec_A", occurred_at="2026-08-17T09:00:00.000Z")
    _record(repo, "rec_B", occurred_at="2026-08-18T09:00:00.000Z")
    found = repo.list_records(since="2026-08-18T00:00:00.000Z",
                              until="2026-08-19T00:00:00.000Z")
    assert [r["record_id"] for r in found] == ["rec_B"]


def test_끝_경계는_배타적이다(repo):
    """`local_day_bounds` 가 주는 끝은 다음날 자정이다. 그 값이 포함되면 하루가 겹친다."""
    _record(repo, "rec_A", occurred_at="2026-08-19T00:00:00.000Z")
    found = repo.list_records(since="2026-08-18T00:00:00.000Z",
                              until="2026-08-19T00:00:00.000Z")
    assert found == []


def test_최신순으로_돌려준다(repo):
    _record(repo, "rec_A", occurred_at="2026-08-17T09:00:00.000Z")
    _record(repo, "rec_B", occurred_at="2026-08-18T09:00:00.000Z")
    assert [r["record_id"] for r in repo.list_records()] == ["rec_B", "rec_A"]


def test_limit_상한은_100_이다(repo):
    for i in range(3):
        _record(repo, f"rec_{i}")
    assert len(repo.list_records(limit=2)) == 2
    assert repo.list_records(limit=9999) == repo.list_records(limit=100)


def test_삭제한_기록은_기본_목록에_안_나온다(repo):
    _record(repo, "rec_A")
    repo.soft_delete("rec_A", NOW)
    assert repo.list_records() == []
    assert len(repo.list_records(include_deleted=True)) == 1


def test_삭제한_기록을_되살린다(repo):
    _record(repo, "rec_A")
    repo.soft_delete("rec_A", NOW)
    repo.restore("rec_A")
    assert len(repo.list_records()) == 1


# ── 슬러그 집계 ────────────────────────────────────────────────────

def test_슬러그별_집계가_건수와_마지막_시각을_돌려준다(repo):
    _record(repo, "rec_A", slug="connection-pool",
            occurred_at="2026-08-18T09:00:00.000Z")
    _record(repo, "rec_B", slug="connection-pool", kind="TROUBLESHOOTING",
            occurred_at="2026-08-18T16:40:00.000Z")
    _record(repo, "rec_C", slug="jvm-gc", occurred_at="2026-08-18T11:00:00.000Z")

    summary = {row["topic_slug"]: row for row in repo.slug_summary()}
    assert summary["connection-pool"]["count"] == 2
    assert summary["connection-pool"]["last_occurred_at"] == "2026-08-18T16:40:00.000Z"
    assert summary["connection-pool"]["kinds"] == {"EXPERIMENT": 1, "TROUBLESHOOTING": 1}
    assert summary["jvm-gc"]["count"] == 1


def test_집계도_원문_topic_을_함께_돌려준다(repo):
    """화면은 슬러그가 아니라 사람이 적은 말을 보여준다."""
    _record(repo, "rec_A", topic="커넥션 풀", slug="커넥션-풀")
    assert repo.slug_summary()[0]["topic"] == "커넥션 풀"


def test_집계는_건수가_많은_순이다(repo):
    _record(repo, "rec_A", slug="jvm-gc")
    _record(repo, "rec_B", slug="connection-pool")
    _record(repo, "rec_C", slug="connection-pool")
    assert [row["topic_slug"] for row in repo.slug_summary()][0] == "connection-pool"


def test_집계에_삭제한_기록은_안_들어간다(repo):
    _record(repo, "rec_A", slug="connection-pool")
    repo.soft_delete("rec_A", NOW)
    assert repo.slug_summary() == []


# ── 유사 슬러그 ────────────────────────────────────────────────────

def test_기록이_없어도_권장_슬러그가_힌트로_나온다(repo):
    """힌트가 가장 필요한 순간은 기록이 0건인 첫날이다.

    DB 만 보면 그때 항상 비어서, 필요한 순간에만 없는 장치가 된다.
    """
    assert "jpa-n-plus-one" in repo.similar_slugs("jpa-n-plus")


def test_DB_에_있는_슬러그도_힌트로_나온다(repo):
    _record(repo, "rec_A", slug="커넥션-풀")
    assert "커넥션-풀" in repo.similar_slugs("커넥션")


def test_유사한_것이_없으면_빈_목록이다(repo):
    assert repo.similar_slugs("전혀-관련-없는-무엇") == []


def test_힌트에_중복이_없다(repo):
    """권장 상수와 DB 양쪽에 있는 슬러그가 두 번 나오면 안 된다."""
    _record(repo, "rec_A", slug="jpa-n-plus-one")
    hints = repo.similar_slugs("jpa-n-plus-one")
    assert len(hints) == len(set(hints))


def test_자기_자신과_똑같은_슬러그는_힌트가_아니다(repo):
    """이미 맞는 슬러그를 쓴 사람에게 그 슬러그를 알려줄 이유가 없다."""
    _record(repo, "rec_A", slug="커넥션-풀")
    assert "커넥션-풀" not in repo.similar_slugs("커넥션-풀")


# ── 보강 (같은 기록을 다시 불러 빈칸을 채운다) ──────────────────────

def test_빈_필드를_나중에_채울_수_있다(repo):
    """힌트가 '다시 불러 채우라'고 하는데 채울 방법이 없으면 그 장치는 무의미하다."""
    _record(repo, "rec_A")
    row, filled = repo.fill_record("rec_A", {"outcome": "p95 가 90ms 로 내려갔다"})
    assert filled == ["outcome"]
    assert row["outcome"] == "p95 가 90ms 로 내려갔다"


def test_이미_있는_값은_덮어쓰지_않는다(repo):
    """spool 을 두 번 흡수해도 안전해야 하고, 실수로 지워지면 안 된다."""
    _record(repo, "rec_A", outcome="처음 결과")
    row, filled = repo.fill_record("rec_A", {"outcome": "나중 결과"})
    assert filled == []
    assert row["outcome"] == "처음 결과"


def test_공백뿐인_값으로는_채우지_않는다(repo):
    _record(repo, "rec_A")
    _, filled = repo.fill_record("rec_A", {"outcome": "   "})
    assert filled == []


def test_비어_있던_필수_필드도_채울_수_있다(repo):
    _record(repo, "rec_A", title="")
    row, filled = repo.fill_record("rec_A", {"title": "풀 크기 10→30"})
    assert filled == ["title"]
    assert row["title"] == "풀 크기 10→30"


def test_없는_기록을_채우려_하면_None_이다(repo):
    assert repo.fill_record("rec_없음", {"outcome": "x"}) == (None, [])


# ── 유사 슬러그의 짧은 후보 ────────────────────────────────────────

def test_짧은_슬러그가_아무_주제에나_달라붙지_않는다(repo):
    """`C++` 는 `c` 로 슬러그가 된다. 그 한 글자가 모든 슬러그에 포함되므로,
    후보 쪽에 길이 조건이 없으면 힌트가 전부 `c` 를 가리킨다.
    에이전트는 그 힌트를 읽고 따르므로 기록이 쓰레기 슬러그로 쏠린다.
    """
    _record(repo, "rec_A", topic="C++", slug="c")
    assert "c" not in repo.similar_slugs("connection-pool")
    assert "c" not in repo.similar_slugs("misc")


# ── material_rows — 재료 막대의 재료 ──────────────────────────────────


def test_material_rows_는_상한에_걸리지_않는다(repo):
    """`list_records` 는 100건에서 잘린다. 그것으로 막대를 세면 기록이
    쌓일수록 막대가 실제보다 비어 보이는데, 화면은 그 사실을 말해 주지 않는다.
    """
    for i in range(120):
        _record(repo, f"rec_{i:03d}", rationale="골랐다")

    assert len(repo.list_records(limit=1000)) == 100      # 상한이 살아 있다
    assert len(repo.material_rows()) == 120               # 여기는 안 걸린다


def test_material_rows_는_본문을_읽지_않는다(repo):
    """`body` 는 64KB 까지 커진다. 목록 화면 한 번에 수십 MB 를 읽을 이유가 없다."""
    _record(repo, "rec_A", body="본" * 1000, rationale="골랐다")

    row = repo.material_rows()[0]

    assert set(row) == {"topic_slug", "rationale", "outcome", "limitation", "interview"}


def test_material_rows_는_지운_기록을_빼고_준다(repo):
    _record(repo, "rec_A")
    _record(repo, "rec_B")
    repo.soft_delete("rec_B", NOW)

    assert len(repo.material_rows()) == 1
