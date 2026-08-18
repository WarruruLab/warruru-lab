"""스키마 버전과 DDL. 데몬이 기동 시 순차 적용한다. 되돌리기는 없다.

v2 는 학습 기록 두 테이블을 더한다. `topic` 원문과 `topic_slug` 를 함께 두는 이유는,
원문은 사람이 적은 말이라 화면에 그대로 보여야 하고 집계는 표기 변형에 흔들리면
안 되기 때문이다. 집계·필터·글 생성은 예외 없이 slug 기준이다.

`measurement` / `tech_option` 정규화 테이블은 만들지 않는다. 정규화가 값을 하는 건
비교·집계 화면이 있을 때인데 MVP 에 그런 화면이 없다. 측정값과 기술 후보는
`body`·`outcome` 안의 텍스트로 받는다. 필요해지면 v3 스크립트 하나를 더하면 된다.
"""

from __future__ import annotations

import sqlite3

CURRENT_VERSION = 2

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

_V2 = """
CREATE TABLE IF NOT EXISTS learning_record (
    record_id          TEXT PRIMARY KEY,
    work_id            TEXT NOT NULL REFERENCES work_session(work_id),
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,

    kind               TEXT NOT NULL,
    topic              TEXT NOT NULL,
    topic_slug         TEXT NOT NULL,
    title              TEXT NOT NULL,
    body               TEXT NOT NULL,
    body_truncated     INTEGER NOT NULL DEFAULT 0,

    rationale          TEXT,
    outcome            TEXT,
    limitation         TEXT,
    interview          TEXT,

    project            TEXT,
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

    deleted_at         TEXT,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_record_occurred
    ON learning_record (occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_slug
    ON learning_record (topic_slug, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_work
    ON learning_record (work_id, occurred_at);

CREATE TABLE IF NOT EXISTS draft (
    draft_id           TEXT PRIMARY KEY,
    topic              TEXT NOT NULL,
    topic_slug         TEXT NOT NULL,
    kind_json          TEXT,
    title              TEXT NOT NULL,
    markdown           TEXT NOT NULL,
    markdown_truncated INTEGER NOT NULL DEFAULT 0,
    source_record_ids_json TEXT,

    file_path          TEXT,
    status             TEXT NOT NULL,
    published_url      TEXT,
    published_at       TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_draft_slug
    ON draft (topic_slug, updated_at DESC);
"""

_SCRIPTS = {1: _V1, 2: _V2}


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
