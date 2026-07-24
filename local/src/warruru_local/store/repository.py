"""모든 SQL 을 독점한다. 다른 모듈은 SQL 문자열을 쓰지 않는다."""

from __future__ import annotations

import json
import sqlite3


def _as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # machine
    # ------------------------------------------------------------------

    def ensure_machine(
        self, machine_id: str, hostname: str, os_name: str, now_iso: str
    ) -> dict:
        """없으면 만들고, 있으면 처음 값을 그대로 둔다."""
        self._conn.execute(
            "INSERT OR IGNORE INTO machine (machine_id, hostname, os, created_at)"
            " VALUES (?, ?, ?, ?)",
            (machine_id, hostname, os_name, now_iso),
        )
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM machine WHERE machine_id = ?", (machine_id,)
            ).fetchone()
        )

    # ------------------------------------------------------------------
    # client_instance
    # ------------------------------------------------------------------

    def get_client(self, client_instance_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM client_instance WHERE client_instance_id = ?",
                (client_instance_id,),
            ).fetchone()
        )

    def ensure_client(
        self,
        client_instance_id: str,
        machine_id: str,
        tool: str,
        client_name: str | None,
        client_version: str | None,
        cwd: str | None,
        now_iso: str,
    ) -> dict:
        """처음 보는 대화면 만든다. 별도 등록 호출이 필요 없다."""
        self._conn.execute(
            "INSERT OR IGNORE INTO client_instance ("
            " client_instance_id, machine_id, tool, client_name, client_version,"
            " cwd, started_at, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                client_instance_id,
                machine_id,
                tool,
                client_name,
                client_version,
                cwd,
                now_iso,
                now_iso,
            ),
        )
        if cwd is not None:
            self._conn.execute(
                "UPDATE client_instance SET cwd = ? WHERE client_instance_id = ?",
                (cwd, client_instance_id),
            )
        return self.get_client(client_instance_id)

    def close_client(self, client_instance_id: str, now_iso: str) -> None:
        self._conn.execute(
            "UPDATE client_instance SET closed_at = ?"
            " WHERE client_instance_id = ? AND closed_at IS NULL",
            (now_iso, client_instance_id),
        )

    # ------------------------------------------------------------------
    # work_session
    # ------------------------------------------------------------------

    def get_work(self, work_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session WHERE work_id = ?", (work_id,)
            ).fetchone()
        )

    def insert_work(
        self,
        *,
        work_id: str,
        machine_id: str,
        client_instance_id: str | None,
        tool: str,
        title: str | None,
        title_origin: str | None,
        goal: str | None,
        origin: str,
        started_at: str,
        repo_path: str | None,
        repo_name: str | None,
        branch: str | None,
        commit_sha: str | None,
        now_iso: str,
    ) -> tuple[dict, bool]:
        """멱등이다. 같은 식별자가 이미 있으면 기존 행과 True 를 준다."""
        existing = self.get_work(work_id)
        if existing is not None:
            return existing, True

        self._conn.execute(
            "INSERT INTO work_session ("
            " work_id, machine_id, client_instance_id, tool,"
            " title, title_origin, goal,"
            " status, origin,"
            " started_at, last_activity_at,"
            " start_repo_path, start_repo_name, start_branch, start_commit,"
            " last_repo_path, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                work_id, machine_id, client_instance_id, tool,
                title, title_origin, goal,
                origin,
                started_at, started_at,
                repo_path, repo_name, branch, commit_sha,
                repo_path, now_iso, now_iso,
            ),
        )
        return self.get_work(work_id), False

    def promote_work(
        self,
        *,
        work_id: str,
        title: str | None,
        goal: str | None,
        started_at: str,
        repo_path: str | None,
        repo_name: str | None,
        branch: str | None,
        commit_sha: str | None,
        now_iso: str,
    ) -> dict:
        """자동으로 만들어 둔 자리를 사용자가 시작한 세션으로 올린다.

        체크포인트가 start_work 보다 먼저 도착하면 그 식별자로 INFERRED 세션이
        생긴다(F-02). 뒤늦게 온 start_work 가 아무것도 하지 않으면 사용자가 적은
        제목·목표·시작 시각이 통째로 사라지고, 확인된 작업이 시스템 추측으로
        남는다.

        강등은 절대 하지 않는다. EXPLICIT 세션과 사용자가 붙인 제목은 WHERE 로
        걸러 이 함수를 잘못 불러도 값이 내려가지 않게 한다.
        """
        self._conn.execute(
            "UPDATE work_session SET"
            " origin = 'EXPLICIT',"
            " title = COALESCE(?, title),"
            " title_origin = CASE WHEN ? IS NULL THEN title_origin ELSE 'USER' END,"
            " goal = COALESCE(?, goal),"
            " started_at = ?,"
            " start_repo_path = COALESCE(?, start_repo_path),"
            " start_repo_name = COALESCE(?, start_repo_name),"
            " start_branch = COALESCE(?, start_branch),"
            " start_commit = COALESCE(?, start_commit),"
            " updated_at = ?"
            " WHERE work_id = ? AND origin = 'INFERRED'"
            "   AND (title_origin IS NULL OR title_origin <> 'USER')",
            (
                title, title, goal, started_at,
                repo_path, repo_name, branch, commit_sha,
                now_iso, work_id,
            ),
        )
        return self.get_work(work_id)

    def touch_work(self, work_id: str, now_iso: str, repo_path: str | None) -> None:
        """마지막 활동 시각을 올린다. 저장소가 None 이면 기존 값을 유지한다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " last_activity_at = ?,"
            " last_repo_path = COALESCE(?, last_repo_path),"
            " updated_at = ?"
            " WHERE work_id = ?",
            (now_iso, repo_path, now_iso, work_id),
        )

    def set_work_title(self, work_id: str, title: str) -> None:
        """제목이 없는 세션에만 붙인다. 이미 있으면 건드리지 않는다."""
        self._conn.execute(
            "UPDATE work_session SET title = ?, title_origin = 'DERIVED'"
            " WHERE work_id = ? AND title IS NULL",
            (title, work_id),
        )

    def find_active_by_client(self, client_instance_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session"
                " WHERE client_instance_id = ? AND status = 'ACTIVE'"
                "   AND deleted_at IS NULL"
                " ORDER BY started_at DESC LIMIT 1",
                (client_instance_id,),
            ).fetchone()
        )

    def find_active_by_client_ids(self, client_instance_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE client_instance_id = ? AND status = 'ACTIVE'"
            "   AND deleted_at IS NULL",
            (client_instance_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def find_active_by_repo(
        self, machine_id: str, tool: str, repo_path: str, since_iso: str
    ) -> dict | None:
        """어댑터가 재기동되어 대화 식별자가 바뀐 경우를 위한 경로다."""
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session"
                " WHERE machine_id = ? AND tool = ? AND last_repo_path = ?"
                "   AND status = 'ACTIVE' AND deleted_at IS NULL"
                "   AND last_activity_at >= ?"
                " ORDER BY last_activity_at DESC LIMIT 1",
                (machine_id, tool, repo_path, since_iso),
            ).fetchone()
        )

    def finish_work(
        self,
        *,
        work_id: str,
        result: str | None,
        limitations: str | None,
        next_steps: str | None,
        ended_at: str,
        repo_path: str | None,
        branch: str | None,
        commit_sha: str | None,
        now_iso: str,
    ) -> dict:
        """자동 마감된 세션에도 쓸 수 있다. 상태를 FINISHED 로 덮는다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " status = 'FINISHED', ended_reason = 'USER_FINISH', ended_at = ?,"
            " result = COALESCE(?, result),"
            " limitations = COALESCE(?, limitations),"
            " next_steps = COALESCE(?, next_steps),"
            " end_repo_path = COALESCE(?, end_repo_path),"
            " end_branch = COALESCE(?, end_branch),"
            " end_commit = COALESCE(?, end_commit),"
            " updated_at = ?"
            " WHERE work_id = ?",
            (
                ended_at, result, limitations, next_steps,
                repo_path, branch, commit_sha, now_iso, work_id,
            ),
        )
        return self.get_work(work_id)

    def auto_close_work(
        self, work_id: str, ended_reason: str, ended_at: str, now_iso: str
    ) -> dict:
        """종료 Git 스냅샷은 수집하지 않는다. 지금 읽은 값은 그 작업의 결과가 아니다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " status = 'AUTO_CLOSED', ended_reason = ?, ended_at = ?, updated_at = ?"
            " WHERE work_id = ? AND status = 'ACTIVE'",
            (ended_reason, ended_at, now_iso, work_id),
        )
        return self.get_work(work_id)

    def find_stale_active(self, before_iso: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE status = 'ACTIVE' AND last_activity_at < ?"
            "   AND deleted_at IS NULL",
            (before_iso,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # checkpoint
    # ------------------------------------------------------------------

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM checkpoint WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
        )

    def insert_checkpoint(
        self,
        *,
        checkpoint_id: str,
        work_id: str,
        machine_id: str,
        tool: str,
        type: str,
        title: str,
        body: str | None,
        body_truncated: bool,
        occurred_at: str,
        recorded_at: str,
        source: str,
        repo_path: str | None,
        repo_name: str | None,
        branch: str | None,
        commit_sha: str | None,
        dirty: bool | None,
        dirty_file_count: int | None,
        dirty_count_capped: bool,
        files: list[str] | None,
        error_excerpt: str | None,
        tags: list[str] | None,
    ) -> tuple[dict, bool]:
        """멱등이다. spool 을 두 번 흡수해도 중복이 생기지 않는다."""
        existing = self.get_checkpoint(checkpoint_id)
        if existing is not None:
            return existing, True

        self._conn.execute(
            "INSERT INTO checkpoint ("
            " checkpoint_id, work_id, machine_id, tool,"
            " type, title, body, body_truncated,"
            " occurred_at, recorded_at, source,"
            " repo_path, repo_name, branch, commit_sha,"
            " dirty, dirty_file_count, dirty_count_capped,"
            " files_json, error_excerpt, tags_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?)",
            (
                checkpoint_id, work_id, machine_id, tool,
                type, title, body, 1 if body_truncated else 0,
                occurred_at, recorded_at, source,
                repo_path, repo_name, branch, commit_sha,
                None if dirty is None else (1 if dirty else 0),
                dirty_file_count,
                1 if dirty_count_capped else 0,
                json.dumps(files or [], ensure_ascii=False),
                error_excerpt,
                json.dumps(tags or [], ensure_ascii=False),
                recorded_at,
            ),
        )
        return self.get_checkpoint(checkpoint_id), False

    def list_checkpoints(
        self, work_id: str, include_deleted: bool = False
    ) -> list[dict]:
        """발생 시각 오름차순. 순번을 두지 않고 시각으로 정렬한다.

        작업 삭제는 체크포인트 행에 deleted_at 을 쓰지 않는다. 기본 조회는
        상위 work_session 의 deleted_at 도 함께 확인해 하위 행을 감춘다.
        include_deleted=True 는 상위 삭제 여부와 무관하게 전부 준다(삭제
        목록 화면이 이 전체 집합에 기대고 있다).
        """
        if include_deleted:
            rows = self._conn.execute(
                "SELECT * FROM checkpoint"
                " WHERE work_id = ?"
                " ORDER BY occurred_at ASC, created_at ASC, checkpoint_id ASC",
                (work_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT checkpoint.* FROM checkpoint"
                " JOIN work_session ON work_session.work_id = checkpoint.work_id"
                " WHERE checkpoint.work_id = ?"
                "   AND checkpoint.deleted_at IS NULL"
                "   AND work_session.deleted_at IS NULL"
                " ORDER BY checkpoint.occurred_at ASC, checkpoint.created_at ASC,"
                "   checkpoint.checkpoint_id ASC",
                (work_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_checkpoints(self, work_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM checkpoint"
            " WHERE work_id = ? AND deleted_at IS NULL",
            (work_id,),
        ).fetchone()
        return int(row["c"])

    def count_types(self, work_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) AS c FROM checkpoint"
            " WHERE work_id = ? AND deleted_at IS NULL"
            " GROUP BY type",
            (work_id,),
        ).fetchall()
        return {row["type"]: int(row["c"]) for row in rows}

    # ------------------------------------------------------------------
    # 날짜 조회
    # ------------------------------------------------------------------

    def list_works_between(
        self, start_iso: str, end_iso: str, include_deleted: bool = False
    ) -> list[dict]:
        """세션은 시작 시각 기준으로 그 날짜에 속한다. 끝 경계는 배타적이다."""
        condition = "" if include_deleted else " AND deleted_at IS NULL"
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            f" WHERE started_at >= ? AND started_at < ?{condition}"
            " ORDER BY started_at DESC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_deleted_works_between(self, start_iso: str, end_iso: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE started_at >= ? AND started_at < ? AND deleted_at IS NOT NULL"
            " ORDER BY started_at DESC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_deleted_checkpoints_between(
        self, start_iso: str, end_iso: str
    ) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM checkpoint"
            " WHERE occurred_at >= ? AND occurred_at < ? AND deleted_at IS NOT NULL"
            " ORDER BY occurred_at ASC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def latest_work_started_before(self, iso: str) -> str | None:
        row = self._conn.execute(
            "SELECT started_at FROM work_session"
            " WHERE started_at < ? AND deleted_at IS NULL"
            " ORDER BY started_at DESC LIMIT 1",
            (iso,),
        ).fetchone()
        return row["started_at"] if row is not None else None

    # ------------------------------------------------------------------
    # 삭제와 복구 — 물리 삭제하지 않는다
    # ------------------------------------------------------------------

    def soft_delete_work(self, work_id: str, now_iso: str) -> None:
        """하위 체크포인트 행은 건드리지 않는다. 조회가 상위 삭제를 함께 본다."""
        self._conn.execute(
            "UPDATE work_session SET deleted_at = ?, updated_at = ?"
            " WHERE work_id = ? AND deleted_at IS NULL",
            (now_iso, now_iso, work_id),
        )

    def restore_work(self, work_id: str) -> None:
        self._conn.execute(
            "UPDATE work_session SET deleted_at = NULL WHERE work_id = ?", (work_id,)
        )

    def soft_delete_checkpoint(self, checkpoint_id: str, now_iso: str) -> None:
        self._conn.execute(
            "UPDATE checkpoint SET deleted_at = ?"
            " WHERE checkpoint_id = ? AND deleted_at IS NULL",
            (now_iso, checkpoint_id),
        )

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        self._conn.execute(
            "UPDATE checkpoint SET deleted_at = NULL WHERE checkpoint_id = ?",
            (checkpoint_id,),
        )
