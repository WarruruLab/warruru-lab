"""회사별 대조 스킬. 매핑 표가 로드맵과 어긋나지 않는지 붙잡는다.

이 표는 공고의 말(`Redis`, `Kubernetes`)과 기록의 슬러그(`redis-ttl-eviction`,
`k8s-probe`)를 잇는 유일한 다리다. 한쪽만 바뀌면 대조가 조용히 비어 보이고,
"빈 곳" 목록이 틀린 공부 계획이 된다.
"""

from __future__ import annotations

import re
from pathlib import Path

from warruru_local.topics import RECOMMENDED_SLUGS

SKILL = (
    Path(__file__).resolve().parents[2]
    / "agent-plugin/warruru/skills/career-prep/SKILL.md"
)


def _table_slugs() -> list[str]:
    """표의 행에서만 슬러그를 걷는다. 본문의 예시는 세지 않는다."""
    found = []
    for line in SKILL.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and "`" in line:
            found += re.findall(r"`([a-z0-9-]+)`", line)
    return found


def test_설명이_발동_조건을_담고_있다():
    head = SKILL.read_text(encoding="utf-8").split("---")[1]
    assert re.search(r"^name: career-prep$", head, re.M)
    description, = re.findall(r"^description: (.+)$", head, re.M)
    assert len(description) > 100


def test_매핑_표가_로드맵_100개를_빠짐없이_덮는다():
    slugs = _table_slugs()
    assert set(slugs) == set(RECOMMENDED_SLUGS)


def test_한_슬러그가_두_줄에_걸치지_않는다():
    """겹치면 같은 기록이 두 키워드에 세어져 빈 곳이 실제보다 적어 보인다."""
    slugs = _table_slugs()
    assert len(slugs) == len(set(slugs))


def test_산출물이_저장소_밖이다():
    """origin 이 public 이다. 자소서와 회사 조사는 여기 들어오면 안 된다."""
    body = SKILL.read_text(encoding="utf-8")
    assert "~/.warruru/career/" in body
    assert "저장소 안에 쓰지 않는다" in body


def test_노션은_단방향으로만_읽는다():
    body = SKILL.read_text(encoding="utf-8")
    assert "되쓰지 않는다" in body


def test_표를_쓰지_말라고_적혀_있다():
    """`/career` 의 렌더러가 마크다운 표를 모른다.

    스킬이 표로 쓰면 파이프 문자가 그대로 문단으로 나온다. 렌더러를 고치는
    대신 쓰는 쪽을 맞췄으므로, 그 약속이 사라지면 화면이 조용히 지저분해진다.
    """
    body = SKILL.read_text(encoding="utf-8")
    assert "마크다운 표" in body and "쓰지 않는다" in body


def test_렌더러가_아직_표를_모른다():
    """위 규칙의 전제. 표를 지원하게 되면 이 테스트가 깨지고,
    그때 스킬의 금지 문구를 걷으면 된다."""
    from warruru_local.publish import tistory_clipboard

    html = tistory_clipboard.to_html("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table" not in html
