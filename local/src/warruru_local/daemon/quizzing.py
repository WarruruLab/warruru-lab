"""문제를 풀며 개념을 익힌다 (명세 §2.17, 2026-10-05 추가).

시험이 닷새 남았을 때 995쪽을 읽고 문제를 푸는 순서는 거꾸로다.
**문제를 먼저 풀고, 틀린 것의 해설만 읽는다.** 해설이 곧 개념 공부이고,
맞힌 것은 다시 읽을 필요가 없다.

문제는 `~/.warruru/career/quiz/{자격증}/*.md` 에 산다. 한 파일이 한 세트,
`## ` 헤딩 하나가 한 문항이다. 에이전트가 쓰고 사람이 고친다 —
**데몬은 읽기만 한다.** 푼 기록만 DB(`quiz_attempt`)에 쌓인다.

```markdown
## 스프린트의 일반적인 기간은?

본문(지문·표·코드)

1) 1~3일
2) 2~4주

정답: 2
영역: M1
근거: 특강 2일차 [9:31]
해설: …
```

보기가 있으면 객관식이고, 없으면 서술·수행형이다. 서술형은 내 답을 적고
모범답안을 본 뒤 **스스로 채점한다** — 데몬 안에는 채점할 모델이 없고,
그것이 이 시험을 준비하는 정직한 방식이기도 하다.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from warruru_local import paths
from warruru_local.daemon import careerview

# 세트 이름은 파일 이름에서 온다. 주소에 실리니 경로가 될 수 있는 것은 막는다.
SET_NAME = re.compile(r"^[가-힣A-Za-z0-9 _-]{1,80}$")

AREAS = ("M1", "M2", "M3", "M4")

_HEAD = re.compile(r"^##\s+(.+?)\s*$")
_CHOICE = re.compile(r"^\s*([1-9])\)\s+(.*)$")
_FIELD = re.compile(r"^(정답|영역|근거|해설)\s*[:：]\s*(.*)$")
_FENCE = "```"
_NUMBER = re.compile(r"^\s*([1-9])\s*번?\s*$")

# 파일을 매번 다시 읽지 않는다. 1,000 문항이 넘으면 화면 하나에 수 MB 를
# 파싱하게 된다. 수정 시각이 바뀐 파일만 다시 읽는다.
_CACHE: dict[Path, tuple[float, dict]] = {}


def question_hash(set_name: str, heading: str) -> str:
    """문제의 이름. **해설을 고쳐도 같은 문제다** — 헤딩만 본다."""
    return hashlib.sha1(f"{set_name}\n{heading}".encode("utf-8")).hexdigest()[:16]


def _parse_block(set_name: str, heading: str, lines: list[str],
                 default_area: str) -> dict:
    body: list[str] = []
    choices: list[str] = []
    fields: dict[str, list[str]] = {}
    current: str | None = None
    fenced = False
    choice_open = False
    for line in lines:
        if line.strip().startswith(_FENCE):
            fenced = not fenced
            (fields[current] if current else body).append(line)
            continue
        if fenced:
            (fields[current] if current else body).append(line)
            continue
        field = _FIELD.match(line)
        if field:
            current = field.group(1)
            fields[current] = [field.group(2)]
            continue
        if current:
            fields[current].append(line)
            continue
        choice = _CHOICE.match(line)
        if choice and int(choice.group(1)) == len(choices) + 1:
            choices.append(choice.group(2).strip())
            choice_open = True
            continue
        if choice_open and line.strip():
            # 빈 줄 없이 바로 이어지는 줄은 앞 보기가 길어 넘어온 것이다.
            choices[-1] += " " + line.strip()
            continue
        choice_open = False
        body.append(line)

    def 글(name: str) -> str:
        return "\n".join(fields.get(name, [])).strip()

    area = 글("영역").upper()[:2]
    if area not in AREAS:
        area = default_area
    answer = 글("정답")
    if choices:
        number = _NUMBER.match(answer)
        if number and int(number.group(1)) <= len(choices):
            answer = number.group(1)
        elif number:
            answer = ""
        else:
            # **정답이 번호가 아니면 객관식이 아니다.** 서술형 지문의 소물음이
            # `1) …` 로 적힌 것이다. 보기로 읽으면 모범답안 속 첫 숫자가
            # 정답 번호가 되어, 틀린 채점을 조용히 내놓는다. 지문으로 되돌린다.
            body.extend(f"{i}) {c}" for i, c in enumerate(choices, 1))
            choices = []
    return {
        "hash": question_hash(set_name, heading),
        "set": set_name,
        "heading": heading,
        "body": "\n".join(body).strip(),
        "choices": choices,
        "kind": "choice" if choices else "free",
        "answer": answer,
        "area": area,
        "basis": 글("근거"),
        "explain": 글("해설"),
    }


def parse_set(path: Path) -> dict | None:
    """세트 한 장. 이름이 주소로 못 쓰일 꼴이면 없는 것으로 본다."""
    name = path.stem
    if not SET_NAME.match(name):
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    meta, body = careerview.parse_front_matter(text)
    default_area = str(meta.get("area", "")).upper()[:2]
    if default_area not in AREAS:
        default_area = "M1"

    questions: list[dict] = []
    seen: set[str] = set()
    heading: str | None = None
    lines: list[str] = []
    fenced = False

    def _close() -> None:
        if heading is None:
            return
        q = _parse_block(name, heading, lines, default_area)
        # 정답이 없는 문항은 풀 수 없다. 같은 헤딩은 같은 문제라 하나만 둔다.
        if q["answer"] and q["hash"] not in seen:
            seen.add(q["hash"])
            questions.append(q)

    for line in body.splitlines():
        if line.strip().startswith(_FENCE):
            fenced = not fenced
        head = None if fenced else _HEAD.match(line)
        if head:
            _close()
            heading, lines = head.group(1), []
            continue
        if heading is not None:
            lines.append(line)
    _close()

    return {
        "name": name,
        "title": str(meta.get("title") or name),
        "source": str(meta.get("source") or ""),
        "area": default_area,
        "questions": questions,
    }


def load(home: Path, cert_key: str) -> list[dict]:
    """이 자격증의 세트 전부. 폴더가 없으면 빈 목록이다 — 고장이 아니다."""
    root = paths.quiz_dir(home) / cert_key
    if not root.is_dir():
        return []
    sets = []
    for path in sorted(root.glob("*.md")):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        cached = _CACHE.get(path)
        if cached and cached[0] == mtime:
            made = cached[1]
        else:
            made = parse_set(path)
            if made is None:
                continue
            _CACHE[path] = (mtime, made)
        sets.append(made)
    return sets


def all_questions(sets: list[dict]) -> list[dict]:
    return [q for s in sets for q in s["questions"]]


def find(sets: list[dict], q_hash: str) -> dict | None:
    return next((q for q in all_questions(sets) if q["hash"] == q_hash), None)


def _filtered(sets: list[dict], area: str = "", set_name: str = "",
              source: str = "") -> list[dict]:
    out = []
    for s in sets:
        if set_name and s["name"] != set_name:
            continue
        if source and s["source"] != source:
            continue
        out.extend(q for q in s["questions"] if not area or q["area"] == area)
    return out


def pick_next(sets: list[dict], state: dict[str, dict], *, area: str = "",
              set_name: str = "", source: str = "", only_wrong: bool = False,
              after: str = "") -> dict | None:
    """다음에 낼 문제.

    순서는 **안 푼 것 → 지금 틀린 것(많이 틀린 것부터) → 끝** 이다.
    맞힌 것은 다시 내지 않는다 — 닷새 안에 할 일은 모르는 것을 줄이는 것이다.
    `only_wrong` 이면 안 푼 것을 건너뛴다.

    `after` 는 방금 푼 문제다. 틀린 것만 남았을 때 같은 문제가 바로 다시
    나오면 답을 외워서 맞히게 되므로, 다른 것이 있으면 그것을 먼저 낸다.
    """
    pool = _filtered(sets, area, set_name, source)
    if not only_wrong:
        for q in pool:
            if q["hash"] not in state:
                return q
    wrong = [q for q in pool
             if q["hash"] in state and not state[q["hash"]]["last"]]
    wrong.sort(key=lambda q: (-state[q["hash"]]["wrongs"], state[q["hash"]]["at"]))
    others = [q for q in wrong if q["hash"] != after]
    if others:
        return others[0]
    return wrong[0] if wrong else None


def tally(questions: list[dict], state: dict[str, dict]) -> dict:
    """`{total, solved, right, wrong, rate}`. rate 는 푼 것 중 지금 맞히는 비율."""
    total = len(questions)
    solved = [q for q in questions if q["hash"] in state]
    right = sum(1 for q in solved if state[q["hash"]]["last"])
    return {
        "total": total,
        "solved": len(solved),
        "right": right,
        "wrong": len(solved) - right,
        "rate": round(right * 100 / len(solved)) if solved else None,
    }


def overview(sets: list[dict], state: dict[str, dict]) -> dict:
    """영역별 · 세트별 집계. **영역별 정답률이 곧 진단표다** — 노트에 손으로
    채우려던 표를 푼 만큼 화면이 채운다."""
    questions = all_questions(sets)
    areas = []
    for area in AREAS:
        mine = [q for q in questions if q["area"] == area]
        areas.append({"key": area, **tally(mine, state)})
    rows = []
    for s in sets:
        rows.append({
            "name": s["name"], "title": s["title"], "source": s["source"],
            "area": s["area"], **tally(s["questions"], state),
        })
    sources = sorted({s["source"] for s in sets if s["source"]})
    return {"all": tally(questions, state), "areas": areas, "sets": rows,
            "sources": sources}


def grade(question: dict, picked: str) -> bool:
    """객관식만 여기서 채점한다. 서술형은 사람이 맞음/틀림을 고른다."""
    return question["kind"] == "choice" and picked == question["answer"]
