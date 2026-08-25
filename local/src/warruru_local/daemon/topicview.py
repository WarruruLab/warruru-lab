"""주제 화면의 뷰 모델. 날짜 경계와 표시 문자열을 여기서 만든다.

라우트는 얇게 두고 판단은 여기에 모은다 — `dayview` 와 같은 자리다.
"""

from __future__ import annotations

from warruru_local import topics
from warruru_local.clock import (
    local_date_or_none,
    local_day_bounds,
    local_time_or_none,
)
from warruru_local.daemon import draft as draft_builder
from warruru_local.publish.tistory_clipboard import TistoryClipboardTarget

# 1건뿐인 주제가 모이는 자리. 표기가 갈린 것을 눈에 띄게 하는 오타 교정 장치다.
# 병합 UI 는 만들지 않는다 — 남는 소수는 SQL 한 줄이 화면보다 싸다.
UNSORTED_MAX = 1

KIND_LABELS = {
    "EXPERIMENT": "실험",
    "TROUBLESHOOTING": "트러블슈팅",
    "TECH_CHOICE": "기술선택",
    "CONCEPT": "개념",
}


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
        "last_time": local_time_or_none(row["last_occurred_at"]),
    }


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
    draft = ctx.records.latest_draft_of(topic_slug)

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
                "time": local_time_or_none(row["occurred_at"]),
                # 앞 10자를 자르면 그건 UTC 날짜다. KST 자정 직후 한 시간의
                # 기록이 전날로 적힌다 — 날짜 경계는 예외 없이 clock 을 거친다.
                "date": local_date_or_none(row["occurred_at"]),
                "project": row["project"],
                # 되짚어 읽는 자리는 여기다. 발행 본문에는 안 들어간다.
                "interview": row["interview"],
            }
            for row in rows
        ],
        "shortages": topics.shortages(rows),
        # 목록과 **같은 함수**를 쓴다. 두 화면이 따로 계산하면
        # 같은 주제를 두고 다른 막대를 그린다.
        "material": topics.material_fill(rows),
        # 막대가 4/4 여도 초안엔 빈 절이 남을 수 있다. 막대는 필드를,
        # 조립기는 kind 도 본다 — 누르기 전에 알아야 다음 기록이 나아진다.
        "empty_sections": draft_builder.empty_sections(rows),
        # 만들어 둔 초안이 있으면 돌아갈 길을 준다. 그 화면에 붙여넣기용
        # HTML 과 발행 폼이 있어서, 길이 없으면 다음 날 이어서 하려는
        # 사람은 다시 만들거나 포기한다.
        "draft_id": (draft or {}).get("draft_id"),
        "draft_status": (draft or {}).get("status"),
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
        # 붙여넣기용 HTML. 정본은 마크다운이고 이건 옮겨 담을 문자열일 뿐이다.
        "paste_html": TistoryClipboardTarget().publish(
            # 정본 파일에는 꼬리말이 남고 발행 본문에서는 빠진다.
            # 독자에게 rec_01M0… 은 아무 뜻이 없다.
            title=row["title"], markdown=draft_builder.body_only(markdown)
        ).body,
    }


def build_index(ctx, date: str) -> dict:
    """그 날짜의 주제별 요약. 경계는 예외 없이 `local_day_bounds` 로 만든다.

    UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다.
    """
    start, end = local_day_bounds(date)
    rows = ctx.records.slug_summary(since=start, until=end)

    published = ctx.records.published_slugs()

    # 재료 막대의 재료. 슬러그마다 따로 물으면 주제 수만큼 질의가 나가므로
    # 하루치를 **한 번** 읽어 파이썬에서 접는다. 하루 기록은 많아야 수십 건이다.
    by_slug: dict[str, list[dict]] = {}
    for record in ctx.records.list_records(since=start, until=end, limit=100):
        by_slug.setdefault(record["topic_slug"], []).append(record)

    def _with_flag(row: dict) -> dict:
        entry = _group(row)
        entry["published"] = row["topic_slug"] in published
        entry["material"] = topics.material_fill(by_slug.get(row["topic_slug"], []))
        return entry

    groups = [_with_flag(row) for row in rows if row["count"] > UNSORTED_MAX]
    unsorted_rows = [_with_flag(row) for row in rows if row["count"] <= UNSORTED_MAX]

    return {
        "date": date,
        "today_count": sum(row["count"] for row in rows),
        "groups": groups,
        "unsorted": unsorted_rows,
    }
