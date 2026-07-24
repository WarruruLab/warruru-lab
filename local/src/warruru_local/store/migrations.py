"""스키마 버전과 DDL. 데몬이 기동 시 순차 적용한다. 되돌리기는 없다."""

from __future__ import annotations

import sqlite3

CURRENT_VERSION = 1

_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine (
    machine_id TEXT PRIMARY KEY,
    hostname   TEXT NOT NULL,
    os         TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_instance (
    client_instance_id TEXT PRIMARY KEY,
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,
    client_name        TEXT,
    client_version     TEXT,
    cwd                TEXT,
    started_at         TEXT NOT NULL,
    closed_at          TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_session (
    work_id            TEXT PRIMARY KEY,
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    client_instance_id TEXT REFERENCES client_instance(client_instance_id),
    tool               TEXT NOT NULL,

    title              TEXT,
    title_origin       TEXT,
    goal               TEXT,

    status             TEXT NOT NULL,
    origin             TEXT NOT NULL,
    ended_reason       TEXT,

    started_at         TEXT NOT NULL,
    last_activity_at   TEXT NOT NULL,
    ended_at           TEXT,

    result             TEXT,
    limitations        TEXT,
    next_steps         TEXT,

    start_repo_path    TEXT,
    start_repo_name    TEXT,
    start_branch       TEXT,
    start_commit       TEXT,
    last_repo_path     TEXT,
    end_repo_path      TEXT,
    end_branch         TEXT,
    end_commit         TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_work_started
    ON work_session (started_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_by_client
    ON work_session (client_instance_id, status, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_by_repo
    ON work_session (machine_id, tool, last_repo_path, status, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_active_sweep
    ON work_session (status, last_activity_at);

CREATE TABLE IF NOT EXISTS checkpoint (
    checkpoint_id      TEXT PRIMARY KEY,
    work_id            TEXT NOT NULL REFERENCES work_session(work_id),
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,

    type               TEXT NOT NULL,
    title              TEXT NOT NULL,
    body               TEXT,
    body_truncated     INTEGER NOT NULL DEFAULT 0,

    occurred_at        TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    source             TEXT NOT NULL,

    repo_path          TEXT,
    repo_name          TEXT,
    branch             TEXT,
    commit_sha         TEXT,
    dirty              INTEGER,
    dirty_file_count   INTEGER,
    dirty_count_capped INTEGER NOT NULL DEFAULT 0,

    files_json         TEXT,
    error_excerpt      TEXT,
    tags_json          TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ckp_work
    ON checkpoint (work_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_ckp_occurred
    ON checkpoint (occurred_at DESC);
"""

_SCRIPTS = {1: _V1}


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master"
        " WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if row is None:
        return 0
    result = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(result["v"] or 0)


def migrate(conn: sqlite3.Connection, now_iso: str) -> int:
    """미적용 버전을 순서대로 적용한다. 이미 최신이면 아무 일도 하지 않는다."""
    version = current_version(conn)
    for target in sorted(_SCRIPTS):
        if target <= version:
            continue
        conn.executescript(_SCRIPTS[target])
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (version, applied_at)"
            " VALUES (?, ?)",
            (target, now_iso),
        )
        version = target
    return version
