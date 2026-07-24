"""맥락 조회. 에이전트가 그대로 읽는 요약과 구조화 목록을 함께 준다."""

from __future__ import annotations

from warruru_local.clock import local_date_of, local_day_bounds, to_iso

RECENT_LIMIT = 5
MAX_WORKS = 30


def build_context(ctx, date_str: str | None, tool: str | None, limit: int) -> dict:
    date_value = date_str or local_date_of(to_iso(ctx.clock.now()))
    start, end = local_day_bounds(date_value)
    capped = max(1, min(limit, MAX_WORKS))

    works = []
    for row in ctx.repo.list_works_between(start, end):
        if tool and row["tool"] != tool:
            continue
        works.append(_summarize(ctx, row))
        if len(works) >= capped:
            break

    return {
        "date": date_value,
        "summary_markdown": _render(date_value, works),
        "works": works,
    }


def _summarize(ctx, row: dict) -> dict:
    checkpoints = ctx.repo.list_checkpoints(row["work_id"])
    recent = [
        {
            "type": item["type"],
            "title": item["title"],
            "occurred_at": item["occurred_at"],
        }
        for item in checkpoints[-RECENT_LIMIT:]
    ]
    return {
        "work_id": row["work_id"],
        "tool": row["tool"],
        "title": row["title"],
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "repo_name": row["start_repo_name"],
        "branch": row["start_branch"],
        "type_counts": ctx.repo.count_types(row["work_id"]),
        "recent_checkpoints": recent,
    }


def _render(date_value: str, works: list[dict]) -> str:
    if not works:
        return f"# {date_value}\n\n기록 없음.\n"

    lines = [f"# {date_value}", ""]
    by_tool: dict[str, list[dict]] = {}
    for work in works:
        by_tool.setdefault(work["tool"], []).append(work)

    for tool_name, items in by_tool.items():
        lines.append(f"## {tool_name}")
        lines.append("")
        for work in items:
            title = work["title"] or "(제목 없음)"
            counts = " ".join(
                f"{name} {count}" for name, count in work["type_counts"].items()
            )
            lines.append(f"- **{title}** — {work['status']}")
            if work["repo_name"]:
                lines.append(f"  - {work['repo_name']} / {work['branch'] or '-'}")
            if counts:
                lines.append(f"  - {counts}")
            for item in work["recent_checkpoints"]:
                lines.append(f"  - {item['type']}: {item['title']}")
        lines.append("")
    return "\n".join(lines)
