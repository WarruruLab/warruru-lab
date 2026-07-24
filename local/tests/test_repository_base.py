import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
LATER = "2026-07-22T09:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    return Repository(conn)


def test_머신을_만들면_행이_생긴다(repo):
    row = repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    assert row["machine_id"] == MACHINE
    assert row["hostname"] == "DESKTOP-A"


def test_머신을_두_번_만들면_처음_값이_남는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    row = repo.ensure_machine(MACHINE, "DESKTOP-B", "macOS 15", LATER)
    assert row["hostname"] == "DESKTOP-A"
    assert row["created_at"] == NOW


def test_클라이언트를_처음_보면_행이_생긴다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    row = repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/x", NOW)
    assert row["tool"] == "codex"
    assert row["cwd"] == "D:/x"
    assert row["closed_at"] is None


def test_클라이언트를_다시_보면_새로_만들지_않는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/x", NOW)
    row = repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/y", LATER)
    assert row["started_at"] == NOW
    assert row["cwd"] == "D:/y"  # 최근 작업 디렉터리는 갱신한다


def test_클라이언트를_닫으면_닫힌_시각이_남는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repo.ensure_client(CLIENT, MACHINE, "codex", None, None, None, NOW)
    repo.close_client(CLIENT, LATER)
    assert repo.get_client(CLIENT)["closed_at"] == LATER


def test_없는_클라이언트를_닫아도_터지지_않는다(repo):
    repo.close_client("cli_없음", LATER)
    assert repo.get_client("cli_없음") is None
