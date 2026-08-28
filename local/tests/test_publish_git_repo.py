"""`GitPrivateRepoTarget` — 초안을 비공개 git 저장소에 밀어 넣는다.

**이 어댑터의 핵심은 git 이 아니라 '정말 비공개인가' 를 쓰기 전에 확인하는 것이다.**
이름만 private 이고 실제로는 public 인 저장소에 초안을 밀어 넣으면,
이 프로젝트가 처음부터 막으려던 사고가 그대로 난다.
확인할 수 없으면 **쓰지 않는다.** 경고하고 쓰는 것은 답이 아니다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from warruru_local.publish.git_private_repo import (
    GitPrivateRepoTarget,
    NotPrivateError,
)
from warruru_local.publish.markdown_file import RepositoryPathError


def _repo(path: Path, remote: str | None = "git@github.com:me/notes.git") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=path, check=True)
    return path


def _target(root, *, private=True, pushed=True, repo_root=None):
    """git 호출과 비공개 판정을 주입한다. 네트워크에 나가지 않는다."""
    return GitPrivateRepoTarget(
        root,
        repo_root=repo_root,
        is_private=lambda remote: private,
        push=(lambda cwd: None) if pushed else _boom,
    )


def _boom(cwd):
    raise subprocess.CalledProcessError(1, ["git", "push"])


def _publish(target, **extra):
    kw = dict(title="제목", markdown="# 제목\n\n본문",
              date="2026-08-28", slug="connection-pool")
    kw.update(extra)
    return target.publish(**kw)


# ── 비공개 확인이 먼저다 ───────────────────────────────────────────

def test_비공개가_아니면_쓰지_않는다(tmp_path):
    """확인 결과가 '공개' 면 파일을 만들기 전에 멈춘다."""
    root = _repo(tmp_path / "notes")
    with pytest.raises(NotPrivateError):
        _publish(_target(root, private=False))
    assert list(root.rglob("*.md")) == []


def test_확인할_수_없으면_쓰지_않는다(tmp_path):
    """gh 가 없거나 GitHub 이 아니면 판정 불가다. 그때도 쓰지 않는다 —
    '아마 비공개일 것' 위에 이 프로젝트의 사고 방지 장치를 얹을 수 없다.
    """
    root = _repo(tmp_path / "notes")
    target = GitPrivateRepoTarget(root, is_private=lambda remote: None,
                                  push=lambda cwd: None)
    with pytest.raises(NotPrivateError):
        _publish(target)
    assert list(root.rglob("*.md")) == []


def test_원격이_없으면_쓰지_않는다(tmp_path):
    """원격이 없으면 공개 여부를 물을 대상이 없다."""
    root = _repo(tmp_path / "notes", remote=None)
    with pytest.raises(NotPrivateError):
        _publish(_target(root))


def test_저장소_안이면_쓰지_않는다(tmp_path):
    """warruru-lab 자신을 가리키면 MarkdownFileTarget 과 같은 이유로 막는다."""
    lab = _repo(tmp_path / "lab")
    with pytest.raises(RepositoryPathError):
        _target(lab / "sub", repo_root=lab)


# ── 밀어 넣기 ──────────────────────────────────────────────────────

def test_파일을_쓰고_커밋한다(tmp_path):
    root = _repo(tmp_path / "notes")
    result = _publish(_target(root))

    written = Path(result.path)
    assert written.exists()
    assert written.relative_to(root).parts[:2] == ("2026", "08")
    assert "본문" in written.read_text(encoding="utf-8")

    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    assert "connection-pool" in log
    assert result.pushed is True


def test_커밋이_비어_있으면_커밋하지_않는다(tmp_path):
    """같은 초안을 두 번 밀어도 빈 커밋이 쌓이지 않는다."""
    root = _repo(tmp_path / "notes")
    _publish(_target(root))
    _publish(_target(root))
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=root,
                           capture_output=True, text=True, check=True).stdout.strip()
    assert count == "1"


def test_푸시가_실패해도_커밋은_남는다(tmp_path):
    """네트워크가 없을 수 있다. 커밋까지는 끝내고 사실대로 보고한다 —
    '밀어 넣었다' 고 말해 놓고 원격에 없는 것이 가장 나쁘다.
    """
    root = _repo(tmp_path / "notes")
    result = _publish(_target(root, pushed=False))
    assert result.pushed is False
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=root,
                           capture_output=True, text=True, check=True).stdout.strip()
    assert count == "1"


def test_원본_마크다운이_그대로_남는다(tmp_path):
    """티스토리는 HTML 로 정규화해 복원이 안 된다. 이쪽을 고른 이유가 이것이다."""
    root = _repo(tmp_path / "notes")
    body = "# 제목\n\n- 목록\n\n```python\nprint('x')\n```\n"
    result = _publish(_target(root), markdown=body)
    assert body in Path(result.path).read_text(encoding="utf-8")
