"""날짜 화면의 표시 모델. 템플릿은 판단하지 않는다."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from warruru_local.clock import local_date_of, local_day_bounds, parse_iso

DATE_FORMAT = "%Y-%m-%d"


def _local_time(iso: str | None) -> str | None:
    if iso is None:
        return None
    return parse_iso(iso).astimezone().strftime("%H:%M")


def _loads(raw: str | None) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _checkpoint_view(row: dict) -> dict:
    return {
        "checkpoint_id": row["checkpoint_id"],
        "type": row["type"],
        "title": row["title"],
        "body": row["body"],
        "occurred_local": _local_time(row["occurred_at"]),
        "repo_name": row["repo_name"],
        "branch": row["branch"],
        "commit_short": (row["commit_sha"] or "")[:7] or None,
        "dirty": row["dirty"],
        "files": _loads(row["files_json"]),
        "error_excerpt": row["error_excerpt"],
        "tags": _loads(row["tags_json"]),
    }


def _work_view(ctx, row: dict, include_deleted: bool) -> dict:
    checkpoints = ctx.repo.list_checkpoints(row["work_id"], include_deleted)
    return {
        "work_id": row["work_id"],
        "title": row["title"] or "(제목 없음)",
        "title_origin": row["title_origin"],
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "origin": row["origin"],
        "started_local": _local_time(row["started_at"]),
        "ended_local": _local_time(row["ended_at"]),
        "repo_name": row["start_repo_name"],
        "branch": row["start_branch"],
        "result": row["result"],
        "limitations": row["limitations"],
        "next_steps": row["next_steps"],
        "type_counts": ctx.repo.count_types(row["work_id"]),
        "checkpoints": [_checkpoint_view(item) for item in checkpoints],
    }


def _group(views: list[tuple[str, dict]]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for tool, view in views:
        if tool not in groups:
            groups[tool] = []
            order.append(tool)
        groups[tool].append(view)
    return [{"tool": tool, "works": groups[tool]} for tool in order]


def _learning_views(ctx, start: str, end: str) -> list[dict]:
    """그날의 학습 기록. 시간순으로 읽는다 — 하루를 되짚는 순서다."""
    rows = ctx.records.list_records(since=start, until=end, limit=100)
    rows = sorted(rows, key=lambda row: (row["occurred_at"], row["record_id"]))
    return [
        {
            "record_id": row["record_id"],
            "kind": row["kind"],
            "topic": row["topic"],
            "topic_slug": row["topic_slug"],
            "title": row["title"],
            "time": _local_time(row["occurred_at"]),
        }
        for row in rows
    ]


def build_day(ctx, date_str: str, include_deleted: bool = False) -> dict:
    start, end = local_day_bounds(date_str)
    rows = (
        ctx.repo.list_deleted_works_between(start, end)
        if include_deleted
        else ctx.repo.list_works_between(start, end)
    )
    views = [(row["tool"], _work_view(ctx, row, include_deleted)) for row in rows]

    # 학습 기록은 작업·체크포인트와 성격이 다르지만 같은 하루에 속한다.
    # 날짜 화면은 '그날 무엇을 했나' 를 보는 자리라 둘 다 있어야 한다.
    # 삭제 화면에는 넣지 않는다 — 그 화면은 되살릴 것을 고르는 자리다.
    learnings = [] if include_deleted else _learning_views(ctx, start, end)

    day = datetime.strptime(date_str, DATE_FORMAT).date()
    hint = None
    if not views and not include_deleted:
        latest = ctx.repo.latest_work_started_before(end)
        hint = local_date_of(latest) if latest else None

    if include_deleted:
        # 세션은 살아 있는데 체크포인트만 삭제된 경우, 그 체크포인트는
        # list_deleted_works_between 에 담긴 어떤 work_view 에도 없다 —
        # 부모 세션 자체가 삭제되지 않았기 때문이다. 삭제 화면은 이런
        # "고아" 체크포인트도 보여줘야 하므로 여기서 채운다.
        orphans = ctx.repo.list_deleted_checkpoints_between(start, end)
        shown = {
            item["checkpoint_id"]
            for _, view in views
            for item in view["checkpoints"]
        }
        remaining = [row for row in orphans if row["checkpoint_id"] not in shown]
        if remaining:
            grouped: dict[str, list[dict]] = {}
            for row in remaining:
                grouped.setdefault(row["work_id"], []).append(row)
            for work_id, checkpoint_rows in grouped.items():
                parent = ctx.repo.get_work(work_id)
                if parent is None:
                    continue
                view = _work_view(ctx, parent, include_deleted=False)
                view["checkpoints"] = [_checkpoint_view(row) for row in checkpoint_rows]
                views.append((parent["tool"], view))

    return {
        "date": date_str,
        "prev_date": (day - timedelta(days=1)).strftime(DATE_FORMAT),
        "next_date": (day + timedelta(days=1)).strftime(DATE_FORMAT),
        "groups": _group(views),
        "learnings": learnings,
        "empty_hint": hint,
    }
