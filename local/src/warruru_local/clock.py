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


def local_month_bounds(year_month: str) -> tuple[str, str]:
    """로컬 시간대 한 달의 [시작, 끝) 을 UTC ISO 로 준다. 끝은 배타적이다.

    `local_day_bounds` 위에 얹는다. 달의 시작은 1일의 시작이고,
    달의 끝은 **다음 달 1일의 시작**이다 — 말일이 28·29·30·31 로 갈리므로
    말일을 계산해서 하루를 더하지 않는다. 그 계산이 윤년에서 틀린다.
    """
    year, month = year_month.split("-")
    start, _ = local_day_bounds(f"{year}-{month}-01")
    next_year, next_month = int(year), int(month) + 1
    if next_month == 13:
        next_year, next_month = next_year + 1, 1
    end, _ = local_day_bounds(f"{next_year:04d}-{next_month:02d}-01")
    return start, end


def local_date_of(iso: str) -> str:
    """UTC ISO 문자열을 로컬 시간대의 YYYY-MM-DD 로 바꾼다."""
    return parse_iso(iso).astimezone().strftime("%Y-%m-%d")


# ── 저장된 값을 읽을 때 ────────────────────────────────────────────
#
# 위의 엄격한 함수들은 **방금 만든 값**을 다룬다. 아래 둘은 **DB 에서 읽은
# 값**을 다룬다. 기록 경계가 시각을 정규화하지만(`recording._normalized_time`)
# 그 이전에 들어간 행은 그대로 남아 있고, 그 한 행에서 예외가 나면 화면
# 전체가 500 이 된다. 삭제 폼이 그 화면 안에 있어서 지울 수도 없다
# (OUTSTANDING I2). 한 칸을 비우는 쪽이 화면 전체를 잃는 것보다 낫다.
#
# 엄격한 쪽을 관용적으로 바꾸지 않고 함수를 나눈 이유는, 방금 만든 값이
# 파싱되지 않는 것은 **버그**여서 조용히 넘기면 안 되기 때문이다.


def local_time_or_none(iso: str | None) -> str | None:
    """저장된 UTC ISO → 로컬 `HH:MM`. 읽지 못하면 시각 없음으로 본다."""
    if iso is None:
        return None
    try:
        return parse_iso(iso).astimezone().strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def local_date_or_none(iso: str | None) -> str | None:
    """저장된 UTC ISO → 로컬 `YYYY-MM-DD`. 읽지 못하면 날짜 없음으로 본다."""
    if iso is None:
        return None
    try:
        return local_date_of(iso)
    except (ValueError, TypeError):
        return None
