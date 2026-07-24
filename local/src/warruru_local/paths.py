"""파일 시스템 레이아웃. 플랫폼에 하드코딩하지 않는다."""

from __future__ import annotations

import os
from pathlib import Path

_SUBDIRS = ("config", "spool", "spool/absorbed", "logs", "run")


def warruru_home() -> Path:
    override = os.environ.get("WARRURU_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".warruru"


def ensure_layout(home: Path) -> None:
    """필요한 디렉터리만 만든다. 후속 단계용 디렉터리는 만들지 않는다."""
    for sub in _SUBDIRS:
        (home / sub).mkdir(parents=True, exist_ok=True)


def db_path(home: Path) -> Path:
    return home / "warruru.db"


def config_dir(home: Path) -> Path:
    return home / "config"


def spool_dir(home: Path) -> Path:
    return home / "spool"


def absorbed_dir(home: Path) -> Path:
    return home / "spool" / "absorbed"


def dead_letter_dir(home: Path) -> Path:
    """몇 번을 다시 시도해도 반영되지 않는 봉투를 치워 두는 곳.

    미리 만들지 않는다. 비어 있는 채로 보이면 사용자가 무언가 잃었다고
    오해한다. 실제로 봉투를 치울 때만 생긴다.
    """
    return home / "spool" / "dead-letter"


def logs_dir(home: Path) -> Path:
    return home / "logs"


def run_dir(home: Path) -> Path:
    return home / "run"
