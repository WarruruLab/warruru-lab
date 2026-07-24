"""단일 인스턴스 잠금. 잠금을 잡지 못한 데몬은 즉시 종료한다.

프로세스가 죽으면 OS 가 잠금을 자동으로 푼다. pid 파일만 쓰는 방식과 달리
남은 파일 때문에 기동이 막히는 일이 없다.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # POSIX
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # Windows
    import msvcrt

    _HAS_FCNTL = False


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+b")
        try:
            if _HAS_FCNTL:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if _HAS_FCNTL:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            else:
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self._handle.close()
        self._handle = None
