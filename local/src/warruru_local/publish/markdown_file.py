"""마크다운 파일 어댑터. 1순위 발행 대상이고 의존성이 0이다.

**마크다운이 정본이다.** 티스토리 같은 원격은 미러다 —
발행하면 원본 마크다운이 HTML 로 정규화되어 복원되지 않기 때문에
이 순서는 뒤집을 수 없다(`local/docs/adr/2026-08-18-publish-target.md`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from warruru_local.publish.base import PublishResult, PublishTarget

# 파일명에 쓸 수 없는 문자. 슬러그가 이미 정규화돼 있지만 한 겹 더 막는다 —
# 여기로 오는 값이 언제나 슬러그라는 보장은 이 모듈 밖에 있다.
# 점도 지운다. `slugify` 는 점을 남기지 않으므로 잃을 것이 없고,
# `..` 이 파일명에 남으면 읽는 사람이 경로 이탈을 의심하게 된다.
_UNSAFE = re.compile(r"[^\w-]", re.UNICODE)


class RepositoryPathError(ValueError):
    """저장소 안에 초안을 쓰려고 했다. 취향이 아니라 사고 방지 장치다."""


class MarkdownFileTarget(PublishTarget):
    """`~/.warruru/drafts/YYYY/MM/YYYY-MM-DD-{slug}.md` 에 쓴다.

    연·월로 나누는 것은 한 디렉터리에 파일이 수백 개 쌓이는 것을 막기 위해서다.
    31주면 글이 수십 편이고, 몇 년을 쓰면 그보다 많아진다.
    """

    name = "markdown_file"

    def __init__(self, root: Path, repo_root: Path | None = None) -> None:
        self._root = Path(root)
        self._repo_root = Path(repo_root).resolve() if repo_root else None
        self._guard(self._root)

    def _guard(self, path: Path) -> None:
        """저장소 안이면 예외를 던진다. **경고가 아니라 예외다.**

        경고는 로그에 묻히고, 묻히면 다음 `git add -A` 에서 사고가 난다.
        """
        if self._repo_root is None:
            return
        resolved = path.expanduser().resolve()
        if resolved == self._repo_root or self._repo_root in resolved.parents:
            raise RepositoryPathError(
                f"초안은 저장소 바깥에 써야 한다. 받은 경로: {resolved}"
                f" (저장소: {self._repo_root})"
            )

    def path_for(self, date: str, slug: str) -> Path:
        """`date` 는 로컬 날짜 `YYYY-MM-DD`. 경계 계산은 부르는 쪽이 한다."""
        safe = _UNSAFE.sub("-", slug).strip("-") or "misc"
        year, month = date[:4], date[5:7]
        return self._root / year / month / f"{date}-{safe}.md"

    def publish(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        visibility: str = "private",
        *,
        date: str,
        slug: str,
        topic: str | None = None,
        kinds: list[str] | None = None,
        source_record_ids: list[str] | None = None,
        status: str = "DRAFT",
    ) -> PublishResult:
        target = self.path_for(date, slug)
        self._guard(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        front = _front_matter(
            topic=topic or title,
            kinds=kinds or [],
            source_record_ids=source_record_ids or [],
            status=status,
        )
        target.write_text(front + markdown, encoding="utf-8")
        return PublishResult(target=self.name, path=str(target))


def _front_matter(
    topic: str, kinds: list[str], source_record_ids: list[str], status: str
) -> str:
    """파일만 열어도 무엇으로 조립됐는지 읽혀야 한다.

    마크다운이 정본이고 DB 는 그 정본을 찾아가는 색인이라는 순서와 같은 이유다.
    `topic` 은 원문이다 — 슬러그는 파일명에 이미 들어 있다.
    """
    lines = [
        "---",
        f"topic: {json.dumps(topic, ensure_ascii=False)}",
        f"kind: {json.dumps(sorted(set(kinds)), ensure_ascii=False)}",
        f"source_record_ids: {json.dumps(source_record_ids, ensure_ascii=False)}",
        f"status: {status}",
        "---",
        "",
    ]
    return "\n".join(lines)
