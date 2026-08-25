"""spool 흡수. 정상 경로와 같은 recording 함수를 쓴다."""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

from warruru_local import paths, spool
from warruru_local.clock import to_iso
from warruru_local.daemon import learning, recording

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
    # 온라인 경로(POST /v1/records)와 **같은 함수**다.
    # 갈라지면 두 경로의 동작이 조용히 달라진다.
    "learning_record": lambda ctx, payload: learning.record(
        ctx, payload, source="SPOOL"
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
        with _isolated(ctx, path):
            applied += _apply_file(ctx, path, spool.read_envelopes(path, ctx.logger))

    for path in sorted(spool_dir.glob("*.jsonl")):
        with _isolated(ctx, path):
            if path.stat().st_mtime > quiet_before:
                continue
            if _has_unknown_version(path):
                ctx.logger.warning("모르는 봉투 버전이 있어 남겨 둔다: %s", path.name)
                continue

            claimed = _claim(ctx, path)
            if claimed is None:
                continue
            applied += _apply_file(
                ctx, claimed, spool.read_envelopes(claimed, ctx.logger)
            )

    return applied


@contextlib.contextmanager
def _isolated(ctx, path: Path):
    """파일 하나의 실패가 나머지를 인질로 잡지 않게 한다.

    `stat` · 읽기 · `rename` 은 봉투별 try 밖에 있어서, 여기서 난 예외는
    `absorb_all` 을 통째로 끝낸다. 기동 경로가 이 함수를 부르므로 그 예외
    하나가 데몬을 영구 정지시킨다(OUTSTANDING I1). 사전순으로 앞선 파일이
    깨졌으면 그 뒤 전부가 함께 묻힌다.

    삼키기만 하고 파일은 손대지 않는다. 옮기거나 지우면 원인을 볼 수 없고,
    남겨 두면 로그에 이름이 매번 찍혀 사람이 찾아갈 수 있다.
    """
    try:
        yield
    except Exception:
        ctx.logger.exception("spool 파일을 처리하지 못해 건너뛴다: %s", path.name)


def _has_unknown_version(path: Path) -> bool:
    """붙잡기 전에 한 번 훑어본다.

    모르는 버전의 파일은 이름조차 건드리지 않고 그대로 둬야 한다(IF-6).
    그래서 이 확인만은 붙잡기 전에 하고, 실제 처리는 붙잡은 파일에서 다시
    읽는다. 읽은 내용을 처리에 쓰지 않으므로 경합의 원인이 되지 않는다.
    """
    return any(
        item.get("envelope_version") not in spool.SUPPORTED_ENVELOPE_VERSIONS
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
    unknown_kind = 0
    deferred = 0
    remaining: list[dict] = []
    dead: list[dict] = []

    for envelope in sorted(envelopes, key=lambda item: item.get("enqueued_at", "")):
        # 붙잡기 전 검사(`_has_unknown_version`)와 이름 바꾸기 사이의 창으로
        # 어댑터가 덧붙인 줄이 들어올 수 있다. 그 줄이 모르는 버전이면
        # 격리하지 않고 남긴다 — 고칠 수 없는 봉투가 아니라 **아직 못 읽는 봉투**이고,
        # 새 데몬이 뜨면 읽힌다. 그래서 시도 횟수도 세지 않는다.
        if envelope.get("envelope_version") not in spool.SUPPORTED_ENVELOPE_VERSIONS:
            remaining.append(envelope)
            deferred += 1
            continue

        handler = _HANDLERS.get(envelope.get("kind"))
        if handler is None:
            # "재시도해도 결과가 달라질 수 없다" 는 데몬 업그레이드를 빼먹은
            # 판단이었다 — 새 kind 의 봉투를 구버전 데몬이 받는 창에서는
            # 재시도가 정확히 결과를 바꾼다(새 데몬이 뜨면 읽힌다).
            # 그래서 실패한 봉투와 같은 규칙을 탄다: 시도 횟수를 세고,
            # MAX_ATTEMPTS 를 넘겨도 모르는 kind 면 그때 격리한다.
            # 버전 게이트가 있는 kind(learning_record 등)는 애초 여기 오지 않는다.
            ctx.logger.warning("모르는 봉투 종류: %s", envelope.get("kind"))
            attempts = _attempts(envelope) + 1
            envelope[ATTEMPTS_FIELD] = attempts
            if attempts >= MAX_ATTEMPTS:
                dead.append(envelope)
                unknown_kind += 1
            else:
                remaining.append(envelope)
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
        _to_dead_letter(ctx, path, dead, unknown_kind)
    if remaining:
        # 남은 것이 전부 '아직 못 읽는 버전'이고 반영·격리한 것도 없으면
        # 파일 내용이 한 글자도 달라지지 않았다. 그런데도 다시 쓰면,
        # `_write` 가 잘라내고 다시 쓰는 방식이라 매 스윕(기본 300초)마다
        # 같은 내용을 덮어쓰게 되고 그 사이 중단되면 줄이 깨진다.
        # 깨진 줄은 `read_envelopes` 가 조용히 버린다 — 지키려던 봉투를 잃는다.
        #
        # 재시도 대기 봉투는 시도 횟수가 올라가므로 반드시 다시 써야 한다.
        # 그것까지 건너뛰면 MAX_ATTEMPTS 에 영영 도달하지 못한다.
        unchanged = not applied and not dead and deferred == len(remaining)
        if not unchanged:
            _write(path, remaining)
        ctx.logger.warning(
            "봉투 %d건이 %s 에 남았다 (재시도 대기 또는 읽을 수 없는 버전)",
            len(remaining), path.name,
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


def _to_dead_letter(
    ctx, path: Path, envelopes: list[dict], unknown_kind: int = 0
) -> None:
    """반영할 수 없는 봉투. 지우지 않고 옆으로 치운다.

    두 갈래가 여기로 온다 — `MAX_ATTEMPTS` 를 넘긴 것과 핸들러가 없는 종류다.
    뒤쪽은 시도조차 한 적이 없으므로 로그가 "5번 시도했다" 고 말하면 안 된다.
    K2 를 조사하러 온 사람이 이 로그를 먼저 읽는다.
    """
    stem = _origin_stem(path)
    target = paths.dead_letter_dir(ctx.settings.home) / f"{stem}.{_stamp(ctx)}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for envelope in envelopes:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    retried = len(envelopes) - unknown_kind
    reasons = []
    if retried:
        reasons.append(f"{MAX_ATTEMPTS}번 시도해도 반영되지 않은 것 {retried}건")
    if unknown_kind:
        reasons.append(f"핸들러가 없는 종류 {unknown_kind}건")
    ctx.logger.error(
        "봉투 %d건을 %s 로 옮겼다 — %s", len(envelopes), target, " · ".join(reasons)
    )
