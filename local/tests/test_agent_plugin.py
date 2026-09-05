"""`agent-plugin/` 이 실재하는 형식인지, 그리고 규칙이 두 벌로 갈라지지 않는지.

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
PLUGIN = ROOT / "agent-plugin" / "warruru"
SKILL = PLUGIN / "skills" / "warruru-recording" / "SKILL.md"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_매니페스트_한_벌로_두_에이전트를_덮는다():
    """`.claude-plugin/plugin.json` 하나를 Codex 와 Claude Code 가 같이 읽는다.

    Codex 는 `.codex-plugin/` · `.claude-plugin/` · `.cursor-plugin/` 셋 다
    인식하고, Claude Code 는 `.claude-plugin/` 만 인식한다(2026-08-31 실측).
    교집합이 하나뿐이라 그쪽으로 모은다 — 매니페스트를 두 벌 두면 어긋난다.
    """
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == "warruru"
    # 이 두 키의 값은 두 CLI 가 실제로 찾는 상대경로다.
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
    (2026-08-31 실측). Claude Code 쪽도 같은 자리를 본다.
    """
    market = _json(ROOT / "agent-plugin" / ".claude-plugin" / "marketplace.json")
    entry, = [p for p in market["plugins"] if p["name"] == "warruru"]
    assert (ROOT / "agent-plugin" / entry["source"]).is_dir()


def test_mcp_연결은_PATH_의_이름을_쓴다():
    """절대경로를 적으면 public 저장소에 이 머신의 홈 경로가 올라간다."""
    server = _json(PLUGIN / ".mcp.json")["mcpServers"]["warruru"]
    assert server["command"] == "warruru-mcp"
    assert "/" not in server["command"]


def test_공용_mcp_설정에_도구_이름을_박지_않는다():
    """`WARRURU_TOOL` 을 여기 적으면 이 파일을 읽는 **모든** 에이전트가 같은
    이름으로 기록된다. Codex 용으로 적어 둔 값이 Claude Code 기록에 붙어
    도구별 집계가 조용히 틀렸다(2026-08-31). 이제 어댑터가 MCP 핸드셰이크의
    `clientInfo` 로 가른다 — `test_mcp_tool_detection.py` 가 그쪽을 본다.
    """
    server = _json(PLUGIN / ".mcp.json")["mcpServers"]["warruru"]
    assert "WARRURU_TOOL" not in server.get("env", {})


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


def test_CS_슬러그도_빠짐없이_실려_있다():
    """로드맵 밖 주제라 `recommended` 는 false 지만, 표기가 갈리면 안 되는 것은
    똑같다. 에이전트가 목록을 못 보면 `자료구조` 같은 한글 슬러그가 생긴다.
    """
    from warruru_local.topics import CS_SLUGS

    listed = re.findall(r"`([a-z0-9-]+)`", SKILL.read_text(encoding="utf-8"))
    assert set(CS_SLUGS) - set(listed) == set()


def test_AI_슬러그도_빠짐없이_실려_있다():
    """`topics.py` 에만 있고 스킬에 없으면, 다른 저장소에서 에이전트가
    `mcp` 같은 즉석 슬러그를 만들어 낸다. 그 기록은 어느 화면에도 안 뜬다.
    """
    from warruru_local.topics import AI_SLUGS

    listed = re.findall(r"`([a-z0-9-]+)`", SKILL.read_text(encoding="utf-8"))
    assert set(AI_SLUGS) - set(listed) == set()


# ── 세션마다 스킬 한 장 (2026-09-05 추가) ────────────────────────────

SKILLS_DIR = PLUGIN / "skills"
# 규칙 목록의 **원본을 들고 있는** 스킬. 각자 대조 테스트가 있다
# (`test_agent_plugin.py` · `test_career_skill.py`).
_원본 = {"warruru-recording", "career-prep"}


def _front(path: Path) -> dict:
    """앞머리의 `name` 과 `description` 만 본다."""
    text = path.read_text(encoding="utf-8")
    body = text.split("---")[1] if text.startswith("---") else ""
    made = {}
    for line in body.splitlines():
        key, sep, value = line.partition(":")
        if sep and not key.startswith(" "):
            made[key.strip()] = value.strip()
    return made


def test_스킬마다_이름이_디렉터리와_같다():
    """`name` 이 어긋나면 두 CLI 중 한쪽에서만 안 뜬다 — 어느 쪽인지도
    모르는 채로 '스킬이 안 붙네' 가 된다."""
    found = sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md"))
    assert found == ["blog-post", "career-prep", "exam-schedule",
                     "study-session", "warruru-recording"]
    for path in SKILLS_DIR.glob("*/SKILL.md"):
        front = _front(path)
        assert front.get("name") == path.parent.name, path
        assert len(front.get("description", "")) > 80, path


def test_기록_규칙은_한_스킬에만_있다():
    """`kind` 네 개를 나열한 파일이 둘이면 그 순간부터 갈라진다.

    이 프로젝트가 한 번 크게 실패한 방식이 '같은 것을 두 문서가 말하는 것'
    이었다(AGENTS.md §6). 스킬에서 같은 실패를 반복하지 않는다.
    """
    kinds = ("EXPERIMENT", "TROUBLESHOOTING", "TECH_CHOICE", "CONCEPT")
    가진_스킬 = [
        path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md")
        if all(kind in path.read_text(encoding="utf-8") for kind in kinds)
    ]
    assert 가진_스킬 == ["warruru-recording"]


def test_새_스킬은_슬러그_목록을_복사하지_않는다():
    """목록을 실으면 원본과 대조하는 테스트가 있어야 하는데, 없으면
    다른 저장소에서만 어긋나서 여기서는 영영 안 보인다."""
    for path in SKILLS_DIR.glob("*/SKILL.md"):
        if path.parent.name in _원본:
            continue
        listed = re.findall(r"`([a-z0-9-]+)`", path.read_text(encoding="utf-8"))
        겹침 = set(listed) & set(RECOMMENDED_SLUGS)
        assert len(겹침) <= 5, (path.parent.name, sorted(겹침))


def test_스킬끼리_담당을_서로_가리킨다():
    """다섯 장이 되면 '어느 스킬이 이 일을 하는가' 가 흐려진다.
    각 스킬이 남의 일을 자기 것으로 삼지 않도록 경계를 본문에 적어 둔다.
    """
    for name, 가리켜야 in {
        "study-session": ("warruru-recording", "exam-schedule", "career-prep",
                          "blog-post"),
        "exam-schedule": ("career-prep", "study-session"),
        "blog-post": ("warruru-recording",),
    }.items():
        text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        for 남 in 가리켜야:
            assert 남 in text, (name, 남)
