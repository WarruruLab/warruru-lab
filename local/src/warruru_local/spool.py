"""데몬에 닿지 못한 요청을 보존한다. 어댑터가 쓰고 데몬이 흡수한다."""

from __future__ import annotations

import json
from pathlib import Path

from warruru_local import paths

ENVELOPE_VERSION = 1
KINDS = {"start_work", "record_checkpoint", "finish_work", "client_closed"}


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
        "envelope_version": ENVELOPE_VERSION,
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
