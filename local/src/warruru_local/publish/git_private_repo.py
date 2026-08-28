"""비공개 git 저장소 어댑터. 티스토리 자동 발행 대신 고른 길이다.

캡차가 없고, 기존 ssh/gh 자격증명을 쓰고, **마크다운이 원본 그대로 남는다** —
티스토리는 붙여넣는 순간 HTML 로 정규화되어 복원되지 않는다
(`local/docs/adr/2026-08-18-publish-target.md`, 2026-08-28 개정).

**이 어댑터의 핵심은 git 이 아니라 '정말 비공개인가' 를 쓰기 전에 확인하는 것이다.**
이름만 private 이고 실제로는 public 인 저장소에 초안을 밀어 넣으면, 이 프로젝트가
처음부터 막으려던 사고가 그대로 난다. **확인할 수 없으면 쓰지 않는다** —
'아마 비공개일 것' 위에 사고 방지 장치를 얹을 수는 없다.

`sqlite3` 도 `warruru_local.store.*` 도 임포트하지 않는다.
`tests/test_publish_boundary.py` 가 소스를 AST 로 훑어 강제한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from warruru_local.publish.base import PublishResult, PublishTarget
from warruru_local.publish.markdown_file import MarkdownFileTarget

GIT_TIMEOUT = 20


class NotPrivateError(RuntimeError):
    """비공개임을 확인하지 못했다. **경고가 아니라 예외다.**

    경고는 로그에 묻히고, 묻히면 다음 push 에서 사고가 난다.
    """


def _run(args: list[str], cwd: Path) -> str:
    done = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True,
        check=True, timeout=GIT_TIMEOUT,
    )
    return done.stdout.strip()


def remote_of(root: Path) -> str | None:
    """`origin` 의 주소. 없으면 None — 그러면 공개 여부를 물을 대상이 없다."""
    try:
        return _run(["git", "remote", "get-url", "origin"], root) or None
    except (subprocess.SubprocessError, OSError):
        return None


def github_is_private(remote: str) -> bool | None:
    """GitHub 저장소면 `gh` 로 공개 여부를 묻는다.

    **True/False 와 None 을 구분한다.** None 은 '공개다' 가 아니라
    '모르겠다' 이고, 부르는 쪽은 그 둘을 같이 취급하지 않는다 —
    GitHub 이 아니거나 `gh` 가 없거나 로그인이 안 돼 있을 때가 None 이다.
    """
    slug = _github_slug(remote)
    if slug is None:
        return None
    try:
        answer = _run(
            ["gh", "repo", "view", slug, "--json", "isPrivate", "-q", ".isPrivate"],
            Path.cwd(),
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if answer == "true":
        return True
    if answer == "false":
        return False
    return None


def _github_slug(remote: str) -> str | None:
    """`git@github.com:me/notes.git` · `https://github.com/me/notes` → `me/notes`."""
    text = remote.strip()
    if text.startswith("git@github.com:"):
        text = text[len("git@github.com:"):]
    elif "github.com/" in text:
        text = text.split("github.com/", 1)[1]
    else:
        return None
    text = text.removesuffix(".git").strip("/")
    return text if text.count("/") == 1 else None


def _push(cwd: Path) -> None:
    _run(["git", "push"], cwd)


class GitPrivateRepoTarget(PublishTarget):
    """비공개 저장소의 `YYYY/MM/YYYY-MM-DD-{slug}.md` 에 쓰고 커밋·푸시한다.

    파일 배치는 `MarkdownFileTarget` 을 그대로 쓴다. 두 어댑터의 결과물이
    같은 모양이어야 나중에 한쪽에서 다른 쪽으로 옮길 때 경로를 다시 짜지 않는다.
    """

    name = "git_private_repo"

    def __init__(
        self,
        root,
        repo_root=None,
        is_private=None,
        push=None,
    ) -> None:
        self._root = Path(root)
        # warruru-lab 자신을 가리키면 여기서 멈춘다. MarkdownFileTarget 과 같은 이유다.
        self._file = MarkdownFileTarget(self._root, repo_root=repo_root)
        self._is_private = is_private or github_is_private
        self._push = push or _push

    def _assert_private(self) -> None:
        remote = remote_of(self._root)
        if remote is None:
            raise NotPrivateError(
                f"원격이 없어 공개 여부를 확인할 수 없다: {self._root}"
            )
        verdict = self._is_private(remote)
        if verdict is not True:
            # None(모르겠다)과 False(공개다)를 같이 막는다.
            reason = "공개 저장소다" if verdict is False else "공개 여부를 확인하지 못했다"
            raise NotPrivateError(f"{reason}: {remote}")

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
        # **쓰기 전에** 확인한다. 쓴 뒤에 확인하면 이미 디스크에 남는다.
        self._assert_private()

        written = self._file.publish(
            title=title, markdown=markdown, tags=tags, visibility=visibility,
            date=date, slug=slug, topic=topic, kinds=kinds,
            source_record_ids=source_record_ids, status=status,
        )
        path = Path(written.path)
        _run(["git", "add", "--", str(path.relative_to(self._root))], self._root)

        # 같은 초안을 두 번 밀어도 빈 커밋이 쌓이지 않게 한다.
        staged = _run(["git", "diff", "--cached", "--name-only"], self._root)
        if staged:
            _run(["git", "commit", "-q", "-m", f"draft: {date} {slug}"], self._root)

        pushed = True
        try:
            self._push(self._root)
        except (subprocess.SubprocessError, OSError):
            # 네트워크가 없을 수 있다. 커밋은 이미 남았으니 잃은 것은 없다.
            # 다만 **사실대로 보고한다** — 원격에 없는데 있다고 말하지 않는다.
            pushed = False

        return PublishResult(
            target=self.name, path=str(path), pushed=pushed,
        )
