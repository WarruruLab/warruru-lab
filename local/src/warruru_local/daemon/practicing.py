"""연습장에 그린 다이어그램 (명세 §2.11 h, 2026-09-22 추가).

TOPCIT 수행형은 **배점의 49%(490점)** 이고 답안을 UML·ERD 도구로 그린다.
공식 연습 도구는 시험장의 조작을 익히는 자리이고, 여기는 **무엇을 그릴지**를
익히는 자리다 — 시나리오를 읽고 클래스와 관계를 세우는 힘은 도구가 바뀌어도
그대로 옮겨 간다.

**그림은 저장소 밖에 산다**(`~/.warruru/career/practice/{자격증}/`). 초안과
노트가 그런 것과 같은 이유다 — origin 이 public 이다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from warruru_local import paths

# 파일 이름이 되는 값이다. 한글을 허용하되 경로가 될 수 있는 것은 다 막는다.
NAME = re.compile(r"^[가-힣A-Za-z0-9 _-]{1,40}$")

# 한 장에 담기는 상한. 브라우저가 보낸 것을 그대로 믿지 않는다.
MAX_NODES = 60
MAX_EDGES = 120
MAX_TEXT = 400


def _root(home: Path, cert_key: str) -> Path:
    return paths.practice_dir(home) / cert_key


def path_of(home: Path, cert_key: str, name: str) -> Path | None:
    if not NAME.match(name or ""):
        return None
    return _root(home, cert_key) / f"{name}.json"


def clean(payload: dict) -> dict:
    """화면이 보낸 그림을 **우리가 아는 모양으로만** 받는다.

    모르는 키는 버린다. 좌표는 숫자로 눌러 담고, 글자는 잘라 담는다 —
    크기 제한이 없으면 한 장이 디스크를 다 먹는다.
    """
    def 글자(value) -> str:
        return str(value or "")[:MAX_TEXT]

    def 수(value) -> float:
        try:
            return round(float(value), 1)
        except (TypeError, ValueError):
            return 0.0

    nodes = []
    for row in (payload.get("nodes") or [])[:MAX_NODES]:
        if not isinstance(row, dict):
            continue
        nodes.append({
            "id": 글자(row.get("id"))[:40],
            "title": 글자(row.get("title")),
            "body": 글자(row.get("body")),
            "x": 수(row.get("x")), "y": 수(row.get("y")),
        })
    ids = {row["id"] for row in nodes}
    edges = []
    for row in (payload.get("edges") or [])[:MAX_EDGES]:
        if not isinstance(row, dict):
            continue
        시작, 끝 = 글자(row.get("from"))[:40], 글자(row.get("to"))[:40]
        # 없는 상자를 가리키는 선은 버린다 — 열 때 허공에 선이 그려진다.
        if 시작 in ids and 끝 in ids:
            edges.append({"from": 시작, "to": 끝, "label": 글자(row.get("label"))[:60]})
    return {"kind": 글자(payload.get("kind"))[:20] or "class",
            "nodes": nodes, "edges": edges}


def save(home: Path, cert_key: str, name: str, payload: dict, now_iso: str) -> bool:
    path = path_of(home, cert_key, name)
    if path is None:
        return False
    그림 = clean(payload)
    그림["name"] = name
    그림["saved_at"] = now_iso
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(그림, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def read(home: Path, cert_key: str, name: str) -> dict | None:
    path = path_of(home, cert_key, name)
    if path is None or not path.is_file():
        return None
    try:
        그림 = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    return 그림 if isinstance(그림, dict) else None


def listing(home: Path, cert_key: str) -> list[dict]:
    """그린 것들. 최근에 저장한 것이 먼저다."""
    root = _root(home, cert_key)
    if not root.is_dir():
        return []
    made = []
    for path in root.glob("*.json"):
        그림 = read(home, cert_key, path.stem) or {}
        made.append({
            "name": path.stem,
            "kind": 그림.get("kind") or "class",
            "nodes": len(그림.get("nodes") or []),
            "saved_at": 그림.get("saved_at") or "",
        })
    return sorted(made, key=lambda row: row["saved_at"], reverse=True)
