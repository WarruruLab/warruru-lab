"""결정적 6단 조립기. **LLM 을 한 번도 호출하지 않는다.**

문제 → 선택 → 구현 → 측정 → 결과 → 한계. 이 여섯은 31주차 면접에서
말해야 하는 순서이고, 그래서 초안의 절 순서가 그것과 같다.
파일을 위에서 아래로 읽는 것만으로 서사가 나와야 한다.

**빈 절은 지우지 않는다.** 재료가 없으면 `TODO:` 를 남긴다.
지워서 매끈해 보이는 초안은 재료가 부족하다는 사실을 감춘다 —
이 조립기는 글을 잘 쓰는 장치가 아니라 **재료 부족 진단기**이고,
빈 자리가 곧 "면접에서 대답 못 할 부분" 목록이다.

LLM 이 필요하면 사용자 앞에 이미 떠 있는 에이전트가 쓴다.
데몬 안에 넣으면 서비스 기동·모델·프롬프트·타임아웃·재시도가 전부 새로 필요하고,
네트워크가 끊기면 버튼이 죽는다.
"""

from __future__ import annotations

TODO = "TODO: 여기서 무엇을 판단했는가?"

# 필드 5개를 절 6개에 어떻게 붙일 것인가 (2026-08-24 확정.
# 평가 기준이 '확인 필요' 로 남겨 둔 항목이다).
#
# | 절   | 재료                                    |
# |------|-----------------------------------------|
# | 문제 | 모든 기록의 `body`                       |
# | 선택 | `rationale`                             |
# | 구현 | `body` 중 EXPERIMENT · TECH_CHOICE 만    |
# | 측정 | `outcome` 중 **숫자가 든 줄**            |
# | 결과 | `outcome` 중 나머지 줄                   |
# | 한계 | `limitation`                            |
#
# 두 가지가 겹친다. `body` 가 '문제' 와 '구현' 양쪽에 오는 것은, 기록 한 건의
# 본문에 상황과 조치가 함께 들어 있기 때문이다. 쪼개려면 기록 시점에 필드를
# 나눠 받아야 하는데 그건 기록 마찰을 키운다 — 이 프로젝트가 가장 경계하는 것이다.
# 대신 '구현' 은 kind 로 좁혀 트러블슈팅·개념 기록이 그 절에 다시 나오지 않게 했다.
#
# `outcome` 을 숫자 유무로 가르는 것은 **어림짐작**이다. "p95 90ms" 는 측정으로,
# "대기가 사라졌다" 는 결과로 간다. 틀릴 때가 있지만 결정적이고 LLM 이 없다.
# 틀리면 사람이 초안에서 옮기면 되고, 그 편이 두 절이 똑같은 문장을 반복하는
# 것보다 낫다. 나눌 것이 없으면 '측정' 은 TODO 로 남아 재료 부족을 알린다.
IMPLEMENTATION_KINDS = ("EXPERIMENT", "TECH_CHOICE")

SECTIONS = (
    ("문제", "body", None),
    ("선택", "rationale", None),
    ("구현", "body", IMPLEMENTATION_KINDS),
    ("측정", "outcome:measured", None),
    ("결과", "outcome:rest", None),
    ("한계", "limitation", None),
)

KIND_LABELS = {
    "EXPERIMENT": "실험",
    "TROUBLESHOOTING": "트러블슈팅",
    "TECH_CHOICE": "기술선택",
    "CONCEPT": "개념",
}


def build(records: list[dict]) -> str:
    """기록 묶음을 6단 마크다운 한 편으로 조립한다.

    결정적이다 — 같은 입력이면 언제나 같은 결과다. 시각도 난수도 들어가지 않는다.
    입력 순서에도 기대지 않는다: 안에서 시간순으로 다시 세운다.
    """
    if not records:
        # 재료 0건으로 초안을 만들 일은 없다. 조용히 빈 파일을 쓰면
        # 나중에 그 파일이 왜 비었는지 아무도 모른다.
        raise ValueError("기록이 없으면 초안을 만들 수 없다")

    ordered = sorted(
        records, key=lambda row: (row.get("occurred_at") or "", row["record_id"])
    )
    topic = ordered[-1].get("topic") or ordered[-1].get("topic_slug") or "제목 없음"

    lines = [f"# {topic}", ""]
    for heading, field, kinds in SECTIONS:
        lines.append(f"## {heading}")
        lines.append("")
        materials = _materials(ordered, field, kinds)
        if materials:
            lines.extend(materials)
        else:
            lines.append(TODO)
        lines.append("")

    lines.extend(_footer(ordered))
    return "\n".join(lines).rstrip() + "\n"


def _has_digit(text: str) -> bool:
    return any(character.isdigit() for character in text)


def _value_for(row: dict, field: str) -> str:
    """`outcome:measured` 처럼 한 필드를 둘로 가르는 경우를 여기서 처리한다."""
    if not field.startswith("outcome:"):
        return (row.get(field) or "").strip()

    lines = [line for line in (row.get("outcome") or "").splitlines() if line.strip()]
    measured = field.endswith("measured")
    picked = [line for line in lines if _has_digit(line) == measured]
    return "\n".join(picked).strip()


def _materials(
    records: list[dict], field: str, kinds: tuple[str, ...] | None
) -> list[str]:
    lines: list[str] = []
    for row in records:
        if kinds and row.get("kind") not in kinds:
            continue
        value = _value_for(row, field)
        if not value:
            continue
        label = KIND_LABELS.get(row.get("kind"), row.get("kind") or "기록")
        lines.append(f"**{label} · {row.get('title') or ''}**")
        lines.append("")
        lines.append(value)
        lines.append("")
    return lines[:-1] if lines else lines


def _footer(records: list[dict]) -> list[str]:
    """무엇으로 조립됐는지를 글 안에 남긴다.

    파일만 열어도 재료를 되짚을 수 있어야 한다 — 마크다운이 정본이고
    DB 는 그 정본을 찾아가는 색인이라는 순서와 같은 이유다.
    """
    ids = ", ".join(f"`{row['record_id']}`" for row in records)
    return ["---", "", f"조립에 쓴 기록 {len(records)}건: {ids}"]
