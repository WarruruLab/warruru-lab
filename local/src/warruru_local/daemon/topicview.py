"""주제 화면의 뷰 모델. 날짜 경계와 표시 문자열을 여기서 만든다.

라우트는 얇게 두고 판단은 여기에 모은다 — `dayview` 와 같은 자리다.
"""

from __future__ import annotations

from warruru_local.clock import local_day_bounds, parse_iso
from warruru_local.daemon import draft as draft_builder

# 1건뿐인 주제가 모이는 자리. 표기가 갈린 것을 눈에 띄게 하는 오타 교정 장치다.
# 병합 UI 는 만들지 않는다 — 남는 소수는 SQL 한 줄이 화면보다 싸다.
UNSORTED_MAX = 1

KIND_LABELS = {
    "EXPERIMENT": "실험",
    "TROUBLESHOOTING": "트러블슈팅",
    "TECH_CHOICE": "기술선택",
    "CONCEPT": "개념",
}


def _local_time(iso: str) -> str:
    """`16:40` 처럼 사람이 읽는 시각. 화면은 로컬 시간대로 보여준다."""
    return parse_iso(iso).astimezone().strftime("%H:%M")


def _group(row: dict) -> dict:
    return {
        "topic": row["topic"],
        "topic_slug": row["topic_slug"],
        "count": row["count"],
        # 모르는 kind 값도 그대로 보여준다. 기록을 거절하지 않기로 했으므로
        # 화면도 거절하지 않는다 — 오타는 배지에서 눈에 띈다.
        "kinds": [
            (KIND_LABELS.get(kind, kind or "미상"), count)
            for kind, count in sorted(row["kinds"].items())
        ],
        "last_time": _local_time(row["last_occurred_at"]),
    }


# 글 한 편을 쓰기에 있어야 하는 필드. 비어 있으면 그 절이 TODO 로 남는다.
MATERIAL_FIELDS = ("rationale", "outcome", "limitation", "interview")


def build_detail(ctx, topic_slug: str) -> dict | None:
    """한 주제의 전체 기록. **하루치가 아니다** — 글 한 편의 재료는 며칠에 걸친다.

    부족한 필드를 함께 센다. 초안 품질이 낮은 이유가 조립기가 아니라
    재료라는 사실을 [초안 만들기] 를 누르기 전에 보여줘야 다음 기록이 나아진다.
    """
    rows = ctx.records.list_records(topic_slug=topic_slug, limit=100)
    if not rows:
        return None

    # 목록은 최신순이지만 상세는 시간순이다. 읽는 순서가 곧 서사 순서다.
    rows = sorted(rows, key=lambda row: (row["occurred_at"], row["record_id"]))

    shortages = []
    for name in MATERIAL_FIELDS:
        blank = sum(1 for row in rows if not (row.get(name) or "").strip())
        if blank:
            shortages.append({"field": name, "blank": blank, "total": len(rows)})

    return {
        "topic": rows[-1]["topic"],
        "topic_slug": topic_slug,
        "count": len(rows),
        "records": [
            {
                "record_id": row["record_id"],
                "kind": KIND_LABELS.get(row["kind"], row["kind"] or "미상"),
                "title": row["title"],
                "body": row["body"],
                "time": _local_time(row["occurred_at"]),
                "date": row["occurred_at"][:10],
                "project": row["project"],
            }
            for row in rows
        ],
        "shortages": shortages,
    }


def build_draft(ctx, draft_id: str) -> dict | None:
    """초안 한 편. 남은 TODO 와 다듬기 프롬프트를 함께 준다.

    다듬기는 관문이 아니라 선택지다 — 붙여넣지 않고 자도 파일은 이미 있다.
    그래서 이 화면은 '해야 할 일' 이 아니라 '지금 상태' 를 보여준다.
    """
    row = ctx.records.get_draft(draft_id)
    if row is None or row.get("deleted_at"):
        return None

    markdown = row["markdown"] or ""
    return {
        "draft_id": row["draft_id"],
        "topic": row["topic"],
        "topic_slug": row["topic_slug"],
        "title": row["title"],
        "markdown": markdown,
        # 빈 자리가 곧 "면접에서 대답 못 할 부분" 목록이다. 세어서 보여준다.
        "todo_count": markdown.count(draft_builder.TODO),
        "file_path": row["file_path"],
        "status": row["status"],
        "published_url": row["published_url"],
        # 에이전트가 어느 글을 다듬는지 읽는 용도다. save_draft 의 인자가 아니다.
        "polish_prompt": (
            f"polish topic={row['topic_slug']} draft={row['draft_id']}"
        ),
    }


def build_index(ctx, date: str) -> dict:
    """그 날짜의 주제별 요약. 경계는 예외 없이 `local_day_bounds` 로 만든다.

    UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다.
    """
    start, end = local_day_bounds(date)
    rows = ctx.records.slug_summary(since=start, until=end)

    groups = [_group(row) for row in rows if row["count"] > UNSORTED_MAX]
    unsorted_rows = [_group(row) for row in rows if row["count"] <= UNSORTED_MAX]

    return {
        "date": date,
        "today_count": sum(row["count"] for row in rows),
        "groups": groups,
        "unsorted": unsorted_rows,
    }
