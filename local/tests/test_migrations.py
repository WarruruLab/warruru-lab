import sqlite3

import pytest

from warruru_local.store import db, migrations

NOW = "2026-07-22T08:00:00.000Z"

EXPECTED_TABLES = {
    "schema_migrations",
    "machine",
    "client_instance",
    "work_session",
    "checkpoint",
    "learning_record",
    "draft",
}

# migrations.py의 _V1·_V2 DDL을 그대로 옮긴 계약. DDL이 바뀌면 여기도 같이 바뀌어야 한다.

EXPECTED_INDEXES = {
    "ix_work_started",
    "ix_work_by_client",
    "ix_work_by_repo",
    "ix_work_active_sweep",
    "ix_ckp_work",
    "ix_ckp_occurred",
    "ix_record_occurred",
    "ix_record_slug",
    "ix_record_work",
    "ix_draft_slug",
}

EXPECTED_COLUMNS = {
    "schema_migrations": {"version", "applied_at"},
    "machine": {"machine_id", "hostname", "os", "created_at"},
    "client_instance": {
        "client_instance_id",
        "machine_id",
        "tool",
        "client_name",
        "client_version",
        "cwd",
        "started_at",
        "closed_at",
        "created_at",
    },
    "work_session": {
        "work_id",
        "machine_id",
        "client_instance_id",
        "tool",
        "title",
        "title_origin",
        "goal",
        "status",
        "origin",
        "ended_reason",
        "started_at",
        "last_activity_at",
        "ended_at",
        "result",
        "limitations",
        "next_steps",
        "start_repo_path",
        "start_repo_name",
        "start_branch",
        "start_commit",
        "last_repo_path",
        "end_repo_path",
        "end_branch",
        "end_commit",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "checkpoint": {
        "checkpoint_id",
        "work_id",
        "machine_id",
        "tool",
        "type",
        "title",
        "body",
        "body_truncated",
        "occurred_at",
        "recorded_at",
        "source",
        "repo_path",
        "repo_name",
        "branch",
        "commit_sha",
        "dirty",
        "dirty_file_count",
        "dirty_count_capped",
        "files_json",
        "error_excerpt",
        "tags_json",
        "deleted_at",
        "created_at",
    },
    "learning_record": {
        "record_id",
        "work_id",
        "machine_id",
        "tool",
        "kind",
        "topic",
        "topic_slug",
        "title",
        "body",
        "body_truncated",
        "rationale",
        "outcome",
        "limitation",
        "interview",
        "project",
        "occurred_at",
        "recorded_at",
        "source",
        "repo_path",
        "repo_name",
        "branch",
        "commit_sha",
        "dirty",
        "dirty_file_count",
        "dirty_count_capped",
        "deleted_at",
        "created_at",
    },
    "draft": {
        "draft_id",
        "topic",
        "topic_slug",
        "kind_json",
        "title",
        "markdown",
        "markdown_truncated",
        "source_record_ids_json",
        "file_path",
        "status",
        "published_url",
        "published_at",
        "deleted_at",
        "created_at",
        "updated_at",
    },
}

# 각 테이블의 PRIMARY KEY 컬럼. SQLite는 INTEGER PRIMARY KEY(rowid 별칭)에도
# notnull=0을 보고하므로, PK는 pk 플래그로만 확인하고 notnull 여부는 별도로 본다.
EXPECTED_PRIMARY_KEYS = {
    "schema_migrations": "version",
    "machine": "machine_id",
    "client_instance": "client_instance_id",
    "work_session": "work_id",
    "checkpoint": "checkpoint_id",
    "learning_record": "record_id",
    "draft": "draft_id",
}

# DDL에 명시적으로 NOT NULL이 붙은 컬럼만 여기 포함한다 (PK 컬럼은 제외).
EXPECTED_NOT_NULL = {
    "schema_migrations": {"applied_at"},
    "machine": {"hostname", "os", "created_at"},
    "client_instance": {"machine_id", "tool", "started_at", "created_at"},
    "work_session": {
        "machine_id",
        "tool",
        "status",
        "origin",
        "started_at",
        "last_activity_at",
        "created_at",
        "updated_at",
    },
    "checkpoint": {
        "work_id",
        "machine_id",
        "tool",
        "type",
        "title",
        "body_truncated",
        "occurred_at",
        "recorded_at",
        "source",
        "dirty_count_capped",
        "created_at",
    },
    "learning_record": {
        "work_id",
        "machine_id",
        "tool",
        "kind",
        "topic",
        "topic_slug",
        "title",
        "body",
        "body_truncated",
        "occurred_at",
        "recorded_at",
        "source",
        "dirty_count_capped",
        "created_at",
    },
    "draft": {
        "topic",
        "topic_slug",
        "title",
        "markdown",
        "markdown_truncated",
        "status",
        "created_at",
        "updated_at",
    },
}

# DEFAULT가 붙은 컬럼. PRAGMA table_info의 dflt_value는 문자열로 나온다.
EXPECTED_DEFAULTS = {
    ("checkpoint", "body_truncated"): "0",
    ("checkpoint", "dirty_count_capped"): "0",
    ("learning_record", "body_truncated"): "0",
    ("learning_record", "dirty_count_capped"): "0",
    ("draft", "markdown_truncated"): "0",
}


def _tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"]: row for row in rows}


def _assert_column_contract(conn, table):
    columns = _columns(conn, table)
    assert set(columns) == EXPECTED_COLUMNS[table]

    pk_name = EXPECTED_PRIMARY_KEYS[table]
    assert columns[pk_name]["pk"] != 0

    for name in EXPECTED_NOT_NULL[table]:
        assert columns[name]["notnull"] == 1, f"{table}.{name}은 NOT NULL이어야 한다"

    for (t, col), default in EXPECTED_DEFAULTS.items():
        if t == table:
            assert columns[col]["dflt_value"] == default, (
                f"{table}.{col}의 기본값이 {default!r}이 아니다"
            )


def test_빈_DB_에_마이그레이션하면_현재_버전이_된다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    assert migrations.migrate(conn, NOW) == migrations.CURRENT_VERSION


def test_필요한_테이블이_모두_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    assert EXPECTED_TABLES <= _tables(conn)


def test_두_번_마이그레이션해도_안전하다(tmp_path):
    path = tmp_path / "warruru.db"
    conn = db.connect(path)
    migrations.migrate(conn, NOW)
    migrations.migrate(conn, NOW)
    assert migrations.current_version(conn) == migrations.CURRENT_VERSION
    assert EXPECTED_TABLES <= _tables(conn)


def test_WAL_모드가_켜진다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_외래키가_켜진다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_행을_이름으로_읽을_수_있다(tmp_path):
    """row_factory 계약을 본다. 버전이 늘면 행도 늘므로 최댓값을 읽는다."""
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    assert row["version"] == migrations.CURRENT_VERSION


def test_체크포인트_인덱스가_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert "ix_ckp_work" in names
    assert "ix_work_by_client" in names


def test_인덱스가_모두_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert EXPECTED_INDEXES <= names


def test_schema_migrations_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "schema_migrations")


def test_machine_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "machine")


def test_client_instance_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "client_instance")


def test_work_session_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "work_session")


def test_checkpoint_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "checkpoint")


def test_존재하지_않는_work_id로_체크포인트를_넣으면_무결성_오류가_난다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    conn.execute(
        "INSERT INTO machine (machine_id, hostname, os, created_at)"
        " VALUES (?, ?, ?, ?)",
        ("m1", "host", "windows", NOW),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO checkpoint ("
            " checkpoint_id, work_id, machine_id, tool, type, title,"
            " occurred_at, recorded_at, source, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ckp1",
                "존재하지-않는-work-id",
                "m1",
                "claude-code",
                "note",
                "제목",
                NOW,
                NOW,
                "test",
                NOW,
            ),
        )


# ── 마이그레이션 v2 ────────────────────────────────────────────────

V1_ROWS = {
    "machine": ("mch_기존", "host", "macOS", NOW),
    "work": ("wrk_기존", "mch_기존", "codex", "ACTIVE", "EXPLICIT", NOW, NOW, NOW, NOW),
    "ckp": ("ckp_기존", "wrk_기존", "mch_기존", "codex", "NOTE", "예전 제목",
            NOW, NOW, "MCP", NOW),
}


def _seed_v1(conn):
    """v1 스크립트만 적용한 DB 에 행 셋을 심는다."""
    conn.executescript(migrations._V1)
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)", (NOW,)
    )
    conn.execute(
        "INSERT INTO machine (machine_id, hostname, os, created_at)"
        " VALUES (?, ?, ?, ?)",
        V1_ROWS["machine"],
    )
    conn.execute(
        "INSERT INTO work_session (work_id, machine_id, tool, status, origin,"
        " started_at, last_activity_at, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        V1_ROWS["work"],
    )
    conn.execute(
        "INSERT INTO checkpoint (checkpoint_id, work_id, machine_id, tool, type,"
        " title, occurred_at, recorded_at, source, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        V1_ROWS["ckp"],
    )
    conn.commit()


def test_v2_테이블이_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    assert {"learning_record", "draft"} <= _tables(conn)


def test_스크립트가_버전_상수까지_빠짐없이_있다():
    """버전을 올리고 스크립트를 안 등록하면 조용히 안 만들어진다.
    상수를 다시 베끼는 대신 **둘이 맞는지**를 본다.
    """
    assert sorted(migrations._SCRIPTS) == list(
        range(1, migrations.CURRENT_VERSION + 1)
    )


def test_v1_데이터가_최신으로_올라가도_보존된다(tmp_path):
    """이미 쓰고 있는 DB 를 올리는 것이므로, 기존 행이 한 줄도 상하면 안 된다."""
    path = tmp_path / "warruru.db"
    conn = db.connect(path)
    _seed_v1(conn)
    assert migrations.current_version(conn) == 1

    assert migrations.migrate(conn, NOW) == migrations.CURRENT_VERSION

    assert conn.execute(
        "SELECT title FROM checkpoint WHERE checkpoint_id = ?", ("ckp_기존",)
    ).fetchone()["title"] == "예전 제목"
    assert conn.execute(
        "SELECT status FROM work_session WHERE work_id = ?", ("wrk_기존",)
    ).fetchone()["status"] == "ACTIVE"
    assert conn.execute(
        "SELECT hostname FROM machine WHERE machine_id = ?", ("mch_기존",)
    ).fetchone()["hostname"] == "host"


def test_v1_에서_올라온_DB_에도_새_테이블이_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    _seed_v1(conn)
    migrations.migrate(conn, NOW)
    assert {"learning_record", "draft"} <= _tables(conn)


def test_기록_인덱스가_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert {"ix_record_occurred", "ix_record_slug",
            "ix_record_work", "ix_draft_slug"} <= names


def test_learning_record_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "learning_record")


def test_draft_컬럼_계약을_지킨다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    _assert_column_contract(conn, "draft")


def test_존재하지_않는_work_id로_기록을_넣으면_무결성_오류가_난다(tmp_path):
    """체크포인트와 같은 규칙이다. 기록은 반드시 어떤 작업에 붙어 있어야 한다."""
    conn = db.connect(tmp_path / "warruru.db")
    _seed_v1(conn)
    migrations.migrate(conn, NOW)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO learning_record ("
            " record_id, work_id, machine_id, tool, kind, topic, topic_slug,"
            " title, body, occurred_at, recorded_at, source, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rec_A", "존재하지-않는-work-id", "mch_기존", "codex", "CONCEPT",
             "커넥션 풀", "connection-pool", "제목", "본문",
             NOW, NOW, "MCP", NOW),
        )


def test_measurement_와_tech_option_은_만들지_않는다(tmp_path):
    """정규화가 값을 하는 건 비교·집계 화면이 있을 때다. MVP 에 그런 화면이 없다.

    읽는 코드가 없는 테이블을 먼저 만드는 비용이, 나중에 v3 를 더하는 비용보다 크다.
    """
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    assert not ({"measurement", "tech_option"} & _tables(conn))


def test_v3_가_질문_체크_테이블을_만든다(tmp_path):
    """체크는 화면에서 3초 만에 눌리는 값이라 파일이 아니라 DB 로 간다."""
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    conn.execute(
        "INSERT INTO ask_check (topic_slug, ask_hash, ask_text, checked_at)"
        " VALUES ('ds-hash', 'abc', '충돌은?', ?)", (NOW,)
    )
    assert conn.execute("SELECT COUNT(*) AS n FROM ask_check").fetchone()["n"] == 1


def test_같은_질문을_두_번_체크해도_한_줄이다(tmp_path):
    """폼을 두 번 눌러도(뒤로 가기·새로고침) 상태가 어긋나지 않아야 한다."""
    import sqlite3

    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    conn.execute(
        "INSERT INTO ask_check (topic_slug, ask_hash, ask_text, checked_at)"
        " VALUES ('ds-hash', 'abc', '충돌은?', ?)", (NOW,)
    )
    try:
        conn.execute(
            "INSERT INTO ask_check (topic_slug, ask_hash, ask_text, checked_at)"
            " VALUES ('ds-hash', 'abc', '충돌은?', ?)", (NOW,)
        )
    except sqlite3.IntegrityError:
        pass
    assert conn.execute("SELECT COUNT(*) AS n FROM ask_check").fetchone()["n"] == 1


def test_v4_가_커리큘럼_진도_테이블을_만든다(tmp_path):
    """시험 범위가 로드맵과 안 겹치는 기간에도 셀 것이 있어야 화면이 움직인다."""
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    conn.execute(
        "INSERT INTO cert_progress (cert_key, item_hash, item_text, done, updated_at)"
        " VALUES ('jeongcheogi', 'abc', '기출 3개년', 3, ?)", (NOW,)
    )
    assert conn.execute(
        "SELECT done FROM cert_progress WHERE cert_key = 'jeongcheogi'"
    ).fetchone()["done"] == 3
