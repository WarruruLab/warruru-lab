"""`codex-plugin/` 이 실재하는 형식인지, 그리고 규칙이 두 벌로 갈라지지 않는지.

플러그인은 저장소 밖(다른 프로젝트)에서 로드된다. 거기서는 `AGENTS.md` 도
`topics.py` 도 안 읽히므로 SKILL.md 가 규칙의 **유일한 사본**이 된다.
사본이 생기는 순간 원본과 어긋나기 시작하는데, 그 어긋남은 다른 저장소에서만
드러나서 여기서는 영영 안 보인다. 그래서 여기서 붙잡는다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from warruru_local.topics import RECOMMENDED_SLUGS

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "codex-plugin" / "warruru"
SKILL = PLUGIN / "skills" / "warruru-recording" / "SKILL.md"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_플러그인_매니페스트가_코덱스가_읽는_자리에_있다():
    manifest = _json(PLUGIN / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == "warruru"
    # 이 두 키의 값은 codex 0.151.0 이 실제로 찾는 상대경로다.
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert (PLUGIN / manifest["mcpServers"]).exists()
    assert (PLUGIN / "skills").is_dir()


def test_마켓플레이스가_이_플러그인을_가리킨다():
    """**`.claude-plugin/` 이 오타가 아니다.**

    codex 0.151.0 은 마켓플레이스 매니페스트를 `.claude-plugin/marketplace.json`
    과 `.cursor-plugin/marketplace.json` 에서만 찾는다. `.codex-plugin/` 아래
    두거나 루트에 그냥 `marketplace.json` 으로 두면
    `marketplace root does not contain a supported manifest` 로 거절한다
    (2026-08-31 실측). 플러그인 매니페스트 쪽은 `.codex-plugin/plugin.json` 이
    맞아서, 두 디렉터리 이름이 서로 다른 것이 정상이다.
    """
    market = _json(ROOT / "codex-plugin" / ".claude-plugin" / "marketplace.json")
    entry, = [p for p in market["plugins"] if p["name"] == "warruru"]
    assert (ROOT / "codex-plugin" / entry["source"]).is_dir()


def test_mcp_연결은_PATH_의_이름을_쓴다():
    """절대경로를 적으면 public 저장소에 이 머신의 홈 경로가 올라간다."""
    server = _json(PLUGIN / ".mcp.json")["mcpServers"]["warruru"]
    assert server["command"] == "warruru-mcp"
    assert "/" not in server["command"]
    # Codex 에서 남긴 기록이 다른 도구로 집계되면 안 된다.
    assert server["env"]["WARRURU_TOOL"] == "codex"


def test_스킬에_설명이_있다():
    head = SKILL.read_text(encoding="utf-8").split("---")[1]
    assert re.search(r"^name: warruru-recording$", head, re.M)
    description, = re.findall(r"^description: (.+)$", head, re.M)
    # 설명이 곧 발동 조건이다. 짧으면 필요한 순간에 안 불린다.
    assert len(description) > 100


@pytest.mark.parametrize(
    "kind", ["EXPERIMENT", "TROUBLESHOOTING", "TECH_CHOICE", "CONCEPT"]
)
def test_네_가지_계기가_모두_적혀_있다(kind):
    assert kind in SKILL.read_text(encoding="utf-8")


def test_권장_슬러그_목록이_원본과_한_글자도_다르지_않다():
    """`topics.py` 가 원본이다. 여기서 갈라지면 다른 저장소에서만 틀린다."""
    listed = re.findall(r"`([a-z0-9-]+)`", SKILL.read_text(encoding="utf-8"))
    assert [s for s in listed if s in RECOMMENDED_SLUGS] == list(RECOMMENDED_SLUGS)
    assert set(RECOMMENDED_SLUGS) - set(listed) == set()
