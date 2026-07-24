from datetime import datetime, timedelta, timezone

import pytest

from warruru_local.clock import FixedClock, to_iso
from warruru_local.config import Settings
from warruru_local.gitinfo import GitSnapshot
from warruru_local.session import SessionService
from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="aaa",
    dirty=False, dirty_file_count=0,
)
END_SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="bbb",
    dirty=False, dirty_file_count=0,
)


def _settings(tmp_path) -> Settings:
    return Settings(
        home=tmp_path, host="127.0.0.1", port=8787, token="t", tool=None,
        http_timeout_seconds=3.0, autostart_daemon=False,
        attach_window_minutes=90, idle_timeout_hours=4,
        sweep_interval_seconds=300, git_timeout_seconds=2.0,
        git_cache_ttl_seconds=5.0, git_dirty_file_cap=500,
        spool_quiet_seconds=10, log_level="INFO",
    )


@pytest.fixture
def service(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, to_iso(START))
    repo = Repository(conn)
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", to_iso(START))
    repo.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", to_iso(START))
    return SessionService(repo, FixedClock(START), _settings(tmp_path))


def _start(service, work_id="wrk_A", client=CLIENT):
    work, _ = service.start(
        work_id=work_id, client_instance_id=client, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    return work


def test_유휴_제한_전에는_마감하지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=3).total_seconds())
    assert service.sweep_idle() == []
    assert service.repo.get_work("wrk_A")["status"] == "ACTIVE"


def test_유휴_제한을_넘기면_자동_마감한다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    assert service.sweep_idle() == ["wrk_A"]
    row = service.repo.get_work("wrk_A")
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "IDLE_TIMEOUT"


def test_자동_마감_시각은_마지막_활동_시각이다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.repo.get_work("wrk_A")["ended_at"] == to_iso(START)


def test_자동_마감은_종료_커밋을_남기지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.repo.get_work("wrk_A")["end_commit"] is None


def test_두_번_쓸어도_같은_작업을_다시_마감하지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.sweep_idle() == []


def test_대화가_끝나면_진행중_작업을_마감한다(service):
    _start(service, work_id="wrk_A")
    _start(service, work_id="wrk_B")
    closed = service.close_client(CLIENT)
    assert set(closed) == {"wrk_A", "wrk_B"}
    assert service.repo.get_work("wrk_A")["ended_reason"] == "CLIENT_EXIT"


def test_대화가_끝나면_대화_행에도_닫힌_시각이_남는다(service):
    _start(service)
    service.close_client(CLIENT)
    assert service.repo.get_client(CLIENT)["closed_at"] is not None


def test_진행중_작업이_없는_대화를_닫아도_터지지_않는다(service):
    assert service.close_client(CLIENT) == []


def test_마감하면_결과와_종료_커밋이_남는다(service):
    _start(service)
    service.clock.advance(600)
    row = service.finish(
        work_id="wrk_A", client_instance_id=CLIENT, result="됐다",
        limitations="한계", next_steps="다음", snapshot=END_SNAPSHOT,
    )
    assert row["status"] == "FINISHED"
    assert row["end_commit"] == "bbb"
    assert row["result"] == "됐다"


def test_식별자가_없으면_그_대화의_최근_작업을_마감한다(service):
    _start(service, work_id="wrk_A")
    service.clock.advance(60)
    _start(service, work_id="wrk_B")
    row = service.finish(
        work_id=None, client_instance_id=CLIENT, result=None, limitations=None,
        next_steps=None, snapshot=END_SNAPSHOT,
    )
    assert row["work_id"] == "wrk_B"


def test_마감할_작업이_없으면_None_이다(service):
    assert service.finish(
        work_id=None, client_instance_id=CLIENT, result=None, limitations=None,
        next_steps=None, snapshot=END_SNAPSHOT,
    ) is None


def test_자동_마감된_작업도_뒤늦게_마감할_수_있다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    row = service.finish(
        work_id="wrk_A", client_instance_id=CLIENT, result="뒤늦은 결과",
        limitations=None, next_steps=None, snapshot=END_SNAPSHOT,
    )
    assert row["status"] == "FINISHED"
    assert row["ended_reason"] == "USER_FINISH"
    assert row["result"] == "뒤늦은 결과"
