import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

DAY_START = "2026-07-22T00:00:00.000Z"
DAY_END = "2026-07-23T00:00:00.000Z"
T0 = "2026-07-21T23:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
T9 = "2026-07-22T23:59:59.999Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, DAY_START)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", DAY_START)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", DAY_START)
    return repository


def _work(repo, work_id, started_at, tool="codex"):
    repo.insert_work(
        work_id=work_id, machine_id=MACHINE, client_instance_id=CLIENT, tool=tool,
        title="제목", title_origin="USER", goal=None, origin="EXPLICIT",
        started_at=started_at, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", now_iso=started_at,
    )


def _ckp(repo, checkpoint_id, work_id, occurred_at=T1):
    repo.insert_checkpoint(
        checkpoint_id=checkpoint_id, work_id=work_id, machine_id=MACHINE,
        tool="codex", type="NOTE", title="제목", body=None, body_truncated=False,
        occurred_at=occurred_at, recorded_at=occurred_at, source="MCP",
        repo_path=None, repo_name=None, branch=None, commit_sha=None,
        dirty=None, dirty_file_count=None, dirty_count_capped=False,
        files=None, error_excerpt=None, tags=None,
    )


def test_그_날짜의_작업만_준다(repo):
    _work(repo, "wrk_어제", T0)
    _work(repo, "wrk_오늘", T1)
    ids = [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_오늘"]


def test_경계_시각을_포함하고_다음날_시작은_뺀다(repo):
    _work(repo, "wrk_자정", DAY_START)
    _work(repo, "wrk_막차", T9)
    _work(repo, "wrk_내일", DAY_END)
    ids = {row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)}
    assert ids == {"wrk_자정", "wrk_막차"}


def test_시작_시각_내림차순으로_준다(repo):
    _work(repo, "wrk_이른", T1)
    _work(repo, "wrk_늦은", T2)
    ids = [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_늦은", "wrk_이른"]


def test_삭제한_작업은_기본_조회에서_빠진다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    assert repo.list_works_between(DAY_START, DAY_END) == []


def test_삭제한_작업은_삭제_목록에_나온다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    ids = [row["work_id"] for row in repo.list_deleted_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_A"]


def test_작업을_복구하면_다시_보인다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    repo.restore_work("wrk_A")
    assert [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)] == ["wrk_A"]


def test_작업을_삭제해도_체크포인트_행은_남는다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_work("wrk_A", T2)
    assert repo.get_checkpoint("ckp_A")["deleted_at"] is None


def test_체크포인트를_삭제하면_목록에서_빠진다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    assert repo.list_checkpoints("wrk_A") == []
    assert len(repo.list_checkpoints("wrk_A", include_deleted=True)) == 1


def test_체크포인트를_복구하면_다시_보인다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    repo.restore_checkpoint("ckp_A")
    assert len(repo.list_checkpoints("wrk_A")) == 1


def test_삭제한_체크포인트는_삭제_목록에_나온다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    ids = [
        row["checkpoint_id"]
        for row in repo.list_deleted_checkpoints_between(DAY_START, DAY_END)
    ]
    assert ids == ["ckp_A"]


def test_작업을_삭제하면_체크포인트도_기본_조회에서_빠진다(repo):
    """체크포인트 자체는 deleted_at 이 없어도, 상위 세션 삭제를 조회가 함께 본다."""
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_work("wrk_A", T2)
    assert repo.list_checkpoints("wrk_A") == []
    assert len(repo.list_checkpoints("wrk_A", include_deleted=True)) == 1


def test_기록이_있는_직전_시각을_찾는다(repo):
    _work(repo, "wrk_어제", T0)
    assert repo.latest_work_started_before(DAY_START) == T0


def test_직전_기록이_없으면_None_이다(repo):
    assert repo.latest_work_started_before(DAY_START) is None
