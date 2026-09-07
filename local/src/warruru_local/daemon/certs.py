"""자격증 — **오늘 뭐 하지**에 먼저 답한다 (명세 §2.11).

`cert_progress` 가 0건이었다. 만든 지 오래됐는데 한 번도 안 눌렸다.
CS 체크가 0이었던 것과 같은 모양이다 — **눌러도 아무 일이 안 생기니까
안 누른다.** 화면이 9줄을 두 번 펼쳐 놓고 "오늘 0.1" 이라고 말하면
아무것도 안 하게 된다.

그래서 셋을 바꾼다(2026-09-08 확정).

1. **오늘 할 것 셋이 맨 위**다. 나머지는 접는다.
2. **오늘 분량을 계산해서 말하지 않는다.** 무엇을 할지만 세우고 얼마나는
   내가 정한다. `남은 것 ÷ 남은 날` 은 항목마다 단위가 달라서
   (영역 · 문항 · 회독 · 세트) 뜻이 없는 소수를 만든다.
3. **자격증을 화면에서 늘리고 내린다.** 코드 상수에만 있으면 딴 것도
   안 볼 것도 영영 목록에 선다.
"""

from __future__ import annotations

import re

from warruru_local import paths
from warruru_local.daemon.careerview import parse_front_matter

# 오늘 칸에 세우는 최대 수. 셋을 넘으면 그것도 목록이 된다.
TODAY_MAX = 3

# 자격증 키는 그대로 파일 이름이 된다.
KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# 상태 넷. `합격` 은 예전 값이라 `보유` 와 같이 본다.
READY = "준비중"
HELD = ("보유", "합격")
DROPPED = "안 함"


def is_held(status: str) -> bool:
    return status in HELD


def is_dropped(status: str) -> bool:
    return status == DROPPED


def today_items(cert: dict) -> list[dict]:
    """오늘 세울 것. **마감이 가까운 단계부터** 최대 셋.

    일정 자체가 할 일인 경우가 있다 — 접수가 그렇다. 접수 단계에 커리큘럼이
    없으면 접수 마감 자체를 첫 줄로 세운다. D-4 로 제일 급한 칸이 비어
    있으면 그 화면은 급한 것을 말하지 않는 화면이다.
    """
    made: list[dict] = []
    단계들 = sorted(
        [s for s in cert.get("stages") or [] if not s["done"]],
        key=lambda s: (s["next"] is None, s["next"]["days"] if s["next"] else 0),
    )
    for stage in 단계들:
        남은것 = [row for row in stage["plan"] if row["left"]]
        if stage["next"] and not 남은것:
            # 할 일이 안 적힌 단계다. 일정이 곧 할 일이다.
            made.append({
                "kind": "exam", "title": stage["next"]["label"],
                "stage": stage["name"], "days": stage["next"]["days"],
                "note": stage["next"]["note"], "date": stage["next"]["date"],
                "url": link_for(cert, stage["name"]),
            })
            continue
        for row in 남은것:
            made.append({
                "kind": "item", "title": row["title"], "stage": stage["name"],
                "hash": row["hash"], "total": row["total"], "done": row["done"],
                "days": stage["next"]["days"] if stage["next"] else None,
            })
    # 단계가 안 적힌 자격증도 있다. 그때는 커리큘럼을 그대로 쓴다.
    if not 단계들:
        for row in cert.get("curriculum") or []:
            if row["left"]:
                made.append({
                    "kind": "item", "title": row["title"], "stage": row["stage"],
                    "hash": row["hash"], "total": row["total"], "done": row["done"],
                    "days": None,
                })
    return made[:TODAY_MAX]


def link_for(cert: dict, stage: str) -> str:
    """그 단계로 가는 공식 링크. **없으면 빈 문자열이다** — 아무 링크나
    붙이면 접수하러 눌렀다가 소개 페이지에 떨어진다.

    단계 이름이 링크 라벨에 들어 있는 것을 먼저 찾고(접수 → "접수하기"),
    없으면 공식 사이트로 보낸다.
    """
    for link in cert.get("links") or []:
        if stage and stage in link["label"]:
            return link["url"]
    return cert.get("site") or ""


def note_path(ctx, key: str):
    """자격증 노트 경로. 키가 이상하면 `None` 이다 —
    이 값이 그대로 파일 이름이 된다."""
    if not KEY.match(key or ""):
        return None
    return paths.cert_dir(ctx.settings.home) / f"{key}.md"


def add(ctx, key: str, name: str, site: str = "") -> bool:
    """자격증 하나를 늘린다. **있으면 덮지 않는다** — 이미 적어 둔 일정과
    커리큘럼을 빈 노트가 지우는 것이 이 기능의 유일한 사고다."""
    path = note_path(ctx, key)
    if path is None or not name.strip() or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    앞머리 = [f"name: {name.strip()}", f"status: {READY}"]
    if site.strip().startswith(("http://", "https://")):
        앞머리.append(f"site: {site.strip()}")
    path.write_text(
        "---\n" + "\n".join(앞머리) + "\n---\n\n"
        f"# {name.strip()}\n\n"
        "일정과 커리큘럼은 앞머리에 적는다 — `exams` · `curriculum`.\n"
        "**일정은 사람이 확인해 적는다.** 해마다 바뀌고, 틀리면 접수를 놓친다.\n",
        encoding="utf-8",
    )
    return True


def set_status(ctx, key: str, status: str) -> bool:
    """상태를 바꾼다. 내리는 것도 여기다 — **파일을 지우지 않는다.**
    지우면 적어 둔 일정과 커리큘럼이 같이 사라지고, 마음이 바뀌었을 때
    처음부터 다시 적어야 한다."""
    path = note_path(ctx, key)
    if path is None or not status.strip():
        return False
    if not path.is_file():
        # 코드 상수에만 있던 자격증이다. 노트를 만들어 상태를 담는다.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nstatus: {status.strip()}\n---\n", encoding="utf-8")
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, _ = parse_front_matter(text)
    lines = text.splitlines()
    if not meta:
        path.write_text(f"---\nstatus: {status.strip()}\n---\n\n{text}",
                        encoding="utf-8")
        return True
    for i, line in enumerate(lines):
        if line.startswith("status:"):
            lines[i] = f"status: {status.strip()}"
            break
    else:
        lines.insert(1, f"status: {status.strip()}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def note_keys(ctx) -> list[str]:
    """노트 파일로만 있는 자격증도 목록에 선다.
    화면에서 늘린 것은 코드 상수에 없다."""
    root = paths.cert_dir(ctx.settings.home)
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.glob("*.md") if KEY.match(p.stem))
