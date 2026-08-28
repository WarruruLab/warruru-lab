"""발행의 유일한 이음매.

어댑터가 바뀌어도 부르는 쪽은 이 한 메서드만 안다. 티스토리 자동 발행이
MVP 밖인 것도, 나중에 붙일 자리가 여기 하나로 정해져 있기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishResult:
    """어디에 앉았는지. `path` 는 로컬 파일, `url` 은 원격 주소다."""

    target: str
    path: str | None = None
    url: str | None = None
    # 화면에 띄울 문자열. 파일도 원격도 아닌 어댑터(붙여넣기)가 쓴다.
    body: str | None = None
    # 원격까지 갔는가. 원격이 있는 어댑터만 채운다(없으면 None).
    # 산문이 아니라 값으로 알려야 읽는 쪽이 분기할 수 있다 —
    # "밀어 넣었다" 고 말해 놓고 원격에 없는 것이 가장 나쁘다.
    pushed: bool | None = None


class PublishTarget:
    """발행 대상. 구현체는 `publish` 하나만 채운다.

    `visibility` 의 기본값이 `private` 인 것은 실수로 공개되는 사고를 막기 위해서다.
    공개는 명시해야만 되게 한다.
    """

    name = "base"

    def publish(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        visibility: str = "private",
    ) -> PublishResult:
        raise NotImplementedError
