"""학습 기록의 기록 로직. HTTP 와 spool 흡수가 같은 경로를 쓰도록 여기 모은다.

`recording.record_checkpoint()` 와 같은 순서로 흐른다 —
클라이언트 등록 → git 스냅샷 → 세션 부착 → 한도 적용 → 삽입 → 작업 시각 갱신.

**검증은 이 함수 안에 두지 않는다.** 흡수 경로가 같은 함수를 부르기 때문이다.
안쪽에 두면 이미 입구(MCP·API)를 통과해 spool 에 들어간 기록이 흡수 시점에
다시 걸려 dead-letter 로 갈 여지가 생긴다. 그때는 에이전트가 이미 사라진 뒤라
아무도 고칠 수 없다.
"""

from __future__ import annotations

from warruru_local import limits, topics
from warruru_local.clock import parse_iso, to_iso
from warruru_local.daemon.recording import _register_client, _snapshot


def _normalized_time(raw, fallback: str) -> str:
    """잘못된 시각은 현재 시각으로 대체한다.

    `occurred_at` 은 에이전트에게 노출되고 문자열로만 타입돼 있다. 검증 없이
    저장하면 잘못된 값 하나가 날짜 화면을 영구히 500 으로 만든다(OUTSTANDING I2).
    기록을 거절하지 않기로 했으므로, 거절 대신 대체한다.
    """
    if not raw:
        return fallback
    try:
        parse_iso(raw)
    except (ValueError, TypeError):
        return fallback
    return raw


def record(ctx, payload: dict, source: str = "MCP") -> dict:
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

    # 슬러그는 **자른 뒤에** 만든다. 순서를 바꾸면 같은 원문이 상한 근처에서
    # 두 슬러그로 갈리고, 그 둘은 영영 한 주제로 모이지 않는다.
    topic, _ = limits.clamp_text(payload.get("topic"), limits.TITLE_MAX)
    topic = (topic or "").strip()
    topic_slug = topics.slugify(topic)

    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    body, body_truncated = limits.clamp_text(payload.get("body"), limits.BODY_MAX)
    rationale, _ = limits.clamp_text(payload.get("rationale"), limits.TEXT_MAX)
    outcome, _ = limits.clamp_text(payload.get("outcome"), limits.TEXT_MAX)
    limitation, _ = limits.clamp_text(payload.get("limitation"), limits.TEXT_MAX)
    interview, _ = limits.clamp_text(payload.get("interview"), limits.TEXT_MAX)

    row, duplicate = ctx.records.insert_record(
        record_id=payload["record_id"],
        work_id=work["work_id"],
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        kind=(payload.get("kind") or "").strip(),
        topic=topic,
        topic_slug=topic_slug,
        title=(title or "").strip(),
        body=(body or "").strip(),
        body_truncated=body_truncated,
        rationale=_stripped(rationale),
        outcome=_stripped(outcome),
        limitation=_stripped(limitation),
        interview=_stripped(interview),
        # 기록 시점의 저장소 이름으로 고정한다. 나중에 이름이 바뀌어도
        # 과거 기록의 소속은 흔들리지 않는다.
        project=snapshot.repo_name,
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
    )

    if not duplicate:
        ctx.repo.touch_work(work["work_id"], now, snapshot.repo_path)

    # 거절하지 않는 대신 무엇이 비었는지와 어떻게 채우는지를 돌려준다.
    # 에이전트는 재시도 비용이 거의 0이라 방법을 알려주면 실제로 보강 호출을 한다.
    #
    # 힌트는 **저장된 값** 기준으로 만든다. 원본 payload 를 쓰면 예시가
    # 앞뒤 공백이나 잘리기 전 길이를 그대로 되돌려 주고, 그걸 복사하면
    # 방금 정리한 것을 다시 되돌리는 호출이 나간다.
    stored = {
        "kind": row["kind"], "topic": row["topic"],
        "title": row["title"], "body": row["body"],
        "rationale": row["rationale"], "outcome": row["outcome"],
        "limitation": row["limitation"], "interview": row["interview"],
    }
    missing = topics.missing_fields(stored)
    return {
        "record_id": row["record_id"],
        "work_id": work["work_id"],
        "work_origin": work["origin"],
        "attached_by": attachment.attached_by,
        "topic_slug": row["topic_slug"],
        "project": row["project"],
        "missing_fields": missing,
        "example_call": topics.example_call(stored, missing),
        "similar_slugs": ctx.records.similar_slugs(topic_slug),
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
    }


def _stripped(value: str | None) -> str | None:
    """화면에 앞뒤 공백이 보이지 않게. 공백뿐이면 비어 있는 것으로 본다."""
    if value is None:
        return None
    text = value.strip()
    return text or None
