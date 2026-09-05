"""초안 다듬기 버튼(`scripts/polish.command`).

셸 스크립트라 파이썬 테스트가 실행까지는 못 본다. 대신 **되돌아오면
조용히 위험해지는 세 가지**를 소스에서 붙잡는다. 셋 다 "권한 오류가 나서
풀었다" 는 흔한 수정으로 깨지는 것들이다.
"""

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "polish.command"


@pytest.fixture(scope="module")
def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_스크립트가_실행_가능하다():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111, "chmod +x 가 빠지면 두 번 눌러도 안 열린다"


def test_API_키를_쓰지_않는다(source):
    """이 버튼의 존재 이유가 그것이다 — 구독 요금제로 돈다.

    API 키 경로로 바꾸면 같은 일이 토큰당 과금으로 바뀌는데, 화면도
    출력도 똑같아서 청구서가 오기 전까지 아무도 모른다.
    """
    for 금지 in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "--api-key", "api.openai.com"):
        assert 금지 not in source, 금지


def test_에이전트에게_쓰기_권한을_주지_않는다(source):
    """재료는 `get_topic_records` 로 읽고 결과는 `save_draft` 로 되돌린다.
    디스크에 손댈 일이 없다.

    초안은 `~/.warruru/drafts/` — **저장소 바깥**이다. 쓰기를 열어 두면
    그 경계를 지키는 것이 발행 어댑터 하나뿐이 된다.
    """
    assert "-s read-only" in source
    assert "danger-full-access" not in source
    assert "--dangerously-bypass-approvals-and-sandbox" not in source


def test_데몬이_꺼져_있으면_멈춘다(source):
    """꺼진 채로 부르면 `save_draft` 가 spool 로 새고, 다듬은 글은 다음
    기동까지 어디에도 안 보인다. 성공한 줄 알고 브라우저를 열었다가 옛
    초안을 보는 것이 가장 나쁜 결말이다.
    """
    assert "/v1/health" in source
    assert "exit 1" in source
