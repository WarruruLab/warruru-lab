"""자소서 소스 — 내가 한 활동 하나마다 한 장 (명세 §2.16, 2026-09-24 추가).

**회사마다 자소서를 새로 쓰지 않는다.** 회사는 늘어나는데 재료는 그대로다 —
카카오 테크 캠퍼스에서 겪은 일은 LG CNS 에 쓰든 현대오토에버에 쓰든 같은
사실이고, 달라지는 것은 어느 문장을 고르고 어떻게 잇느냐뿐이다.
그래서 **재료를 회사 노트에서 떼어 활동별로 모은다.**

노트는 `~/.warruru/career/activities/{활동}.md` 다 — 저장소 밖이다.

앞머리는 이렇다.

    name: 카카오 테크 캠퍼스 2기
    kind: 교육
    org: 카카오
    period: 2024-04-01..2024-11-30
    role: 백엔드 (5명 중 채팅 담당)
    keywords: 협업, Git 충돌, WebSocket, Thymeleaf
    slugs: net-socket, git-branch-strategy
    used: lg-cns
    sources:
      - 수치 | 팀 5명 중 채팅 기능을 둘이 나눠 맡았다
      - 행동 | 충돌이 날 때마다 원인을 함께 확인하고 작업 범위를 먼저 나눴다
      - 배움 | 협업은 구현보다 범위와 병합 절차를 먼저 맞추는 일이다

`sources:` 가 이 축의 알맹이다. **자소서에 그대로 옮길 수 있는 단위**로 적고,
유형(`수치`·`행동`·`상황`·`배움`·`협업`)으로 묶어 고르기 쉽게 한다.
"""

from __future__ import annotations

import re
from pathlib import Path

from warruru_local import paths
from warruru_local.publish import tistory_clipboard

# 파일 이름이 그대로 주소가 된다. 회사·자격증 노트와 같은 규칙을 쓴다.
KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# 소스 문장의 유형. **목록 밖은 '기타' 로 떨어뜨린다** — 유형이 늘어나면
# 화면에서 묶이지 않고, 묶이지 않으면 고를 때 다시 전부 읽어야 한다.
KINDS = ("상황", "행동", "수치", "배움", "협업", "기타")


def _fields(item, count: int) -> list[str]:
    from warruru_local.daemon.careerview import _fields as 쪼개기

    return 쪼개기(item, count)


def note_keys(ctx) -> list[str]:
    root = paths.activity_dir(ctx.settings.home)
    if not root.is_dir():
        return []
    return sorted(path.stem for path in root.glob("*.md") if KEY.match(path.stem))


def _one(ctx, key: str) -> dict | None:
    from warruru_local.daemon.careerview import parse_front_matter

    path = paths.activity_dir(ctx.settings.home) / f"{key}.md"
    if not KEY.match(key) or not path.is_file():
        return None
    meta, body = parse_front_matter(path.read_text(encoding="utf-8", errors="replace"))

    def 글(이름: str) -> str:
        값 = meta.get(이름)
        return 값.strip() if isinstance(값, str) else ""

    def 목록(이름: str) -> list[str]:
        값 = meta.get(이름)
        if isinstance(값, str):
            return [x.strip() for x in 값.split(",") if x.strip()]
        if isinstance(값, list):
            return [str(x).strip() for x in 값 if str(x).strip()]
        return []

    sources = []
    for item in meta.get("sources") or []:
        종류, 문장 = _fields(item, 2)
        if not 문장:
            continue
        sources.append({"kind": 종류 if 종류 in KINDS else "기타", "text": 문장})

    시작, 끝 = "", ""
    기간 = 글("period")
    if ".." in 기간:
        시작, 끝 = [x.strip() for x in 기간.split("..", 1)]
    else:
        시작 = 기간

    return {
        "key": key,
        "name": 글("name") or key,
        "kind": 글("kind"),
        "org": 글("org"),
        "role": 글("role"),
        "period": 기간,
        "start": 시작,
        "end": 끝,
        "award": 글("award"),
        "keywords": 목록("keywords"),
        "slugs": 목록("slugs"),
        "used": 목록("used"),
        "links": 목록("links"),
        "sources": sources,
        "counts": {종류: sum(1 for s in sources if s["kind"] == 종류)
                   for 종류 in KINDS},
        "html": tistory_clipboard.to_html(body) if body.strip() else "",
        "markdown": body,
    }


def build_activities(ctx) -> list[dict]:
    """활동 목록. **최근 것이 위다** — 자소서를 쓸 때 먼저 꺼내는 것이 최근 일이다."""
    made = [_one(ctx, key) for key in note_keys(ctx)]
    made = [row for row in made if row]
    made.sort(key=lambda row: (row["start"] or "0000", row["name"]), reverse=True)
    return made


def build_activity(ctx, key: str) -> dict | None:
    """활동 하나. **기록 축에서 면접 문장을 끌어온다**(2026-09-24).

    `slugs:` 에 적은 주제로 남긴 기록의 `interview` 가 여기 붙는다 —
    자소서를 쓰다 막히는 자리가 대개 "그래서 뭐라고 말할 건데" 이고,
    그 문장은 이미 기록에 있다. 없는 것을 지어내지 않고 있는 것을 잇는다.
    """
    row = _one(ctx, key)
    if row is None:
        return None
    문장, 기록수 = [], 0
    for slug in row["slugs"]:
        for rec in ctx.records.list_records(topic_slug=slug, limit=50):
            기록수 += 1
            말 = (rec.get("interview") or "").strip()
            if 말:
                문장.append({"slug": slug, "title": rec["title"], "text": 말,
                             "id": rec["record_id"]})
    row["records"] = 기록수
    # 같은 문장이 여러 번 나오면 한 번만 — 기록은 겹쳐 남는 일이 흔하다.
    본것, 고른것 = set(), []
    for 말 in 문장:
        if 말["text"] in 본것:
            continue
        본것.add(말["text"])
        고른것.append(말)
    row["interviews"] = 고른것
    return row
