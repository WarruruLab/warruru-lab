"""학습 기록의 저장과 조회.

기존 `repository.py` 는 이미 483줄에 메서드 28개다. 여기에 더 넣는 대신
옆 파일로 둔다 — `ctx.sessions` 가 이미 그렇게 분리돼 있어 구조와 어긋나지 않는다.
`insert` 멱등 · 구간 조회 · soft delete 패턴은 그 파일에서 그대로 가져왔다.

**이 클래스는 설정을 모른다.** 주차나 날짜를 스스로 계산하지 않고 ISO 구간만 받는다.
날짜 경계를 만드는 일은 `clock.local_day_bounds` 하나에만 있어야 하기 때문이다.
"""

from __future__ import annotations

import json
import sqlite3

from warruru_local import topics

# 한 번에 돌려주는 최대 건수. 이보다 크게 요청해도 여기서 잘린다.
LIMIT_MAX = 100
LIMIT_DEFAULT = 20




class RecordRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ── 쓰기 ───────────────────────────────────────────────────────

    def insert_record(
        self,
        *,
        record_id: str,
        work_id: str,
        machine_id: str,
        tool: str,
        kind: str,
        topic: str,
        topic_slug: str,
        title: str,
        body: str,
        body_truncated: bool,
        rationale: str | None,
        outcome: str | None,
        limitation: str | None,
        interview: str | None,
        project: str | None,
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
    ) -> tuple[dict, bool]:
        """멱등이다. spool 을 두 번 흡수해도 중복이 생기지 않는다.

        돌려주는 두 번째 값이 True 면 이미 있던 기록이다.
        """
        existing = self.get_record(record_id)
        if existing is not None:
            return existing, True

        self._conn.execute(
            "INSERT INTO learning_record ("
            " record_id, work_id, machine_id, tool,"
            " kind, topic, topic_slug, title, body, body_truncated,"
            " rationale, outcome, limitation, interview,"
            " project, occurred_at, recorded_at, source,"
            " repo_path, repo_name, branch, commit_sha,"
            " dirty, dirty_file_count, dirty_count_capped, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record_id, work_id, machine_id, tool,
                kind, topic, topic_slug, title, body,
                1 if body_truncated else 0,
                rationale, outcome, limitation, interview,
                project, occurred_at, recorded_at, source,
                repo_path, repo_name, branch, commit_sha,
                None if dirty is None else (1 if dirty else 0),
                dirty_file_count,
                1 if dirty_count_capped else 0,
                recorded_at,
            ),
        )
        return self.get_record(record_id), False

    # 나중에 채울 수 있는 필드. `record_id` 같은 식별자와 시각은 손대지 않는다.
    # `topic` 은 슬러그를 함께 고쳐야 하므로 아래에서 따로 다룬다 —
    # 다만 "비어 있을 때만" 규칙은 나머지와 **같은 곳에서** 지켜진다.
    FILLABLE = (
        "kind", "title", "body",
        "rationale", "outcome", "limitation", "interview",
    )

    def fill_record(self, record_id: str, values: dict) -> tuple[dict | None, list[str]]:
        """비어 있던 필드만 채운다. **이미 있는 값은 덮어쓰지 않는다.**

        힌트(`missing_fields` · `example_call`)가 "같은 툴을 다시 불러 채우라" 고
        말하는데 채울 경로가 없으면 그 장치 전체가 무의미하다. 이 메서드가 그 경로다.

        덮어쓰지 않는 이유는 둘이다 — spool 을 두 번 흡수해도 안전해야 하고,
        보강 호출이 앞서 적은 내용을 실수로 지우면 안 된다.
        `topic` 은 여기 없다. 바꾸면 슬러그가 갈라져 그 기록이 다른 주제로 이사한다.
        """
        existing = self.get_record(record_id)
        if existing is None:
            return None, []

        filled = []
        # topic 이 빈 기록은 슬러그가 `misc` 로 좌초하는데, 힌트가 topic 을
        # 채우라고 말하면서 채울 경로가 없으면 그 힌트는 영원히 도는 헛바퀴다.
        # 값이 있으면 절대 바꾸지 않는다 — 바꾸면 슬러그가 갈라져 기록이 이사한다.
        topic_update: tuple[str, str] | None = None
        incoming_topic = values.get("topic")
        if isinstance(incoming_topic, str) and incoming_topic.strip():
            if not (existing.get("topic") or "").strip():
                topic_update = (
                    incoming_topic.strip(), topics.slugify(incoming_topic.strip())
                )
                filled.append("topic")

        for name in self.FILLABLE:
            incoming = values.get(name)
            if isinstance(incoming, str):
                incoming = incoming.strip()
            if not incoming:
                continue
            current = existing.get(name)
            if current is not None and str(current).strip():
                continue
            filled.append(name)

        if not filled:
            return existing, []

        columns = [name for name in filled if name != "topic"]
        assignments = [f"{name} = ?" for name in columns]
        params: list = [str(values[name]).strip() for name in columns]
        if topic_update is not None:
            # 원문과 슬러그가 어긋난 행을 만들지 않는다. 한 UPDATE 안에서 함께 바꾼다.
            assignments += ["topic = ?", "topic_slug = ?"]
            params += list(topic_update)
        assignments = ", ".join(assignments)
        params.append(record_id)
        self._conn.execute(
            f"UPDATE learning_record SET {assignments} WHERE record_id = ?", params
        )
        return self.get_record(record_id), filled

    def soft_delete(self, record_id: str, now_iso: str) -> None:
        self._conn.execute(
            "UPDATE learning_record SET deleted_at = ? WHERE record_id = ?",
            (now_iso, record_id),
        )

    def restore(self, record_id: str) -> None:
        self._conn.execute(
            "UPDATE learning_record SET deleted_at = NULL WHERE record_id = ?",
            (record_id,),
        )

    # ── 읽기 ───────────────────────────────────────────────────────

    def get_record(self, record_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM learning_record WHERE record_id = ?", (record_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_records(
        self,
        *,
        topic_slug: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = LIMIT_DEFAULT,
        include_deleted: bool = False,
    ) -> list[dict]:
        """최신순. `until` 은 **배타적**이다 — `local_day_bounds` 의 끝이 다음날 자정이다."""
        where = []
        params: list = []
        if not include_deleted:
            where.append("deleted_at IS NULL")
        if topic_slug:
            where.append("topic_slug = ?")
            params.append(topic_slug)
        if since:
            where.append("occurred_at >= ?")
            params.append(since)
        if until:
            where.append("occurred_at < ?")
            params.append(until)

        clause = (" WHERE " + " AND ".join(where)) if where else ""
        # 0 을 1 로 올리지 않는다. 0 건을 달라는 요청에 1 건을 주면 거짓말이다.
        params.append(max(0, min(limit, LIMIT_MAX)))
        rows = self._conn.execute(
            f"SELECT * FROM learning_record{clause}"
            " ORDER BY occurred_at DESC, record_id DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def slug_summary(
        self, *, since: str | None = None, until: str | None = None
    ) -> list[dict]:
        """슬러그별 건수 · kind 별 건수 · 마지막 기록 시각 · 원문 topic.

        화면은 슬러그가 아니라 사람이 적은 말을 보여주므로 `topic` 원문도 함께 준다.
        같은 슬러그에 원문이 여럿이면 가장 최근 것을 쓴다.
        """
        where = ["deleted_at IS NULL"]
        params: list = []
        if since:
            where.append("occurred_at >= ?")
            params.append(since)
        if until:
            where.append("occurred_at < ?")
            params.append(until)
        clause = " WHERE " + " AND ".join(where)

        rows = self._conn.execute(
            "SELECT topic_slug, topic, kind, occurred_at"
            f" FROM learning_record{clause}"
            # record_id 까지 봐야 같은 시각의 두 기록에서 원문 topic 이
            # 매번 다르게 뽑히지 않는다. 한 턴 안의 기록은 시각이 같기 쉽다.
            " ORDER BY occurred_at DESC, record_id DESC",
            params,
        ).fetchall()

        summary: dict[str, dict] = {}
        for row in rows:
            slug = row["topic_slug"]
            entry = summary.get(slug)
            if entry is None:
                # 최신순으로 훑으므로 처음 만나는 것이 가장 최근이다.
                entry = summary[slug] = {
                    "topic_slug": slug,
                    "topic": row["topic"],
                    "count": 0,
                    "kinds": {},
                    "last_occurred_at": row["occurred_at"],
                }
            entry["count"] += 1
            entry["kinds"][row["kind"]] = entry["kinds"].get(row["kind"], 0) + 1

        return sorted(
            summary.values(),
            key=lambda item: (-item["count"], item["topic_slug"]),
        )

    # ── draft ─────────────────────────────────────────────────────

    def upsert_draft(
        self,
        *,
        draft_id: str,
        topic: str,
        topic_slug: str,
        kinds: list[str],
        title: str,
        markdown: str,
        markdown_truncated: bool,
        source_record_ids: list[str],
        file_path: str | None,
        now_iso: str,
    ) -> tuple[dict, bool]:
        """그 주제의 **가장 최근 미발행 초안**을 덮어쓰고, 없으면 만든다.

        조립기와 (나중에 붙을) `save_draft` 가 결국 여기로 모인다.
        발행된 초안은 건드리지 않는다 — 이미 티스토리에 올라간 글의 본문을
        말없이 바꾸면 로컬과 원격이 어긋난다.
        """
        existing = self._conn.execute(
            "SELECT * FROM draft"
            " WHERE topic_slug = ? AND status = 'DRAFT' AND deleted_at IS NULL"
            " ORDER BY updated_at DESC, draft_id DESC LIMIT 1",
            (topic_slug,),
        ).fetchone()

        kinds_json = json.dumps(sorted(set(kinds)), ensure_ascii=False)
        ids_json = json.dumps(source_record_ids, ensure_ascii=False)

        if existing is not None:
            self._conn.execute(
                "UPDATE draft SET topic = ?, kind_json = ?, title = ?,"
                " markdown = ?, markdown_truncated = ?, source_record_ids_json = ?,"
                " file_path = ?, updated_at = ? WHERE draft_id = ?",
                (topic, kinds_json, title, markdown,
                 1 if markdown_truncated else 0, ids_json, file_path, now_iso,
                 existing["draft_id"]),
            )
            return self.get_draft(existing["draft_id"]), True

        self._conn.execute(
            "INSERT INTO draft ("
            " draft_id, topic, topic_slug, kind_json, title, markdown,"
            " markdown_truncated, source_record_ids_json, file_path, status,"
            " created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)",
            (draft_id, topic, topic_slug, kinds_json, title, markdown,
             1 if markdown_truncated else 0, ids_json, file_path,
             now_iso, now_iso),
        )
        return self.get_draft(draft_id), False

    def mark_published(self, draft_id: str, url: str, now_iso: str) -> dict | None:
        """발행 사실을 남긴다. 본문은 건드리지 않는다 —
        원격에 올라간 글과 로컬 정본이 어긋나면 어느 쪽이 맞는지 알 수 없다.
        """
        self._conn.execute(
            "UPDATE draft SET status = 'PUBLISHED', published_url = ?,"
            " published_at = ?, updated_at = ? WHERE draft_id = ?",
            (url, now_iso, now_iso, draft_id),
        )
        return self.get_draft(draft_id)

    def published_slugs(self) -> set[str]:
        """이미 글로 낸 주제. 목록 화면이 체크 표시를 붙이는 데 쓴다."""
        rows = self._conn.execute(
            "SELECT DISTINCT topic_slug FROM draft"
            " WHERE status = 'PUBLISHED' AND deleted_at IS NULL"
        ).fetchall()
        return {row["topic_slug"] for row in rows}

    def get_draft(self, draft_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM draft WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        return dict(row) if row else None

    def similar_slugs(
        self, slug: str, limit: int = topics.SIMILAR_LIMIT
    ) -> list[str]:
        """비슷한 슬러그. **두 갈래를 본다.**

        (1) DB 에 이미 있는 `topic_slug`, (2) `topics.RECOMMENDED_SLUGS`.

        권장 상수까지 보는 이유는 첫날 때문이다. DB 만 보면 기록이 0건인 동안
        힌트가 항상 비는데, 힌트가 가장 필요한 순간이 바로 그때다.
        로드맵 문서의 슬러그를 함께 보면 첫 기록부터 한 갈래로 모인다.
        """
        target = (slug or "").strip()
        if len(target) < topics.SIMILAR_MIN:
            # match_slugs 가 어차피 빈 목록을 돌려준다. 기록 삽입 응답마다
            # 도는 가장 뜨거운 경로에서 전체 DISTINCT 스캔을 할 이유가 없다.
            return []
        known = {
            row["topic_slug"]
            for row in self._conn.execute(
                "SELECT DISTINCT topic_slug FROM learning_record"
                " WHERE deleted_at IS NULL"
            ).fetchall()
        }
        # 거르는 규칙은 topics.match_slugs 한 곳에만 있다.
        # SPOOL 경로(어댑터)와 여기가 다른 규칙을 쓰면 데몬을 켰을 때 힌트가 바뀐다.
        hits = topics.match_slugs(
            target, known | set(topics.RECOMMENDED_SLUGS)
        )
        # DB 에 있는 것을 먼저 — 이 사람이 실제로 쓰던 말이다.
        hits.sort(key=lambda candidate: (candidate not in known, candidate))
        return hits[:limit]
