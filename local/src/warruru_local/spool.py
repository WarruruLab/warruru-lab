"""데몬에 닿지 못한 요청을 보존한다. 어댑터가 쓰고 데몬이 흡수한다."""

from __future__ import annotations

import json
from pathlib import Path

from warruru_local import paths

ENVELOPE_VERSION = 1
KINDS = {"start_work", "record_checkpoint", "finish_work", "client_closed"}

# 데몬이 읽을 수 있는 봉투 버전. 모르는 버전이 섞인 파일은 이름조차 건드리지 않는다.
#
# **여기에 버전을 더하는 것은 그 버전을 처리할 핸들러를 더하는 것과 같은 커밋이어야 한다.**
# 먼저 올리면 데몬이 파일을 붙잡아 놓고 핸들러가 없어 dead-letter 로 격리한다 —
# 대기시키려던 봉투를 오히려 버리는 셈이라 이 장치의 목적이 뒤집힌다.
# 그래서 `2` 는 `learning_record` 핸들러가 들어오는 태스크에서 함께 올린다.
SUPPORTED_ENVELOPE_VERSIONS = {1}

# 봉투 종류 이름. 오타 하나가 이 장치를 통째로 무력화하므로 상수로 둔다.
# 어댑터가 `send()` 에 넘기는 첫 인자가 이 값이어야 한다 — **툴 이름이 아니다.**
KIND_LEARNING_RECORD = "learning_record"

# 봉투 종류마다 버전이 다를 수 있다. 적지 않은 종류는 ENVELOPE_VERSION 을 쓴다.
#
# `learning_record` 가 2 인 이유는 구버전 데몬을 막기 위해서다. 그 데몬은 이 종류의
# 핸들러가 없어서 봉투를 경고만 남기고 버리는데(dead-letter 수정은 새 데몬에만 있다),
# 버전이 높으면 파일을 통째로 건너뛰므로 유실이 아니라 대기가 된다.
# 같은 파일에 든 기존 봉투도 함께 미뤄지지만, 새 데몬이 뜨면 전부 반영된다.
ENVELOPE_VERSION_BY_KIND = {KIND_LEARNING_RECORD: 2}


def envelope_version_for(kind: str) -> int:
    return ENVELOPE_VERSION_BY_KIND.get(kind, ENVELOPE_VERSION)


def spool_path(home: Path, client_instance_id: str) -> Path:
    """대화마다 파일을 나눈다. 여러 어댑터가 같은 파일에 동시에 쓰지 않게 한다."""
    return paths.spool_dir(home) / f"{client_instance_id}.jsonl"


def append(
    home: Path,
    client_instance_id: str,
    kind: str,
    payload: dict,
    enqueued_at: str,
    event_id: str,
) -> None:
    target = spool_path(home, client_instance_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "envelope_version": envelope_version_for(kind),
        "event_id": event_id,
        "kind": kind,
        "enqueued_at": enqueued_at,
        "payload": payload,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def read_envelopes(path: Path) -> list[dict]:
    """깨진 줄은 건너뛴다. 한 줄이 깨졌다고 파일 전체를 버리지 않는다."""
    if not path.exists():
        return []
    envelopes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            envelopes.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return envelopes
