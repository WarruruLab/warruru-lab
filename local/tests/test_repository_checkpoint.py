import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    repository.insert_work(
        work_id=WORK, machine_id=MACHINE, client_instance_id=CLIENT, tool="codex",
        title="제목", title_origin="USER", goal=None, origin="EXPLICIT",
        started_at=NOW, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", now_iso=NOW,
    )
    return repository


def _insert(repo, checkpoint_id=CKP, ckp_type="PROBLEM", occurred_at=T1,
            files=None, tags=None, source="MCP"):
    return repo.insert_checkpoint(
        checkpoint_id=checkpoint_id, work_id=WORK, machine_id=MACHINE,
        tool="codex", type=ckp_type, title="제목", body="본문",
        body_truncated=False, occurred_at=occurred_at, recorded_at=occurred_at,
        source=source, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", dirty=True, dirty_file_count=4,
        dirty_count_capped=False, files=files, error_excerpt=None, tags=tags,
    )


def test_체크포인트를_넣으면_읽을_수_있다(repo):
    row, duplicate = _insert(repo)
    assert duplicate is False
    assert row["type"] == "PROBLEM"
    assert row["dirty"] == 1
    assert row["source"] == "MCP"


def test_같은_식별자면_기존_행을_준다(repo):
    _insert(repo, ckp_type="PROBLEM")
    row, duplicate = _insert(repo, ckp_type="RESULT")
    assert duplicate is True
    assert row["type"] == "PROBLEM"


def test_파일과_태그는_목록으로_오가며_JSON_으로_저장된다(repo):
    _insert(repo, files=["a.py", "b.py"], tags=["idempotency"])
    row = repo.get_checkpoint(CKP)
    assert row["files_json"] == '["a.py", "b.py"]'
    assert row["tags_json"] == '["idempotency"]'


def test_파일이_없으면_빈_목록으로_저장된다(repo):
    _insert(repo)
    assert repo.get_checkpoint(CKP)["files_json"] == "[]"


def test_작업의_체크포인트를_발생_시각_오름차순으로_준다(repo):
    _insert(repo, checkpoint_id="ckp_늦음", occurred_at=T2)
    _insert(repo, checkpoint_id="ckp_이름", occurred_at=T1)
    ids = [row["checkpoint_id"] for row in repo.list_checkpoints(WORK)]
    assert ids == ["ckp_이름", "ckp_늦음"]


def test_같은_시각이면_생성_순서로_결정한다(repo):
    _insert(repo, checkpoint_id="ckp_A", occurred_at=T1)
    _insert(repo, checkpoint_id="ckp_B", occurred_at=T1)
    ids = [row["checkpoint_id"] for row in repo.list_checkpoints(WORK)]
    assert ids == ["ckp_A", "ckp_B"]


def test_개수를_센다(repo):
    _insert(repo, checkpoint_id="ckp_A")
    _insert(repo, checkpoint_id="ckp_B")
    assert repo.count_checkpoints(WORK) == 2


def test_유형별_개수를_센다(repo):
    _insert(repo, checkpoint_id="ckp_A", ckp_type="ATTEMPT")
    _insert(repo, checkpoint_id="ckp_B", ckp_type="ATTEMPT")
    _insert(repo, checkpoint_id="ckp_C", ckp_type="RESULT")
    assert repo.count_types(WORK) == {"ATTEMPT": 2, "RESULT": 1}


def test_spool_에서_온_기록은_출처가_다르다(repo):
    _insert(repo, source="SPOOL")
    assert repo.get_checkpoint(CKP)["source"] == "SPOOL"


def test_dirty_가_None_이면_NULL_로_저장된다(repo):
    """워크트리를 읽지 못한 경우를 나타낸다. None은 0으로 강제되지 않는다."""
    row, _ = repo.insert_checkpoint(
        checkpoint_id="ckp_아무것도없음", work_id=WORK, machine_id=MACHINE,
        tool="codex", type="PROBLEM", title="제목", body="본문",
        body_truncated=False, occurred_at=T1, recorded_at=T1,
        source="MCP", repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", dirty=None, dirty_file_count=None,
        dirty_count_capped=False, files=None, error_excerpt=None, tags=None,
    )
    assert row["dirty"] is None
    assert row["dirty_file_count"] is None
