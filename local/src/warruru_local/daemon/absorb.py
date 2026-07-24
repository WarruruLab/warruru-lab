"""spool 흡수. 정상 경로와 같은 recording 함수를 쓴다."""

from __future__ import annotations

import json
import time
from pathlib import Path

from warruru_local import paths, spool
from warruru_local.clock import to_iso
from warruru_local.daemon import recording

# 고칠 수 없는 봉투 하나가 파일 전체를 영원히 붙잡지 않게 하는 상한이다.
MAX_ATTEMPTS = 5
ATTEMPTS_FIELD = "absorb_attempts"

# 붙잡은 파일에 붙이는 꼬리표. 어댑터는 `<대화 식별자>.jsonl` 에만 덧붙이므로
# 이 이름의 파일에는 아무도 쓰지 않는다.
CLAIM_SUFFIX = ".claimed"

_HANDLERS = {
    "start_work": lambda ctx, payload: recording.start_work(ctx, payload),
    "record_checkpoint": lambda ctx, payload: recording.record_checkpoint(
        ctx, payload, source="SPOOL"
    ),
    "finish_work": lambda ctx, payload: recording.finish_work(
        ctx, payload.get("work_id"), payload
    ),
    "client_closed": lambda ctx, payload: ctx.sessions.close_client(
        payload["client_instance_id"]
    ),
}


def absorb_all(ctx) -> int:
    """마지막 수정 후 조용해진 파일만, 이름을 먼저 붙잡은 뒤 처리한다."""
    home = ctx.settings.home
    quiet_before = time.time() - ctx.settings.spool_quiet_seconds
    spool_dir = paths.spool_dir(home)
    applied = 0

    # 지난 스윕이 붙잡아 두고 끝내지 못한 파일이 먼저다. 시간 순서를 지킨다.
    # 붙잡은 파일에는 아무도 덧붙이지 않으므로 조용해질 때까지 기다리지 않는다.
    for path in sorted(spool_dir.glob(f"*{CLAIM_SUFFIX}")):
        applied += _apply_file(ctx, path, spool.read_envelopes(path))

    for path in sorted(spool_dir.glob("*.jsonl")):
        if path.stat().st_mtime > quiet_before:
            continue
        if _has_unknown_version(path):
            ctx.logger.warning("모르는 봉투 버전이 있어 남겨 둔다: %s", path.name)
            continue

        claimed = _claim(ctx, path)
        if claimed is None:
            continue
        applied += _apply_file(ctx, claimed, spool.read_envelopes(claimed))

    return applied


def _has_unknown_version(path: Path) -> bool:
    """붙잡기 전에 한 번 훑어본다.

    모르는 버전의 파일은 이름조차 건드리지 않고 그대로 둬야 한다(IF-6).
    그래서 이 확인만은 붙잡기 전에 하고, 실제 처리는 붙잡은 파일에서 다시
    읽는다. 읽은 내용을 처리에 쓰지 않으므로 경합의 원인이 되지 않는다.
    """
    return any(
        item.get("envelope_version") != spool.ENVELOPE_VERSION
        for item in spool.read_envelopes(path)
    )


def _claim(ctx, path: Path) -> Path | None:
    """읽기 전에 이름을 바꿔 파일을 붙잡는다.

    읽고 나서 옮기면, 읽은 뒤에 어댑터가 덧붙인 줄이 한 번도 읽히지 않은 채
    absorbed/ 로 딸려 간다. 흡수는 이벤트 루프 위에서 몇 초씩 걸릴 수 있어
    그 창이 좁지 않다. 이름을 먼저 바꾸면 어댑터의 다음 덧붙임은 새로 만들어진
    같은 이름의 파일로 가고, 그 파일은 다음 스윕이 가져간다.
    """
    stamp = _stamp(ctx).replace(".", "")
    for counter in range(100):
        mark = stamp if counter == 0 else f"{stamp}-{counter}"
        target = path.with_name(f"{path.stem}.{mark}{CLAIM_SUFFIX}")
        if target.exists():
            continue
        try:
            path.rename(target)
        except OSError:
            ctx.logger.exception("spool 파일을 붙잡지 못했다: %s", path.name)
            return None
        return target

    ctx.logger.warning("붙잡을 이름을 정하지 못했다: %s", path.name)
    return None


def _origin_stem(path: Path) -> str:
    """붙잡은 이름에서 원래 대화 파일 이름을 되찾는다."""
    if path.name.endswith(CLAIM_SUFFIX):
        return path.name[: -len(CLAIM_SUFFIX)].rsplit(".", 1)[0]
    return path.stem


def _apply_file(ctx, path: Path, envelopes: list[dict]) -> int:
    """봉투를 하나씩 반영하고, 전부 반영됐을 때만 파일을 보관한다.

    실패한 봉투는 파일에 남겨 다음 스윕이 다시 시도한다. 예전에는 실패해도
    파일을 그대로 보관해 버려서, 한 번 실패한 기록이 영영 사라졌다.
    """
    applied = 0
    remaining: list[dict] = []
    dead: list[dict] = []

    for envelope in sorted(envelopes, key=lambda item: item.get("enqueued_at", "")):
        handler = _HANDLERS.get(envelope.get("kind"))
        if handler is None:
            ctx.logger.warning("모르는 봉투 종류: %s", envelope.get("kind"))
            continue
        try:
            handler(ctx, envelope.get("payload") or {})
            applied += 1
        except Exception:  # 한 봉투가 실패해도 나머지를 반영한다
            ctx.logger.exception("봉투를 반영하지 못했다: %s", envelope.get("event_id"))
            attempts = _attempts(envelope) + 1
            envelope[ATTEMPTS_FIELD] = attempts
            (dead if attempts >= MAX_ATTEMPTS else remaining).append(envelope)

    if dead:
        _to_dead_letter(ctx, path, dead)
    if remaining:
        _write(path, remaining)
        ctx.logger.warning(
            "봉투 %d건을 반영하지 못해 %s 에 남겨 둔다", len(remaining), path.name
        )
        return applied

    _archive(ctx, path)
    return applied


def _attempts(envelope: dict) -> int:
    try:
        return int(envelope.get(ATTEMPTS_FIELD) or 0)
    except (TypeError, ValueError):
        return 0


def _write(path: Path, envelopes: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in envelopes),
        encoding="utf-8",
    )


def _stamp(ctx) -> str:
    return to_iso(ctx.clock.now()).replace(":", "").replace("-", "")


def _archive(ctx, path: Path) -> None:
    stem = _origin_stem(path)
    target = paths.absorbed_dir(ctx.settings.home) / f"{stem}.{_stamp(ctx)}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    path.replace(target)


def _to_dead_letter(ctx, path: Path, envelopes: list[dict]) -> None:
    """몇 번을 시도해도 반영되지 않는 봉투. 지우지 않고 옆으로 치운다."""
    stem = _origin_stem(path)
    target = paths.dead_letter_dir(ctx.settings.home) / f"{stem}.{_stamp(ctx)}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for envelope in envelopes:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    ctx.logger.error(
        "%d번 시도해도 반영되지 않은 봉투 %d건을 %s 로 옮겼다",
        MAX_ATTEMPTS,
        len(envelopes),
        target,
    )
