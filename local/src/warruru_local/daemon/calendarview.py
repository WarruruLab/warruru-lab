"""달력 화면의 표시 모델. 템플릿은 판단하지 않는다.

`dayview` 와 같은 자리를 지킨다 — 여기서 격자를 다 만들어 넘기고,
템플릿은 받은 것을 그대로 그린다.

**달력이 칠하는 것은 '학습 기록이 있는 날' 이 아니라 '날짜 화면에 무언가
있는 날' 이다.** 학습 기록만 세면 작업 세션 5개뿐인 날이 빈칸으로 보이고,
사용자는 그 날을 누르지 않는다. 달력이 하는 일이 '어디를 누를지 고르는 것'
하나뿐이라, 그 거짓 빈칸 하나가 기능 전체를 무력화한다.
"""

from __future__ import annotations

import calendar

from warruru_local.clock import local_date_or_none, local_month_bounds

# 월요일 시작. 주가 일요일에 시작하는지 월요일에 시작하는지는 취향이지만,
# 개발 기록을 되짚는 화면이라 주중이 붙어 있는 쪽을 골랐다.
_CAL = calendar.Calendar(firstweekday=0)
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


def _shift(year: int, month: int, delta: int) -> str:
    index = (year * 12 + (month - 1)) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def build_month(ctx, year_month: str, today: str) -> dict:
    """한 달치 격자. 질의는 달 전체를 한 구간으로 두 번만 한다.

    날마다 물으면 31번이다. 구간으로 한 번 훑고 로컬 날짜로 접는다 —
    접는 일은 `local_date_of` 가 한다. UTC 문자열 앞 10자를 잘라 쓰면
    KST 오전 9시 이전 기록이 통째로 앞날로 샌다.
    """
    start, end = local_month_bounds(year_month)
    marked: set[str] = set()
    # 읽지 못하는 값은 어느 날도 칠하지 않는다. 구간 질의는 문자열 비교라
    # 불량 값도 사전순으로 구간 안에 들면 여기까지 온다 — 그 한 행에
    # 달력 전체가 500 이 되면 날짜를 고를 방법이 없어진다.
    marked.update(
        day
        for iso in ctx.records.occurred_between(start, end)
        if (day := local_date_or_none(iso)) is not None
    )
    marked.update(
        day
        for iso in ctx.repo.works_started_between(start, end)
        if (day := local_date_or_none(iso)) is not None
    )

    year, month = (int(part) for part in year_month.split("-"))
    weeks = []
    for week in _CAL.monthdatescalendar(year, month):
        row = []
        for day in week:
            # 격자를 채우려고 끌려온 앞뒤 달의 날은 빈칸으로 둔다.
            # 칠해서 링크를 걸면 달력을 넘겼을 때 같은 날이 두 번 보인다.
            inside = day.month == month
            iso_date = day.isoformat()
            row.append({
                "day": day.day if inside else None,
                "date": iso_date if inside else None,
                "marked": inside and iso_date in marked,
                "today": inside and iso_date == today,
            })
        weeks.append(row)

    return {
        "year_month": year_month,
        "label": f"{year}년 {month}월",
        "weekdays": WEEKDAYS,
        "weeks": weeks,
        "marked_days": len(marked),
        "prev_month": _shift(year, month, -1),
        "next_month": _shift(year, month, 1),
    }
