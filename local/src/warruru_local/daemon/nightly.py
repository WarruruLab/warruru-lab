"""하루가 끝나면 아직 마감하지 못한 날들의 주제로 초안을 만들어 둔다.

**새 프로세스도 새 포트도 만들지 않는다.** 이미 도는 스위퍼 안에 함수로
들어간다(`AGENTS.md` §3). cron 을 쓰지 않는 이유도 같다 — 데몬은 화면 때문에
어차피 떠 있어야 하고, 파일 하나 쓰려고 스케줄러를 하나 더 두면 중간에
멈췄을 때 골격만 남고 결과물은 없다.

**어제까지를 마감한다. 오늘은 아니다.** 오늘은 아직 기록이 더 들어올 수 있고,
어제는 확정된 하루다. 그래서 '몇 시에 돌 것인가' 를 설정으로 받지 않는다 —
로컬 날짜가 바뀐 뒤 처음 도는 스위프가 곧 그 시각이다. 머신이 자고 있었어도
깨어난 뒤 첫 스위프에서 처리된다.

**데몬이 꺼져 있던 날도 함께 마감한다.** 표식에 적힌 날부터 어제까지를 한
구간으로 훑는다. 어제 하루만 보면 재부팅 뒤 며칠 만에 데몬이 뜬 경우 그 사이
날짜가 영영 잡히지 않는데, 이 저장소에는 데몬을 자동으로 띄우는 장치가 없어서
(launchd 도 cron 도 두지 않기로 했다) 그 구멍이 실제로 열린다.

되돌아보기에는 바닥이 있다(`LOOKBACK_DAYS`). 표식이 없는 첫 기동에 몇 달치가
한꺼번에 쏟아지면 그것은 마감이 아니라 사고다. 바닥 너머의 날은 사람이 `/t`
에서 직접 만들면 되고, 초안은 어차피 그 주제의 기록 전부를 재료로 쓰므로
잃는 것은 편의지 기록이 아니다.

**이미 초안이 있는 주제는 건드리지 않는다. 이 경계가 이 기능의 전부다.**
`upsert_draft` 는 미발행 초안을 덮어쓰므로, 사람이 `save_draft` 로 다듬어 둔
글이 다음 날 밤 조립기 출력으로 덮이면 그 문장은 복원되지 않는다.
자동화가 사람의 작업을 지우는 것은 자동화가 아니라 사고다.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from warruru_local import paths
from warruru_local.clock import local_date_of, local_day_bounds, to_iso
from warruru_local.daemon import drafting, publishing

MARKER = "nightly.json"

# 되돌아보기의 바닥. 이보다 오래 전 날은 자동으로 잡지 않는다.
LOOKBACK_DAYS = 14


def _marker_path(ctx):
    return paths.run_dir(ctx.settings.home) / MARKER


def _last_run(ctx) -> str | None:
    path = _marker_path(ctx)
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("date")
    except (OSError, ValueError):
        # 표식이 깨졌으면 '안 돌았다' 로 본다. 한 번 더 도는 것이
        # 안 도는 것보다 낫고, 이미 초안이 있는 주제는 어차피 건너뛴다.
        return None


def _mark(ctx, today: str, made: dict) -> None:
    path = _marker_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"date": today, **made}, ensure_ascii=False), encoding="utf-8"
    )


def _shift(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def _span(last_run: str | None, today: str) -> tuple[str, str] | None:
    """이번에 마감할 날짜 구간 `[첫날, 마지막날]`. 마감할 것이 없으면 `None`.

    표식의 날짜 `D` 에 돈 스위프는 `D-1` 까지를 마감했다. 그러므로 남은 것은
    `D` 부터다 — 첫날을 `D+1` 로 잡으면 데몬이 그날 하루만 떠 있다 꺼진 경우가
    샌다.

    표식이 없으면 첫 기동이거나 표식이 깨진 것이다. 그때는 어제만 본다.
    '모르겠으니 넓게 훑자' 는 첫 기동에 과거를 통째로 쏟는 쪽이라 반대로 간다.
    """
    last_day = _shift(today, -1)
    first_day = last_run if last_run is not None else last_day
    # ISO 날짜는 사전순 비교가 곧 시간순 비교다.
    first_day = max(first_day, _shift(last_day, -(LOOKBACK_DAYS - 1)))
    # 표식이 미래면(시계가 되돌아갔다) 마감할 날이 없다.
    return (first_day, last_day) if first_day <= last_day else None


def run(ctx) -> dict:
    """스위프마다 불린다. 대부분의 호출은 아무것도 하지 않고 돌아간다."""
    if not ctx.settings.nightly_draft:
        return {"skipped": "꺼져 있다", "drafted": [], "failed": []}

    today = local_date_of(to_iso(ctx.clock.now()))
    last_run = _last_run(ctx)
    if last_run == today:
        return {"skipped": "이미 돌았다", "drafted": [], "failed": []}

    span = _span(last_run, today)
    if span is None:
        # 표식을 오늘로 옮겨 다음 스위프가 빠른 길로 돌아가게 한다.
        _mark(ctx, today, {"drafted": [], "failed": [], "pushed": []})
        return {"skipped": "마감할 날이 없다", "drafted": [], "failed": []}

    first_day, last_day = span
    # 구간의 양 끝만 `local_day_bounds` 로 뽑는다. 날짜 문자열을 직접 잇지
    # 않는 이유는 `AGENTS.md` §4 와 같다 — 그렇게 하면 KST 오전 9시 이전
    # 기록이 통째로 앞 구간으로 샌다.
    start, _ = local_day_bounds(first_day)
    _, end = local_day_bounds(last_day)
    # 하루씩 돌지 않고 한 번에 묻는다. 여러 날에 걸친 주제가 한 번만 나오고,
    # 조립기는 어차피 그 주제의 기록 전부를 재료로 쓴다.
    rows = ctx.records.slug_summary(since=start, until=end)

    drafted: list[str] = []
    failed: list[str] = []
    pushed: list[str] = []
    for row in rows:
        slug = row["topic_slug"]
        # 사람이 손댔을 수 있다. 있으면 지나간다.
        if ctx.records.latest_draft_of(slug) is not None:
            continue
        try:
            made = drafting.create(ctx, slug)
            drafted.append(slug)
        except Exception:
            # 한 주제가 터졌다고 그날 밤 전체를 잃지 않는다.
            ctx.logger.exception("밤 초안 실패: %s", slug)
            failed.append(slug)
            continue
        if ctx.settings.publish_repo is not None and _push(ctx, made["draft_id"]):
            pushed.append(slug)

    result = {
        "drafted": drafted,
        "failed": failed,
        "pushed": pushed,
        "from": first_day,
        "to": last_day,
    }
    # 표식은 마지막에 남긴다. 도중에 죽으면 다음 스위프가 다시 시도한다.
    _mark(ctx, today, result)
    return result


def _push(ctx, draft_id: str) -> bool:
    """밀어 넣기는 부가다. 실패해도 초안은 이미 남았으니 밤을 망치지 않는다."""
    try:
        return bool(publishing.push_to_repo(ctx, draft_id).pushed)
    except Exception:
        ctx.logger.exception("밤 밀어넣기 실패: %s", draft_id)
        return False
