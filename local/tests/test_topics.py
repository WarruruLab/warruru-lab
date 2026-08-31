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


def test_결손_목록은_필수_먼저_선택_나중_순서다():
    values = {k: None for k in FULL}
    assert topics.missing_fields(values) == list(
        topics.REQUIRED_FIELDS + topics.OPTIONAL_FIELDS
    )


def test_공백뿐인_필수_필드도_결손으로_본다():
    """거절하지도, 조용히 담지도 않는다 (2026-08-18 확정).

    거절하면 '기록 안 하기'가 가장 안전한 선택이 되고,
    조용히 빈 채로 담으면 목록에서 안 보이면서 성공한 것처럼 보인다.
    """
    assert topics.missing_fields(dict(FULL, title="   ")) == ["title"]


def test_공백뿐인_필수_필드는_예시에서_자리표시자가_된다():
    values = dict(FULL, title="   ")
    example = topics.example_call(values, topics.missing_fields(values))
    assert 'title="..."' in example


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
    assert in_doc, "부록 A 에서 슬러그를 하나도 찾지 못했다 — 문서 구조가 바뀌었나"
    # 양방향이다. 한쪽만 보면 '문서에 없는 슬러그를 지어내지 않는다' 를 못 지킨다.
    assert in_doc == set(topics.RECOMMENDED_SLUGS)


# ── 경계 ───────────────────────────────────────────────────────────

def test_topics_는_다른_모듈을_임포트하지_않는다():
    """어댑터가 데몬 없이 혼자 계산할 수 있어야 한다. 임포트가 그 경계다."""
    import ast
    from pathlib import Path

    source = Path(topics.__file__).read_text(encoding="utf-8")
    offenders = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            offenders.update(
                alias.name for alias in node.names
                if alias.name.startswith("warruru_local")
            )
        elif isinstance(node, ast.ImportFrom):
            # 상대 임포트(`from . import spool`)는 module 에 패키지 이름이
            # 안 담긴다. level 을 안 보면 경계가 뚫려도 이 테스트가 통과한다.
            if node.level > 0:
                offenders.add("." * node.level + (node.module or ""))
            elif (node.module or "").startswith("warruru_local"):
                offenders.add(node.module)

    assert offenders == set(), f"이 모듈은 패키지 안의 무엇도 임포트하면 안 된다: {offenders}"


def test_예시_재호출은_문법이_맞는_파이썬이다():
    """이 문자열의 유일한 용도가 복사해서 다시 부르는 것이다.

    본문은 6단 마크다운이라 줄바꿈이 들어 있다. 따옴표만 바꿔치기하면
    닫히지 않은 문자열이 나가고, 그걸 받은 에이전트는 보강을 포기한다.
    """
    import ast

    values = dict(FULL, body="## 문제\n풀이 말랐다.\n\n## 선택\n\"인용\" 과 역슬래시 \\")
    example = topics.example_call(values, ["outcome"])
    ast.parse(example)


def test_긴_값은_자리표시자로_줄인다():
    values = dict(FULL, body="가" * (topics.ECHO_MAX + 1))
    example = topics.example_call(values, ["outcome"])
    assert 'body="..."' in example
    assert "가" * 20 not in example


def test_짧은_값은_그대로_실어_복사만으로_끝나게_한다():
    example = topics.example_call(FULL, ["outcome"])
    assert '"커넥션 풀"' in example


def test_이미_채운_선택_필드도_예시에_남는다():
    """빼면 그 예시를 복사한 순간 사용자가 이미 준 근거가 사라진다."""
    values = dict(FULL, outcome=None, limitation=None)
    example = topics.example_call(values, topics.missing_fields(values))
    assert "rationale=" in example
    assert '"근거"' in example


def test_숫자_0_은_결손이_아니다():
    """`not value` 로 판정하면 0 과 False 가 결손으로 보고된다."""
    assert topics.missing_fields(dict(FULL, outcome=0)) == []


# ── is_recommended (A13) ──────────────────────────────────────────

def test_권장_슬러그는_권장으로_표시된다():
    """로드맵 문서와 힌트 장치가 이어져 있다는 것을 값 하나로 증명한다.

    `similar_slugs` 로는 증명할 수 없다 — 그쪽은 자기 자신을 빼므로
    권장 슬러그를 그대로 적으면 오히려 빈 목록이 온다(A13 채점 참조).
    """
    assert topics.is_recommended("net-tcp") is True
    assert topics.is_recommended(topics.RECOMMENDED_SLUGS[0]) is True


def test_권장_목록에_없으면_권장이_아니다():
    assert topics.is_recommended("connection-pool") is False
    assert topics.is_recommended("") is False
    assert topics.is_recommended(None) is False


def test_권장_판정은_슬러그를_다시_만들지_않는다():
    """이미 슬러그인 값만 받는다. 원문을 넣으면 아니라고 답한다 —
    정규화를 두 곳에서 하면 한쪽만 바뀌었을 때 조용히 어긋난다.
    """
    assert topics.is_recommended("Net TCP") is False


# ── material_fill — 재료 막대의 재료 ────────────────────────────────

def test_재료_막대는_네_칸이_항상_같은_순서다():
    """칸 순서가 주제마다 바뀌면 화면에서 비교가 안 된다.
    글 한 편에 필요한 네 필드를 고정 순서로 돌려준다.
    """
    fill = topics.material_fill([{"rationale": "있다"}])
    assert [item["field"] for item in fill] == list(topics.MATERIAL_FIELDS)


def test_채워진_칸과_빈_칸을_센다():
    records = [
        {"rationale": "a", "outcome": "b", "limitation": None, "interview": ""},
        {"rationale": "c", "outcome": None, "limitation": None, "interview": ""},
    ]
    by = {item["field"]: item for item in topics.material_fill(records)}
    assert by["rationale"]["filled"] == 2
    assert by["outcome"]["filled"] == 1
    assert by["limitation"]["filled"] == 0
    assert all(item["total"] == 2 for item in by.values())


def test_공백만_있으면_비어_있는_것으로_본다():
    """shortages 와 같은 규칙을 쓴다. 두 곳이 다르게 세면
    막대와 '부족한 필드' 문장이 서로 다른 말을 한다.
    """
    fill = {i["field"]: i for i in topics.material_fill([{"rationale": "   "}])}
    assert fill["rationale"]["filled"] == 0


def test_기록이_없으면_전부_0이다():
    fill = topics.material_fill([])
    assert all(item["filled"] == 0 and item["total"] == 0 for item in fill)


# ── 슬러그 묶음 (2026-08-31) ─────────────────────────────────────────

def test_묶음이_로드맵_100개를_빠짐없이_덮는다():
    """덮지 못하면 기술스택 화면에서 그 슬러그가 조용히 사라진다."""
    from warruru_local.topics import RECOMMENDED_SLUGS, SLUG_GROUPS

    flat = [slug for _, slugs in SLUG_GROUPS for slug in slugs]
    assert set(flat) == set(RECOMMENDED_SLUGS)


def test_한_슬러그가_두_묶음에_걸치지_않는다():
    """겹치면 기술스택 화면의 '몇 개 중 몇 개' 가 실제보다 커진다."""
    from warruru_local.topics import SLUG_GROUPS

    flat = [slug for _, slugs in SLUG_GROUPS for slug in slugs]
    assert len(flat) == len(set(flat))
