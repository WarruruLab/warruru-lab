"""기록 로직. HTTP 와 spool 흡수가 같은 경로를 쓰도록 여기 모은다."""

from __future__ import annotations

from warruru_local import limits
from warruru_local.clock import parse_iso, to_iso
from warruru_local.daemon.models import CHECKPOINT_TYPES


def _register_client(ctx, payload: dict, now: str) -> None:
    client_instance_id = payload.get("client_instance_id")
    if not client_instance_id:
        return
    ctx.repo.ensure_client(
        client_instance_id,
        ctx.machine_id,
        payload.get("tool") or "unknown",
        payload.get("client_name"),
        payload.get("client_version"),
        payload.get("cwd"),
        now,
    )


def _snapshot(ctx, payload: dict):
    return ctx.git.collect(payload.get("repo_path") or payload.get("cwd"))


def _normalized_time(raw, fallback: str) -> str:
    """잘못된 시각은 현재 시각으로 대체한다.

    시각 필드는 전부 에이전트에게 노출되고 문자열로만 타입돼 있다. 검증 없이
    저장하면 잘못된 값 하나가 그 날짜 화면을 영구히 500 으로 만든다
    (OUTSTANDING I2). 삭제 폼이 그 화면 안에 있으므로 UI 로는 복구할 수 없고,
    `finish_work` 는 `started_at` 을 다시 파싱하므로 그 작업은 영영 못 닫는다.
    기록을 거절하지 않기로 했으므로, 거절 대신 대체한다.

    통과만 시키지 않고 **다시 써서** 돌려준다. `%f` 는 1~6자리를 다 받으므로
    `.1Z` 와 `.150Z` 가 그대로 저장되면 사전순 정렬이 시간순과 어긋난다.
    목록과 집계가 그 정렬에 기대고 있다.
    """
    if not raw:
        return fallback
    try:
        return to_iso(parse_iso(raw))
    except (ValueError, TypeError):
        return fallback


def start_work(ctx, payload: dict) -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    goal, _ = limits.clamp_text(payload.get("goal"), limits.TEXT_MAX)
    snapshot = _snapshot(ctx, payload)

    work, duplicate = ctx.sessions.start(
        work_id=payload["work_id"],
        client_instance_id=payload.get("client_instance_id"),
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        title=title,
        goal=goal,
        snapshot=snapshot,
        started_at=_normalized_time(payload.get("started_at"), now),
    )
    return {
        "work_id": work["work_id"],
        "title": work["title"],
        "started_at": work["started_at"],
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
    }


def record_checkpoint(ctx, payload: dict, source: str = "MCP") -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    snapshot = _snapshot(ctx, payload)
    attachment = ctx.sessions.attach(
        work_id=payload.get("work_id"),
        client_instance_id=payload.get("client_instance_id"),
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        snapshot=snapshot,
    )
    work = attachment.work

    tags = limits.clamp_list(payload.get("tags"), limits.TAGS_MAX)
    raw_type = payload.get("type") or "NOTE"
    kind = raw_type.upper()
    if kind not in CHECKPOINT_TYPES:
        tags = [*tags, f"type:{raw_type}"][: limits.TAGS_MAX]
        kind = "NOTE"

    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    body, body_truncated = limits.clamp_text(payload.get("body"), limits.BODY_MAX)
    excerpt, _ = limits.clamp_text(
        payload.get("error_excerpt"), limits.ERROR_EXCERPT_MAX
    )

    row, duplicate = ctx.repo.insert_checkpoint(
        checkpoint_id=payload["checkpoint_id"],
        work_id=work["work_id"],
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        type=kind,
        title=title,
        body=body,
        body_truncated=body_truncated,
        occurred_at=_normalized_time(payload.get("occurred_at"), now),
        recorded_at=now,
        source=source,
        repo_path=snapshot.repo_path,
        repo_name=snapshot.repo_name,
        branch=snapshot.branch,
        commit_sha=snapshot.commit_sha,
        dirty=snapshot.dirty,
        dirty_file_count=snapshot.dirty_file_count,
        dirty_count_capped=snapshot.dirty_count_capped,
        files=limits.clamp_list(payload.get("files"), limits.FILES_MAX),
        error_excerpt=excerpt,
        tags=tags,
    )

    if not duplicate:
        ctx.repo.touch_work(work["work_id"], now, snapshot.repo_path)
        ctx.sessions.promote_title(work, title)

    return {
        "checkpoint_id": row["checkpoint_id"],
        "work_id": work["work_id"],
        "work_origin": work["origin"],
        "attached_by": attachment.attached_by,
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
    }


def _duration(work: dict) -> int:
    """마감이 저장된 `started_at` 에 걸려 있으면 안 된다.

    정규화 이전에 들어간 불량 값이 남아 있고, 여기서 예외가 나면 그 작업은
    **영영 못 닫는다** — 열린 채로 매일 화면에 남는다. 소요 시간 하나를
    포기하는 쪽이 싸다(OUTSTANDING I2).
    """
    try:
        started = parse_iso(work["started_at"])
        ended = parse_iso(work["ended_at"])
    except (ValueError, TypeError):
        return 0
    return int((ended - started).total_seconds())


def finish_work(ctx, work_id: str | None, payload: dict) -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    snapshot = _snapshot(ctx, payload)
    result, _ = limits.clamp_text(payload.get("result"), limits.TEXT_MAX)
    limitations, _ = limits.clamp_text(payload.get("limitations"), limits.TEXT_MAX)
    next_steps, _ = limits.clamp_text(payload.get("next_steps"), limits.TEXT_MAX)

    work = ctx.sessions.finish(
        work_id=work_id,
        client_instance_id=payload.get("client_instance_id"),
        result=result,
        limitations=limitations,
        next_steps=next_steps,
        snapshot=snapshot,
    )
    if work is None:
        return {
            "work_id": None,
            "reason": "NO_ACTIVE_WORK",
            "ended_at": None,
            "checkpoint_count": 0,
            "duration_seconds": 0,
            "git": snapshot.as_dict(),
        }

    return {
        "work_id": work["work_id"],
        "reason": None,
        "ended_at": work["ended_at"],
        "checkpoint_count": ctx.repo.count_checkpoints(work["work_id"]),
        "duration_seconds": _duration(work),
        "git": snapshot.as_dict(),
    }
