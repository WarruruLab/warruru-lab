"""초안 만들기. 조립기와 발행 어댑터를 잇는 얇은 층이다.

라우트는 얇게, 판단은 여기에. HTTP 와 웹 폼이 같은 함수를 부른다 —
갈라지면 두 경로의 동작이 조용히 달라진다.
"""

from __future__ import annotations

from warruru_local import ids, limits, paths
from warruru_local.clock import local_date_of, to_iso
from warruru_local.daemon import draft as draft_builder
from warruru_local.publish.markdown_file import MarkdownFileTarget


class NoRecordsError(ValueError):
    """재료가 없다. 빈 파일을 조용히 쓰는 것보다 거절하는 편이 낫다."""


def create(ctx, topic_slug: str) -> dict:
    """그 주제의 기록으로 초안을 조립하고, 파일과 행을 함께 남긴다."""
    records = ctx.records.list_records(topic_slug=topic_slug, limit=100)
    if not records:
        raise NoRecordsError(topic_slug)

    # 조립기와 **같은 순서**로 세운다. front matter 의 source_record_ids 가
    # 본문에 나오는 순서와 다르면, 파일을 읽는 사람이 둘을 맞춰 보다 헷갈린다.
    records = sorted(
        records, key=lambda row: (row.get("occurred_at") or "", row["record_id"])
    )

    markdown = draft_builder.build(records)
    markdown, truncated = limits.clamp_text(markdown, limits.BODY_MAX)

    now = to_iso(ctx.clock.now())
    # 파일명의 날짜는 **오늘**이다. 기록의 날짜가 아니다 —
    # 한 주제의 기록이 며칠에 걸치므로 어느 하루를 고를 근거가 없고,
    # "언제 쓴 글인가" 가 파일을 찾을 때 쓰는 단서다.
    date = local_date_of(now)
    # 가장 최근 기록의 원문을 제목으로 쓴다. 조립기도 같은 것을 고른다.
    topic = records[-1]["topic"]

    # `drafts_root` 가 None 이면 정해진 자리다. 해석은 여기 한 곳에서 한다.
    root = ctx.settings.drafts_root or paths.drafts_dir(ctx.settings.home)
    target = MarkdownFileTarget(root, repo_root=ctx.settings.repo_root)
    result = target.publish(
        title=topic,
        markdown=markdown,
        date=date,
        slug=topic_slug,
        topic=topic,
        kinds=[row["kind"] for row in records],
        source_record_ids=[row["record_id"] for row in records],
        status="DRAFT",
    )

    row, updated = ctx.records.upsert_draft(
        draft_id=ids.new_id("drf"),
        topic=topic,
        topic_slug=topic_slug,
        kinds=[row["kind"] for row in records],
        title=topic,
        markdown=markdown,
        markdown_truncated=truncated,
        source_record_ids=[row["record_id"] for row in records],
        file_path=result.path,
        now_iso=now,
    )
    return {
        "draft_id": row["draft_id"],
        "topic_slug": row["topic_slug"],
        "title": row["title"],
        "status": row["status"],
        "file_path": row["file_path"],
        "source_record_count": len(records),
        "updated": updated,
    }
