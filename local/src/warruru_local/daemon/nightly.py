"""하루가 끝나면 어제 주제로 초안을 만들어 둔다.

**새 프로세스도 새 포트도 만들지 않는다.** 이미 도는 스위퍼 안에 함수로
들어간다(`AGENTS.md` §3). cron 을 쓰지 않는 이유도 같다 — 데몬은 화면 때문에
어차피 떠 있어야 하고, 파일 하나 쓰려고 스케줄러를 하나 더 두면 중간에
멈췄을 때 골격만 남고 결과물은 없다.

**어제를 마감한다. 오늘이 아니다.** 오늘은 아직 기록이 더 들어올 수 있고,
어제는 확정된 하루다. 그래서 '몇 시에 돌 것인가' 를 설정으로 받지 않는다 —
로컬 날짜가 바뀐 뒤 처음 도는 스위프가 곧 그 시각이다. 머신이 자고 있었어도
깨어난 뒤 첫 스위프에서 처리된다.

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


def run(ctx) -> dict:
    """스위프마다 불린다. 대부분의 호출은 아무것도 하지 않고 돌아간다."""
    if not ctx.settings.nightly_draft:
        return {"skipped": "꺼져 있다", "drafted": [], "failed": []}

    today = local_date_of(to_iso(ctx.clock.now()))
    if _last_run(ctx) == today:
        return {"skipped": "이미 돌았다", "drafted": [], "failed": []}

    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    start, end = local_day_bounds(yesterday)
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

    result = {"drafted": drafted, "failed": failed, "pushed": pushed}
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
