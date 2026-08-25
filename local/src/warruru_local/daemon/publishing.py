"""발행 표시. 사람이 붙여넣고 돌아와 URL 을 적으면 여기로 온다.

본문은 건드리지 않는다 — 원격에 올라간 글과 로컬 정본이 어긋나면
어느 쪽이 맞는지 알 수 없다. 바뀌는 것은 상태와 URL 뿐이다.
"""

from __future__ import annotations

import re

from pathlib import Path

from warruru_local.clock import to_iso

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
