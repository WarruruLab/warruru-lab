import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
OTHER_CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF5"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    repository.ensure_client(OTHER_CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    return repository


def _insert(repo, work_id=WORK, client=CLIENT, started_at=NOW, repo_path="D:/x",
            origin="EXPLICIT", title="제목"):
    return repo.insert_work(
        work_id=work_id,
        machine_id=MACHINE,
        client_instance_id=client,
        tool="codex",
        title=title,
        title_origin="USER" if title else None,
        goal="목표",
        origin=origin,
        started_at=started_at,
        repo_path=repo_path,
        repo_name="x",
        branch="main",
        commit_sha="a3f91c2",
        now_iso=started_at,
    )


def test_작업을_만들면_ACTIVE_다(repo):
    row, duplicate = _insert(repo)
    assert row["status"] == "ACTIVE"
    assert row["origin"] == "EXPLICIT"
    assert row["last_activity_at"] == NOW
    assert row["last_repo_path"] == "D:/x"
    assert duplicate is False


def test_같은_식별자를_다시_넣으면_기존_행을_준다(repo):
    _insert(repo, title="처음")
    row, duplicate = _insert(repo, title="나중")
    assert duplicate is True
    assert row["title"] == "처음"


def test_활동을_갱신하면_마지막_시각과_저장소가_바뀐다(repo):
    _insert(repo)
    repo.touch_work(WORK, T1, "D:/y")
    row = repo.get_work(WORK)
    assert row["last_activity_at"] == T1
    assert row["last_repo_path"] == "D:/y"


def test_저장소가_None_이면_기존_저장소를_유지한다(repo):
    _insert(repo)
    repo.touch_work(WORK, T1, None)
    assert repo.get_work(WORK)["last_repo_path"] == "D:/x"


def test_제목을_승격하면_파생으로_표시된다(repo):
    _insert(repo, title=None)
    repo.set_work_title(WORK, "첫 체크포인트 제목")
    row = repo.get_work(WORK)
    assert row["title"] == "첫 체크포인트 제목"
    assert row["title_origin"] == "DERIVED"


def _promote(repo, work_id=WORK, title="사용자 제목"):
    return repo.promote_work(
        work_id=work_id,
        title=title,
        goal="사용자 목표",
        started_at=T1,
        repo_path="D:/y",
        repo_name="y",
        branch="feat",
        commit_sha="bbb",
        now_iso=T2,
    )


def test_자동으로_만든_세션은_사용자가_적은_값으로_올라간다(repo):
    _insert(repo, origin="INFERRED", title=None)
    repo.set_work_title(WORK, "체크포인트에서 딴 제목")
    row = _promote(repo)
    assert row["origin"] == "EXPLICIT"
    assert row["title"] == "사용자 제목"
    assert row["title_origin"] == "USER"
    assert row["goal"] == "사용자 목표"
    assert row["started_at"] == T1
    assert row["start_commit"] == "bbb"


def test_명시적으로_시작한_세션은_올리지_않는다(repo):
    _insert(repo, origin="EXPLICIT", title="처음 제목")
    row = _promote(repo)
    assert row["title"] == "처음 제목"
    assert row["started_at"] == NOW
    assert row["origin"] == "EXPLICIT"


def test_사용자가_붙인_제목은_올릴_때도_덮지_않는다(repo):
    _insert(repo, origin="INFERRED", title="사용자가 먼저 적은 제목")
    row = _promote(repo)
    assert row["title"] == "사용자가 먼저 적은 제목"
    assert row["origin"] == "INFERRED"


def test_제목_없이_올리면_있던_제목을_지우지_않는다(repo):
    _insert(repo, origin="INFERRED", title=None)
    repo.set_work_title(WORK, "체크포인트에서 딴 제목")
    row = _promote(repo, title=None)
    assert row["title"] == "체크포인트에서 딴 제목"
    assert row["title_origin"] == "DERIVED"
    assert row["origin"] == "EXPLICIT"


def test_대화로_진행중_작업을_찾는다(repo):
    _insert(repo)
    assert repo.find_active_by_client(CLIENT)["work_id"] == WORK


def test_대화에_진행중_작업이_여러_개면_가장_최근_것을_준다(repo):
    _insert(repo, work_id="wrk_A", started_at=NOW)
    _insert(repo, work_id="wrk_B", started_at=T1)
    assert repo.find_active_by_client(CLIENT)["work_id"] == "wrk_B"


def test_저장소와_시간창으로_진행중_작업을_찾는다(repo):
    _insert(repo)
    found = repo.find_active_by_repo(MACHINE, "codex", "D:/x", since_iso=NOW)
    assert found["work_id"] == WORK


def test_시간창_밖이면_찾지_않는다(repo):
    _insert(repo)
    assert repo.find_active_by_repo(MACHINE, "codex", "D:/x", since_iso=T1) is None


def test_마감하면_FINISHED_이고_사유가_남는다(repo):
    _insert(repo)
    row = repo.finish_work(
        work_id=WORK, result="됐다", limitations="한계", next_steps="다음",
        ended_at=T2, repo_path="D:/x", branch="main", commit_sha="bbb",
        now_iso=T2,
    )
    assert row["status"] == "FINISHED"
    assert row["ended_reason"] == "USER_FINISH"
    assert row["end_commit"] == "bbb"
    assert row["result"] == "됐다"


def test_마감된_작업은_대화_조회에_안_걸린다(repo):
    _insert(repo)
    repo.finish_work(
        work_id=WORK, result=None, limitations=None, next_steps=None,
        ended_at=T2, repo_path=None, branch=None, commit_sha=None, now_iso=T2,
    )
    assert repo.find_active_by_client(CLIENT) is None


def test_자동마감은_AUTO_CLOSED_이고_사유를_보존한다(repo):
    _insert(repo)
    row = repo.auto_close_work(WORK, "IDLE_TIMEOUT", ended_at=NOW, now_iso=T2)
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "IDLE_TIMEOUT"
    assert row["ended_at"] == NOW


def test_유휴_기준보다_오래된_진행중_작업을_찾는다(repo):
    _insert(repo, work_id="wrk_오래", started_at=NOW)
    _insert(repo, work_id="wrk_최근", started_at=T2)
    stale = repo.find_stale_active(before_iso=T1)
    assert [row["work_id"] for row in stale] == ["wrk_오래"]


def test_대화의_진행중_작업을_모두_찾는다(repo):
    _insert(repo, work_id="wrk_A", started_at=NOW)
    _insert(repo, work_id="wrk_B", started_at=T1)
    _insert(repo, work_id="wrk_C", client=OTHER_CLIENT, started_at=T1)
    ids = {row["work_id"] for row in repo.find_active_by_client_ids(CLIENT)}
    assert ids == {"wrk_A", "wrk_B"}


def test_대화의_삭제된_진행중_작업은_찾지_않는다(repo):
    _insert(repo, work_id="wrk_A", started_at=NOW)
    _insert(repo, work_id="wrk_B", started_at=T1)
    # wrk_A를 소프트 삭제
    repo._conn.execute(
        "UPDATE work_session SET deleted_at = ? WHERE work_id = ?",
        (T2, "wrk_A"),
    )
    ids = {row["work_id"] for row in repo.find_active_by_client_ids(CLIENT)}
    assert ids == {"wrk_B"}


def test_유휴_작업_중_삭제된_작업은_찾지_않는다(repo):
    _insert(repo, work_id="wrk_오래", started_at=NOW)
    _insert(repo, work_id="wrk_최근", started_at=T2)
    # wrk_오래를 소프트 삭제
    repo._conn.execute(
        "UPDATE work_session SET deleted_at = ? WHERE work_id = ?",
        (T2, "wrk_오래"),
    )
    stale = repo.find_stale_active(before_iso=T1)
    assert stale == []
