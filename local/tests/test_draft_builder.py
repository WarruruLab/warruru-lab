"""결정적 6단 조립기 — **LLM 을 한 번도 호출하지 않는다.**

빈 절은 지우지 않고 TODO 로 남긴다. 그래서 조립기 자체가 재료 부족 진단기이자
다음 기록에 대한 압력이 된다. 빈 절을 지워 매끈해 보이는 초안은 미달이다.
"""

from warruru_local.daemon import draft

RECORDS = [
    {
        "record_id": "rec_A",
        "kind": "EXPERIMENT",
        "topic": "connection pool",
        "title": "풀 크기 10→30",
        "body": "p95 가 320ms 에서 90ms 로 떨어졌다.",
        "rationale": "커넥션 대기가 병목이라고 봤다",
        "outcome": "p95 90ms",
        "limitation": None,
        "interview": None,
        "occurred_at": "2026-08-24T07:00:00.000Z",
        "project": "산책온",
    },
    {
        "record_id": "rec_B",
        "kind": "TROUBLESHOOTING",
        "topic": "connection pool",
        "title": "풀 고갈로 타임아웃",
        "body": "대기 큐가 가득 차 504 가 났다.",
        "rationale": None,
        "outcome": None,
        "limitation": "30 이상은 DB 쪽 한계로 못 올린다",
        "interview": None,
        "occurred_at": "2026-08-24T09:00:00.000Z",
        "project": "산책온",
    },
]

SECTIONS = ["## 문제", "## 선택", "## 구현", "## 측정", "## 결과", "## 한계"]


def test_6단_제목이_순서대로_들어간다():
    """31주차에 이 파일을 위에서 아래로 읽는 것만으로 서사가 나와야 한다."""
    markdown = draft.build(RECORDS)
    positions = [markdown.index(title) for title in SECTIONS]
    assert positions == sorted(positions)


def test_재료가_없는_절에는_TODO_가_남는다():
    """빈 절을 지우면 조립기가 재료 부족 진단기 노릇을 못 한다."""
    sparse = [dict(RECORDS[1])]        # rationale · outcome 이 비어 있다
    markdown = draft.build(sparse)
    assert markdown.count("TODO: 여기서 무엇을 판단했는가?") >= 2


def test_측정과_결과는_같은_문장을_반복하지_않는다():
    """숫자가 든 줄은 측정으로, 나머지는 결과로 간다.

    어림짐작이라 틀릴 때가 있지만 결정적이고, 두 절이 똑같은 문장을
    반복하는 것보다는 낫다. 틀리면 사람이 초안에서 옮긴다.
    """
    records = [dict(RECORDS[0], outcome="p95 90ms 로 내려갔다\n대기가 사라졌다")]
    markdown = draft.build(records)
    measured = markdown.split("## 측정")[1].split("## 결과")[0]
    rest = markdown.split("## 결과")[1].split("## 한계")[0]
    assert "p95 90ms" in measured and "대기가 사라졌다" not in measured
    assert "대기가 사라졌다" in rest and "p95 90ms" not in rest


def test_구현_절에는_트러블슈팅_본문이_오지_않는다():
    """body 가 '문제' 와 '구현' 양쪽에 오므로, kind 로 좁혀 반복을 줄인다."""
    markdown = draft.build(RECORDS)
    implementation = markdown.split("## 구현")[1].split("## 측정")[0]
    assert "대기 큐가 가득 차" not in implementation
    assert "p95 가 320ms" in implementation


def test_재료가_있으면_TODO_대신_그_내용이_들어간다():
    markdown = draft.build(RECORDS)
    assert "커넥션 대기가 병목이라고 봤다" in markdown
    assert "30 이상은 DB 쪽 한계로 못 올린다" in markdown


def test_같은_입력이면_같은_마크다운이_나온다():
    """결정적이다. 시각도 난수도 LLM 도 들어가지 않는다."""
    assert draft.build(RECORDS) == draft.build(RECORDS)


def test_기록_순서가_바뀌어도_같은_결과다():
    """조립은 기록의 시간순으로 하되, 입력 순서에는 기대지 않는다."""
    assert draft.build(RECORDS) == draft.build(list(reversed(RECORDS)))


def test_source_record_ids_가_초안에_기록된다():
    markdown = draft.build(RECORDS)
    assert "rec_A" in markdown and "rec_B" in markdown


def test_기록이_하나여도_6단이_그대로_나온다():
    markdown = draft.build(RECORDS[:1])
    for title in SECTIONS:
        assert title in markdown


def test_제목은_원문_topic_을_쓴다():
    assert draft.build(RECORDS).startswith("# connection pool")


def test_기록이_없으면_빈_문자열이_아니라_예외다():
    """재료 0건으로 초안을 만들 일은 없다. 조용히 빈 파일을 쓰면 더 나쁘다."""
    import pytest

    with pytest.raises(ValueError):
        draft.build([])


def test_LLM_을_부르지_않는다():
    """네트워크가 끊긴 채로도 눌러야 한다. 임포트로 확인한다."""
    import ast
    import pathlib

    source = pathlib.Path(draft.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not ({"httpx", "requests", "urllib", "openai"} & imported)


def _record(**extra):
    """한 건짜리 기록. 절 매핑을 시험할 때는 최소한만 채우고 나머지를 준다."""
    row = {
        "record_id": "rec_X", "kind": "EXPERIMENT", "topic": "connection pool",
        "title": "제목", "body": "", "rationale": None, "outcome": None,
        "limitation": None, "interview": None,
        "occurred_at": "2026-08-25T07:00:00.000Z", "project": None,
    }
    row.update(extra)
    return row

# ── 발행 본문과 정본을 가른다 ───────────────────────────────────────

def test_꼬리말을_뺀_본문을_돌려준다():
    """꼬리말은 **정본 파일에는 남고 발행 본문에서는 빠진다.**

    파일만 열어도 재료를 되짚을 수 있어야 한다는 이유로 넣은 줄인데,
    티스토리 독자에게 rec_01M0… 은 아무 뜻이 없다.
    """
    text = draft.build([_record(body="본문")])
    assert "조립에 쓴 기록" in text
    assert "조립에 쓴 기록" not in draft.body_only(text)
    assert "본문" in draft.body_only(text)


def test_꼬리말이_없으면_그대로_둔다():
    """사람이 다듬어 save_draft 로 덮어쓴 글에는 꼬리말이 없을 수 있다."""
    assert draft.body_only("# 제목\n\n본문") == "# 제목\n\n본문"


def test_본문_안의_구분선은_건드리지_않는다():
    """다듬은 글이 가로줄을 쓸 수 있다. 마지막 --- 라고 다 꼬리말이 아니다."""
    text = "# 제목\n\n앞\n\n---\n\n뒤"
    assert draft.body_only(text) == text


# ── 어느 절이 빌 것인가 ────────────────────────────────────────────

def test_채울_수_없는_절을_미리_알려준다():
    """재료 막대가 4/4 여도 초안에 빈 절이 남을 수 있다.

    막대는 **필드**를 보고 조립기는 **kind** 도 본다. CONCEPT 한 건짜리
    주제는 '구현' 절을 영원히 못 채운다 — 누르기 전에 알아야 한다.
    """
    concept = _record(kind="CONCEPT", body="본문", rationale="근거",
                      outcome="p95 90ms", limitation="한계")
    assert draft.empty_sections([concept]) == ["구현", "결과"]


def test_다_채우면_빈_절이_없다():
    full = _record(kind="EXPERIMENT", body="본문", rationale="근거",
                   outcome="p95 90ms\n대기가 사라졌다", limitation="한계")
    assert draft.empty_sections([full]) == []


def test_빈_절_목록은_실제_초안과_어긋나지_않는다():
    """두 곳이 따로 판단하면 화면과 파일이 다른 말을 한다."""
    rows = [_record(kind="CONCEPT", body="본문")]
    text = draft.build(rows)
    for name in ("문제", "선택", "구현", "측정", "결과", "한계"):
        section = text.split(f"## {name}")[1].split("##")[0]
        assert (draft.TODO in section) == (name in draft.empty_sections(rows))
