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
        # 통과만 시키지 않고 **다시 써서** 돌려준다. `%f` 는 1~6자리를 다 받으므로
        # `.1Z` 와 `.150Z` 가 그대로 저장되면 사전순 정렬이 시간순과 어긋난다.
        # 목록과 집계가 그 정렬에 기대고 있다.
        return to_iso(parse_iso(raw))
    except (ValueError, TypeError):
        return fallback


def record(ctx, payload: dict, source: str = "MCP") -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    # 멱등 확인이 attach 보다 먼저다. 봉투 재생(크래시 후 재시도, 보강 호출)은
    # 이 kind 에서 설계된 일상인데, attach 를 먼저 부르면 활성 세션이 없을 때마다
    # 빈 INFERRED 작업이 새로 생겨 날짜 화면에 유령 작업이 쌓인다.
    existing = ctx.records.get_record(payload["record_id"])
    if existing is not None:
        return _enrich(ctx, existing, payload, now)

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
        # 대문자로 맞춘다. slug_summary 가 kind 로 집계하므로
        # "Experiment" 와 "EXPERIMENT" 가 갈리면 화면의 건수가 쪼개진다.
        kind=(payload.get("kind") or "").strip().upper(),
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
        "example_call": topics.example_call(
            stored, missing, record_id=row["record_id"]
        ),
        # 저장된 슬러그를 기준으로 한다. 중복 경로에서 새 payload 의
        # 슬러그를 쓰면, 보고한 것과 다른 주제의 힌트가 나간다.
        "similar_slugs": ctx.records.similar_slugs(row["topic_slug"]),
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
        "filled_fields": [],
    }


def _enrich(ctx, existing: dict, payload: dict, now: str) -> dict:
    """같은 record_id 로 다시 온 보강 호출. **비어 있던 필드만** 채운다.

    이 경로가 없으면 `missing_fields` 힌트를 따라도 채울 방법이 없어
    힌트 장치 전체가 무의미해진다. 세션은 새로 붙이지 않는다 —
    기록은 이미 자기 작업을 알고 있다.
    """
    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    body, _ = limits.clamp_text(payload.get("body"), limits.BODY_MAX)
    rationale, _ = limits.clamp_text(payload.get("rationale"), limits.TEXT_MAX)
    outcome, _ = limits.clamp_text(payload.get("outcome"), limits.TEXT_MAX)
    limitation, _ = limits.clamp_text(payload.get("limitation"), limits.TEXT_MAX)
    interview, _ = limits.clamp_text(payload.get("interview"), limits.TEXT_MAX)

    incoming_topic, _ = topics.normalize_topic(
        payload.get("topic"), limits.TITLE_MAX
    )
    row, filled = ctx.records.fill_record(
        existing["record_id"],
        {
            # topic 도 여기 넘긴다. "비어 있을 때만 채운다" 규칙은
            # 나머지 일곱 필드와 **같은 곳**에서 지켜져야 한다.
            "topic": incoming_topic,
            "kind": (payload.get("kind") or "").strip().upper(),
            "title": title, "body": body,
            "rationale": rationale, "outcome": outcome,
            "limitation": limitation, "interview": interview,
        },
    )
    if row is None:
        row = existing

    if filled:
        ctx.repo.touch_work(row["work_id"], now, row.get("repo_path"))

    stored = {
        "kind": row["kind"], "topic": row["topic"],
        "title": row["title"], "body": row["body"],
        "rationale": row["rationale"], "outcome": row["outcome"],
        "limitation": row["limitation"], "interview": row["interview"],
    }
    missing = topics.missing_fields(stored)
    return {
        "record_id": row["record_id"],
        "work_id": row["work_id"],
        "work_origin": None,
        "attached_by": None,
        "topic_slug": row["topic_slug"],
        "project": row["project"],
        "missing_fields": missing,
        "example_call": topics.example_call(
            stored, missing, record_id=row["record_id"]
        ),
        "similar_slugs": ctx.records.similar_slugs(row["topic_slug"]),
        "git": None,
        "duplicate": True,
        "filled_fields": filled,
    }


def _stripped(value: str | None) -> str | None:
    """화면에 앞뒤 공백이 보이지 않게. 공백뿐이면 비어 있는 것으로 본다."""
    if value is None:
        return None
    text = value.strip()
    return text or None
