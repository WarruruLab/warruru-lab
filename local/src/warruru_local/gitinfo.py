"""Git 스냅샷. 부가 정보이지 기록의 조건이 아니다.

어떤 실패도 예외로 새어 나가지 않는다. 실패하면 값이 비어 있을 뿐이다.
플래그 대신 값의 유무로 표현한다 — 플래그와 값이 어긋날 여지를 없앤다.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_NO_WINDOW = 0
if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows 에서 콘솔 창이 뜨지 않게 한다
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW


@dataclass(frozen=True)
class GitSnapshot:
    repo_path: str | None = None
    repo_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    dirty: bool | None = None
    dirty_file_count: int | None = None
    dirty_count_capped: bool = False

    @property
    def available(self) -> bool:
        return self.repo_path is not None

    def as_dict(self) -> dict | None:
        if not self.available:
            return None
        return {
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "commit": self.commit_sha,
            "dirty": self.dirty,
            "dirty_file_count": self.dirty_file_count,
        }


GitSnapshot.EMPTY = GitSnapshot()


class GitCollector:
    def __init__(
        self,
        timeout_seconds: float = 2.0,
        cache_ttl_seconds: float = 5.0,
        dirty_file_cap: int = 500,
        monotonic=time.monotonic,
    ) -> None:
        self._timeout = timeout_seconds
        self._ttl = cache_ttl_seconds
        self._cap = dirty_file_cap
        self._monotonic = monotonic
        self._cache: dict[str, tuple[float, GitSnapshot]] = {}

    def collect(self, path: str | None) -> GitSnapshot:
        if not path:
            return GitSnapshot.EMPTY
        if not Path(path).is_dir():
            return GitSnapshot.EMPTY

        try:
            now = self._monotonic()
        except Exception:
            return GitSnapshot.EMPTY

        cached = self._cache.get(path)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]

        snapshot = self._read(path, now)
        self._cache[path] = (now, snapshot)
        return snapshot

    def _read(self, path: str, started: float) -> GitSnapshot:
        toplevel = self._git(path, "rev-parse", "--show-toplevel", started=started)
        if toplevel is None:
            return GitSnapshot.EMPTY

        branch = self._git(path, "rev-parse", "--abbrev-ref", "HEAD", started=started)
        commit = self._git(path, "rev-parse", "HEAD", started=started)
        dirty, count, capped = self._read_status(path, started)

        return GitSnapshot(
            repo_path=toplevel,
            repo_name=Path(toplevel).name,
            branch=branch,
            commit_sha=commit,
            dirty=dirty,
            dirty_file_count=count,
            dirty_count_capped=capped,
        )

    def _read_status(
        self, path: str, started: float
    ) -> tuple[bool | None, int | None, bool]:
        output = self._git(path, "status", "--porcelain", started=started, allow_empty=True)
        if output is None:
            return None, None, False
        lines = [line for line in output.splitlines() if line.strip()]
        if len(lines) > self._cap:
            return True, self._cap, True
        return bool(lines), len(lines), False

    def _remaining(self, started: float) -> float:
        """남은 예산은 항상 '지금' 시각을 다시 재서 계산한다.

        앞선 git 호출이 시간을 오래 썼다면, 그만큼 뒤의 호출이 받는 예산은
        줄어들어야 한다. 얼어붙은 시각 두 개로 계산하면 절대 줄지 않는다.
        """
        try:
            now = self._monotonic()
        except Exception:
            return 0.0
        return self._timeout - (now - started)

    def _git(
        self, path: str, *args: str, started: float, allow_empty: bool = False
    ) -> str | None:
        """남은 예산이 없으면 즉시 포기한다."""
        command = [str(value) for value in args]
        budget = self._remaining(started)
        if budget <= 0:
            return None
        try:
            completed = subprocess.run(
                ["git", "-C", path, *command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=budget,
                creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        if completed.stdout is None:
            return None
        value = completed.stdout.strip()
        if not value and not allow_empty:
            return None
        return value
