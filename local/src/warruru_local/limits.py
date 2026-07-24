"""문자열 상한. 넘으면 자르고 표시할 뿐, 요청을 거절하지 않는다."""

from __future__ import annotations

TITLE_MAX = 200
BODY_MAX = 65536
ERROR_EXCERPT_MAX = 8192
TEXT_MAX = 4096
FILES_MAX = 50
TAGS_MAX = 20


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def clamp_text(text: str | None, limit: int) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    normalized = normalize_newlines(text)
    if len(normalized) <= limit:
        return normalized, False
    return normalized[:limit], True


def clamp_list(values: list[str] | None, limit: int) -> list[str]:
    if not values:
        return []
    return list(values[:limit])
