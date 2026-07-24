"""시각. 테스트에서 주입할 수 있도록 프로토콜로 둔다.

`datetime.now()`를 코드 곳곳에서 부르면 귀속 규칙과 자동 마감을 신뢰성
있게 검증할 수 없다. 시각은 반드시 이 모듈을 거친다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """테스트용. 시각을 고정하고 원할 때만 전진시킨다."""

    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current = self._current + timedelta(seconds=seconds)


def to_iso(value: datetime) -> str:
    """RFC 3339 UTC, 밀리초 3자리, Z 접미. 사전순 정렬이 시간순과 같다."""
    utc = value.astimezone(timezone.utc)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // 1000:03d}Z"


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, ISO_FORMAT).replace(tzinfo=timezone.utc)


def local_day_bounds(date_str: str) -> tuple[str, str]:
    """로컬 시간대 하루의 [시작, 끝) 을 UTC ISO 로 준다. 끝은 배타적이다.

    지역 오프셋은 "지금"이 아니라 대상 날짜 자체에서 구한다. 이 날짜의
    자정을 나타내는 naive datetime 을 `.astimezone()` 인자 없이 변환하면
    그 날짜에 맞는 로컬 오프셋을 얻는다 — 서머타임 경계를 사이에 두고
    "지금"과 대상 날짜가 갈라져도 어긋나지 않는다.
    """
    day = datetime.strptime(date_str, "%Y-%m-%d")
    start = day.astimezone()
    return to_iso(start), to_iso(start + timedelta(days=1))


def local_date_of(iso: str) -> str:
    """UTC ISO 문자열을 로컬 시간대의 YYYY-MM-DD 로 바꾼다."""
    return parse_iso(iso).astimezone().strftime("%Y-%m-%d")
