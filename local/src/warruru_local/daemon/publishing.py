"""발행 표시. 사람이 붙여넣고 돌아와 URL 을 적으면 여기로 온다.

본문은 건드리지 않는다 — 원격에 올라간 글과 로컬 정본이 어긋나면
어느 쪽이 맞는지 알 수 없다. 바뀌는 것은 상태와 URL 뿐이다.
"""

from __future__ import annotations

import json
import re

from pathlib import Path

from warruru_local.clock import local_date_of, to_iso
from warruru_local.publish.git_private_repo import (
    GitPrivateRepoTarget,
    NotPrivateError,
)

# front matter 의 status 한 줄만 바꾼다. 본문은 그대로 둔다.
_STATUS_LINE = re.compile(r"^status: .*$", re.MULTILINE)


class DraftNotFoundError(LookupError):
    pass


def mark_published(ctx, draft_id: str, url: str) -> dict:
    row = ctx.records.get_draft(draft_id)
    if row is None or row.get("deleted_at"):
        raise DraftNotFoundError(draft_id)

    now = to_iso(ctx.clock.now())
    updated = ctx.records.mark_published(draft_id, url.strip(), now)
    _rewrite_status(updated)
    return updated


def _rewrite_status(row: dict) -> None:
    """파일이 정본이다. DB 만 바꾸면 파일을 여는 사람이 옛 상태를 본다.

    파일이 사라졌으면 조용히 넘어간다 — 사람이 지웠을 수 있고,
    그 때문에 발행 표시가 실패하면 더 나쁘다.
    """
    path = row.get("file_path")
    if not path:
        return
    target = Path(path)
    if not target.exists():
        return
    text = target.read_text(encoding="utf-8")
    target.write_text(_STATUS_LINE.sub("status: PUBLISHED", text, count=1),
                      encoding="utf-8")


class PushUnavailableError(RuntimeError):
    """비공개 저장소로 밀어 넣을 수 없다. **사람이 고칠 수 있는 실패다.**

    설정이 없거나, 저장소가 비공개가 아니거나, 확인하지 못했을 때다.
    셋 다 무엇을 고쳐야 하는지 말해 줄 수 있으므로 500 으로 새어 나가면 안 된다.
    """


def push_to_repo(ctx, draft_id: str):
    """초안 파일을 비공개 git 저장소에 그대로 옮겨 커밋·푸시한다.

    **마크다운이 원본 그대로 간다.** 티스토리는 붙여넣는 순간 HTML 로
    정규화되어 복원되지 않는다 — 이쪽을 고른 이유가 그것이다(ADR 2026-08-28).
    """
    row = ctx.records.get_draft(draft_id)
    if row is None or row.get("deleted_at"):
        raise DraftNotFoundError(draft_id)

    root = ctx.settings.publish_repo
    if root is None:
        raise PushUnavailableError(
            "WARRURU_PUBLISH_REPO 가 설정되지 않았다"
        )

    target = GitPrivateRepoTarget(root, repo_root=ctx.settings.repo_root)
    try:
        return target.publish(
            title=row["title"],
            markdown=row["markdown"],
            date=local_date_of(to_iso(ctx.clock.now())),
            slug=row["topic_slug"],
            topic=row["topic"],
            kinds=json.loads(row["kind_json"] or "[]"),
            source_record_ids=json.loads(row["source_record_ids_json"] or "[]"),
            status=row["status"],
        )
    except NotPrivateError as error:
        raise PushUnavailableError(str(error)) from None
