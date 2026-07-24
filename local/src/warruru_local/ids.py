"""ULID 기반 식별자. 외부 의존성 없이 구현한다.

시간순 정렬이 가능하면서 머신 간 충돌이 없다. 후속 단계에서 두 머신의
기록을 서버에서 합칠 때 그대로 쓴다.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_CHARS = 10
_RANDOM_CHARS = 16
_RANDOM_BYTES = 10


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def ulid(now_ms: int | None = None, randomness: bytes | None = None) -> str:
    """26자 ULID를 만든다. 앞 10자가 밀리초 타임스탬프, 뒤 16자가 무작위다."""
    milliseconds = int(time.time() * 1000) if now_ms is None else now_ms
    entropy = os.urandom(_RANDOM_BYTES) if randomness is None else randomness
    return _encode(milliseconds, _TIME_CHARS) + _encode(
        int.from_bytes(entropy, "big"), _RANDOM_CHARS
    )


def new_id(
    prefix: str, now_ms: int | None = None, randomness: bytes | None = None
) -> str:
    """`wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D` 형태의 접두사 식별자를 만든다."""
    return f"{prefix}_{ulid(now_ms=now_ms, randomness=randomness)}"
