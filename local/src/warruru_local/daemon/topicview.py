"""주제 화면의 뷰 모델. 날짜 경계와 표시 문자열을 여기서 만든다.

라우트는 얇게 두고 판단은 여기에 모은다 — `dayview` 와 같은 자리다.
"""

from __future__ import annotations

from warruru_local.clock import local_day_bounds, parse_iso

# 1건뿐인 주제가 모이는 자리. 표기가 갈린 것을 눈에 띄게 하는 오타 교정 장치다.
# 병합 UI 는 만들지 않는다 — 남는 소수는 SQL 한 줄이 화면보다 싸다.
UNSORTED_MAX = 1

KIND_LABELS = {
    "EXPERIMENT": "실험",
    "TROUBLESHOOTING": "트러블슈팅",
    "TECH_CHOICE": "기술선택",
    "CONCEPT": "개념",
}


def _local_time(iso: str) -> str:
    """`16:40` 처럼 사람이 읽는 시각. 화면은 로컬 시간대로 보여준다."""
    return parse_iso(iso).astimezone().strftime("%H:%M")


def _group(row: dict) -> dict:
    return {
        "topic": row["topic"],
        "topic_slug": row["topic_slug"],
        "count": row["count"],
        # 모르는 kind 값도 그대로 보여준다. 기록을 거절하지 않기로 했으므로
        # 화면도 거절하지 않는다 — 오타는 배지에서 눈에 띈다.
        "kinds": [
            (KIND_LABELS.get(kind, kind or "미상"), count)
            for kind, count in sorted(row["kinds"].items())
        ],
        "last_time": _local_time(row["last_occurred_at"]),
    }


def build_index(ctx, date: str) -> dict:
    """그 날짜의 주제별 요약. 경계는 예외 없이 `local_day_bounds` 로 만든다.

    UTC 자정으로 자르면 KST 오전 9시 이전 기록이 통째로 앞 구간으로 샌다.
    """
    start, end = local_day_bounds(date)
    rows = ctx.records.slug_summary(since=start, until=end)

    groups = [_group(row) for row in rows if row["count"] > UNSORTED_MAX]
    unsorted_rows = [_group(row) for row in rows if row["count"] <= UNSORTED_MAX]

    return {
        "date": date,
        "today_count": sum(row["count"] for row in rows),
        "groups": groups,
        "unsorted": unsorted_rows,
    }
