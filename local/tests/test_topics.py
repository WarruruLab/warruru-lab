"""`topics.py` 는 입력만으로 답이 나오는 순수 모듈이다.

데몬이 꺼진 SPOOL 응답에서도 `topic_slug` 와 결손 필드는 채워져야 하고,
`mcp/` 는 `daemon/` 을 임포트하지 않으므로 어댑터가 혼자 계산할 수 있어야 한다.
"""

import pytest

from warruru_local import topics


# ── slugify ────────────────────────────────────────────────────────

@pytest.mark.parametrize("original,expected", [
    ("connection pool", "connection-pool"),
    ("Connection Pool", "connection-pool"),
    ("  Connection_Pool  ", "connection-pool"),
    ("JPA N+1", "jpa-n1"),
    ("cache--aside", "cache-aside"),
    ("-redis-", "redis"),
])
def test_공백과_대문자를_슬러그로_바꾼다(original, expected):
    assert topics.slugify(original) == expected


def test_표기가_달라도_한_슬러그로_모인다():
    """이게 이 모듈의 존재 이유다. 갈라지면 같은 이야기를 두 번 쓰게 된다."""
    variants = ["connection pool", "Connection Pool", " Connection_Pool ",
                "CONNECTION-POOL"]
    assert len({topics.slugify(v) for v in variants}) == 1


def test_NFKC_로_정규화한다():
    """전각 문자와 반각 문자가 다른 주제가 되면 안 된다."""
    assert topics.slugify("ＲＥＤＩＳ") == topics.slugify("redis")


def test_언더스코어는_하이픈이_된다():
    assert topics.slugify("cache_aside") == "cache-aside"


def test_연속_하이픈을_하나로_줄인다():
    assert topics.slugify("a -- b") == "a-b"


def test_한글_주제는_한글_슬러그가_된다():
    """한글을 버리면 모든 한글 주제가 한 덩어리로 뭉친다.

    로드맵의 권장 슬러그는 전부 영문이라 충돌하지 않는다.
    """
    assert topics.slugify("커넥션 풀") == "커넥션-풀"
    assert topics.slugify("커넥션 풀") != topics.slugify("트랜잭션 격리")


def test_슬러그로_만들_수_없으면_기타로_모은다():
    """비어 있는 집계 키를 만들 수는 없다. 화면의 '미분류' 구획에서 눈에 띈다."""
    assert topics.slugify("???") == topics.FALLBACK_SLUG
    assert topics.slugify("   ") == topics.FALLBACK_SLUG


def test_슬러그는_다시_통과시켜도_그대로다():
    for original in ["Connection Pool", "커넥션 풀", "JPA N+1", "???"]:
        once = topics.slugify(original)
        assert topics.slugify(once) == once


# ── missing_fields · example_call ──────────────────────────────────

FULL = {
    "kind": "EXPERIMENT", "topic": "커넥션 풀", "title": "제목", "body": "본문",
    "rationale": "근거", "outcome": "결과", "limitation": "한계", "interview": "문장",
}


def test_다_채우면_결손이_없다():
    assert topics.missing_fields(FULL) == []


def test_비어_있는_선택_필드를_돌려준다():
    values = dict(FULL, rationale=None, limitation="")
    assert set(topics.missing_fields(values)) == {"rationale", "limitation"}


def test_공백뿐인_선택_필드는_결손으로_본다():
    assert "outcome" in topics.missing_fields(dict(FULL, outcome="   "))


def test_결손_목록은_필드_정의_순서를_따른다():
    values = {k: None for k in FULL}
    assert topics.missing_fields(values) == list(topics.OPTIONAL_FIELDS)


def test_예시_재호출에_결손_필드가_들어_있다():
    values = dict(FULL, outcome=None, limitation=None)
    missing = topics.missing_fields(values)
    example = topics.example_call(values, missing)
    assert "record_learning(" in example
    assert "outcome=" in example and "limitation=" in example


def test_예시_재호출은_필수_필드를_그대로_되돌려_준다():
    """복사해서 바로 다시 부를 수 있어야 한다. 다시 타이핑하게 만들면 안 채운다."""
    example = topics.example_call(FULL, ["outcome"])
    assert "커넥션 풀" in example and "EXPERIMENT" in example


def test_결손이_없으면_예시도_없다():
    assert topics.example_call(FULL, []) == ""


# ── 권장 슬러그 ────────────────────────────────────────────────────

def test_권장_슬러그는_전부_slugify_를_다시_통과해도_그대로다():
    """문서에 대문자나 공백이 섞여 들어오면 힌트가 DB 슬러그와 영영 맞지 않는다."""
    for slug in topics.RECOMMENDED_SLUGS:
        assert topics.slugify(slug) == slug, f"{slug} 는 정규화된 형태가 아니다"


def test_권장_슬러그에_중복이_없다():
    assert len(set(topics.RECOMMENDED_SLUGS)) == len(topics.RECOMMENDED_SLUGS)


def test_로드맵_문서의_슬러그가_전부_들어_있다():
    """문서가 곧 데이터다. 옮겨 적기가 빠지면 힌트가 그만큼 비어 있게 된다."""
    import re
    from pathlib import Path

    doc = Path(__file__).resolve().parents[2] / "docs/guides/backend-infra-roadmap-31w.md"
    text = doc.read_text(encoding="utf-8")
    section = text[text.index("## 부록 A."):text.index("## 부록 B.")]
    in_doc = {s for s in re.findall(r"`([a-z0-9][a-z0-9-]*)`", section)
              if not s.endswith(".py") and "/" not in s}
    assert in_doc <= set(topics.RECOMMENDED_SLUGS)


# ── 경계 ───────────────────────────────────────────────────────────

def test_topics_는_다른_모듈을_임포트하지_않는다():
    """어댑터가 데몬 없이 혼자 계산할 수 있어야 한다. 임포트가 그 경계다."""
    import ast
    from pathlib import Path

    source = Path(topics.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    warruru = {name for name in imported if name.startswith("warruru_local")}
    assert warruru == set(), f"이 모듈은 아무것도 임포트하면 안 된다: {warruru}"
