"""회전 파일 로그. 기록이 안 될 때 사용자가 원인을 찾을 수 있어야 한다."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from warruru_local import paths

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def setup_logging(home: Path, name: str, level: str = "INFO") -> logging.Logger:
    """`name` 은 'daemon' 또는 'mcp'. 파일은 logs/{name}.log 다."""
    logger = logging.getLogger(f"warruru.{name}")
    if logger.handlers:
        return logger

    paths.logs_dir(home).mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        paths.logs_dir(home) / f"{name}.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger
