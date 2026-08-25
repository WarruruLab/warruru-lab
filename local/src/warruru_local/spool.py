"""데몬에 닿지 못한 요청을 보존한다. 어댑터가 쓰고 데몬이 흡수한다."""

from __future__ import annotations

import json
from pathlib import Path

from warruru_local import paths

ENVELOPE_VERSION = 1
KINDS = {
    "start_work", "record_checkpoint", "finish_work", "client_closed",
    "learning_record",
}

# 데몬이 읽을 수 있는 봉투 버전. 모르는 버전이 섞인 파일은 이름조차 건드리지 않는다.
#
# **손으로 적지 않고 아래에서 파생시킨다** — "이 패키지가 쓰는 봉투를 이 패키지가
# 못 읽는" 상태를 테스트로 감시하는 대신 표현 자체가 불가능하게 만든다.
# 새 버전의 kind 를 더하면 이 집합이 저절로 넓어지고, 구버전 데몬만
# (이 상수가 좁은 채로) 그 파일을 건너뛴다. 정의는 파일 아래쪽에 있다 —
# ENVELOPE_VERSION_BY_KIND 뒤에 와야 하기 때문이다.

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


# 위 주석 참조. {1, 2} 를 손으로 적는 대신 쓰는 쪽에서 파생시킨다.
SUPPORTED_ENVELOPE_VERSIONS = frozenset(
    {ENVELOPE_VERSION} | set(ENVELOPE_VERSION_BY_KIND.values())
)


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


def read_envelopes(path: Path, logger=None) -> list[dict]:
    """깨진 줄은 건너뛴다. 한 줄이 깨졌다고 파일 전체를 버리지 않는다.

    **디코드도 건너뛰기로 처리한다.** `encoding="utf-8"` 만 주면 잘못된
    바이트 하나에 `UnicodeDecodeError` 가 나고, 그 예외가 기동 경로를 뚫으면
    데몬이 부팅에 실패한다. 원인이 디스크 파일이므로 다시 켜도 같은 자리에서
    죽는다 — 화면도 API 도 없으니 사용자는 고칠 방법이 없다(OUTSTANDING I1).
    `errors="replace"` 로 읽으면 그 바이트는 U+FFFD 가 되고, 그 줄은
    JSON 이 아니게 되어 아래 건너뛰기 규칙에 그대로 걸린다.

    `logger` 를 주면 버린 줄을 남긴다. 유실이 흔적조차 없으면 나중에
    아무도 찾지 못한다(OUTSTANDING I6). 어댑터 쪽 호출자는 주지 않아도 된다 —
    이 모듈은 `mcp/` 도 임포트하므로 로거를 필수로 만들지 않는다.
    """
    if not path.exists():
        return []
    envelopes = []
    dropped = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            envelopes.append(json.loads(stripped))
        except json.JSONDecodeError:
            dropped += 1
            continue
    if dropped and logger is not None:
        logger.warning("깨진 spool 줄 %d개를 버렸다: %s", dropped, path.name)
    return envelopes
