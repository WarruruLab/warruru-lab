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
OTHER = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF5"
SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="aaa",
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
    repo.ensure_client(OTHER, MACHINE, "codex", None, None, "D:/x", to_iso(START))
    clock = FixedClock(START)
    counter = iter(f"wrk_생성{index}" for index in range(100))
    made = SessionService(
        repo, clock, _settings(tmp_path), id_factory=lambda prefix: next(counter)
    )
    made.repo = repo
    made.clock = clock
    return made


def _attach(service, work_id=None, client=CLIENT, snapshot=SNAPSHOT):
    return service.attach(
        work_id=work_id, client_instance_id=client, machine_id=MACHINE,
        tool="codex", snapshot=snapshot,
    )


def test_요청에_식별자가_있으면_그_작업에_붙는다(service):
    work, _ = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, work_id="wrk_A")
    assert result.work["work_id"] == "wrk_A"
    assert result.attached_by == "REQUEST"


def test_없는_식별자를_주면_그_식별자로_만든다(service):
    result = _attach(service, work_id="wrk_늦게도착")
    assert result.work["work_id"] == "wrk_늦게도착"
    assert result.work["origin"] == "INFERRED"
    assert result.attached_by == "REQUEST"


def test_이미_마감된_작업에도_그대로_붙인다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    service.repo.finish_work(
        work_id="wrk_A", result=None, limitations=None, next_steps=None,
        ended_at=to_iso(START), repo_path=None, branch=None, commit_sha=None,
        now_iso=to_iso(START),
    )
    assert _attach(service, work_id="wrk_A").work["status"] == "FINISHED"


def test_식별자가_없으면_같은_대화의_진행중_작업에_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service)
    assert result.work["work_id"] == "wrk_A"
    assert result.attached_by == "CLIENT_INSTANCE"


def test_대화가_다르면_그_대화의_작업에_붙지_않는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=CLIENT)
    assert result.attached_by == "REPO_WINDOW"
    assert result.work["work_id"] == "wrk_A"


def test_대화가_없으면_저장소와_시간창으로_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=None)
    assert result.attached_by == "REPO_WINDOW"


def test_시간창을_넘기면_새_작업을_만든다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    service.clock.advance(timedelta(minutes=91).total_seconds())
    result = _attach(service, client=None)
    assert result.attached_by == "NEW"
    assert result.work["work_id"] == "wrk_생성0"


def test_저장소_정보가_없으면_시간창_규칙을_쓰지_않는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=None, snapshot=GitSnapshot.EMPTY)
    assert result.attached_by == "NEW"


def test_아무것도_없으면_새_작업을_만들고_제목이_없다(service):
    result = _attach(service)
    assert result.attached_by == "NEW"
    assert result.work["origin"] == "INFERRED"
    assert result.work["title"] is None


def test_한_대화에_진행중이_여럿이면_가장_최근에_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="처음", goal=None, snapshot=SNAPSHOT,
    )
    service.clock.advance(60)
    service.start(
        work_id="wrk_B", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="나중", goal=None, snapshot=SNAPSHOT,
    )
    assert _attach(service).work["work_id"] == "wrk_B"


def test_start_는_명시적_세션을_만든다(service):
    work, duplicate = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal="목표", snapshot=SNAPSHOT,
    )
    assert duplicate is False
    assert work["origin"] == "EXPLICIT"
    assert work["title_origin"] == "USER"
    assert work["start_commit"] == "aaa"


def test_start_를_두_번_부르면_기존_세션을_준다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="처음", goal=None, snapshot=SNAPSHOT,
    )
    work, duplicate = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="나중", goal=None, snapshot=SNAPSHOT,
    )
    assert duplicate is True
    assert work["title"] == "처음"


def test_제목이_없는_세션은_제목을_승격한다(service):
    result = _attach(service)
    service.promote_title(result.work, "첫 체크포인트")
    assert service.repo.get_work(result.work["work_id"])["title"] == "첫 체크포인트"


def test_제목이_있으면_승격하지_않는다(service):
    work, _ = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="원래 제목", goal=None, snapshot=SNAPSHOT,
    )
    service.promote_title(work, "덮어쓰기 시도")
    assert service.repo.get_work("wrk_A")["title"] == "원래 제목"
