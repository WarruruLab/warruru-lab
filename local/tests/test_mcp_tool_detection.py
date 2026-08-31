"""어느 에이전트가 붙었는지 어떻게 아는가.

플러그인 하나를 Codex 와 Claude Code 가 나눠 쓰면서 생긴 문제다.
`.mcp.json` 의 `WARRURU_TOOL` 은 두 에이전트에게 같은 값을 주므로,
그 값으로는 화면의 도구별 집계가 맞을 수가 없다.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from mcp.server.lowlevel.server import request_ctx

from warruru_local.mcp import server


class _Settings(SimpleNamespace):
    pass


def _connected(name: str | None):
    """clientInfo 를 실은 요청 컨텍스트를 세운다."""
    info = SimpleNamespace(name=name) if name is not None else None
    session = SimpleNamespace(client_params=SimpleNamespace(clientInfo=info))
    return request_ctx.set(SimpleNamespace(session=session))


@pytest.mark.parametrize(
    ("client_name", "expected"),
    [
        # 앞의 둘은 실제로 두 CLI 가 보내는 이름이다(2026-08-31 실측).
        ("codex-mcp-client", "codex"),   # 별칭. 기존 기록과 같은 이름으로 모은다
        ("claude-code", "claude-code"),  # 그대로라 별칭이 없다
        ("Cursor IDE", "cursor-ide"),    # 처음 보는 에이전트도 자기 이름으로 남는다
    ],
)
def test_클라이언트가_밝힌_이름으로_도구를_가른다(client_name, expected):
    token = _connected(client_name)
    try:
        assert server._detect_tool(_Settings(tool=None))() == expected
    finally:
        request_ctx.reset(token)


def test_환경변수가_추론을_이긴다():
    """사람이 직접 적은 값을 추론이 덮으면 안 된다."""
    token = _connected("codex-mcp-client")
    try:
        assert server._detect_tool(_Settings(tool="antigravity"))() == "antigravity"
    finally:
        request_ctx.reset(token)


def test_툴_호출_밖에서는_unknown_이고_터지지_않는다():
    """어댑터가 뜨는 시점에는 클라이언트가 아직 이름을 말하기 전이다."""
    assert server._detect_tool(_Settings(tool=None))() == "unknown"


def test_이름을_안_밝히면_unknown():
    token = _connected(None)
    try:
        assert server._detect_tool(_Settings(tool=None))() == "unknown"
    finally:
        request_ctx.reset(token)


def test_호출마다_다시_판단한다():
    """뜰 때 한 번 굳히면 영영 unknown 이다."""
    resolve = server._detect_tool(_Settings(tool=None))
    assert resolve() == "unknown"
    token = _connected("codex-mcp-client")
    try:
        assert resolve() == "codex"
    finally:
        request_ctx.reset(token)


def test_서비스가_호출마다_해석기를_부른다():
    from warruru_local.clock import SystemClock

    seen = []
    service = server.ToolService(
        SimpleNamespace(_client_instance_id="cli_1"),
        lambda: seen.append(1) or f"tool-{len(seen)}",
        SystemClock(),
    )
    assert service._base()["tool"] == "tool-1"
    assert service._base()["tool"] == "tool-2"
