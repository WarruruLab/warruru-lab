"""홈 — **오늘 뭐 하지**에 답한다 (명세 §2.13).

`/` 가 `/d/{오늘}` 로 보내고 있었다. 아침에 열면 그날 남긴 것이 없으니
화면이 통째로 빈다 — "이 날짜에는 기록이 없습니다" 한 줄이 전부였다.
**할 일이 하나도 안 보이니 닫고 나간다.** 손이 가는 기능이 전부 0건이었던
것과 같은 이야기다(2026-09-08 점검).

축마다 '오늘'을 이미 만들어 뒀는데(CS 5개 · 자격증 3개 · 책 · 스택)
**그것을 모으는 자리가 없어서** 네 화면을 따로 찾아가야 했다. 여기가 그 자리다.

규칙 셋.

1. **축마다 하나씩.** 한 축이 화면을 독점하면 다시 목록이 된다.
2. **최대 여섯.** 다 해도 하루치여야 누른다.
3. **마감은 위에 따로 선다.** 공부거리와 같은 줄에 두면 D-0 이 묻힌다.
"""

from __future__ import annotations

# 축마다 하나씩. 이 수를 늘리면 한 축이 화면을 독점하기 시작한다.
PER_AXIS = 1

# 다 해도 하루치여야 누른다.
MAX_ITEMS = 6

# 마감은 이만큼까지만 위에 세운다. 전부 세우면 그것도 목록이다.
MAX_DUE = 2


def _cs(ctx, today: str) -> list[dict]:
    """CS — 오늘 볼 질문 하나. **공고가 많이 찾는 과목**에서 뽑는다."""
    from warruru_local import topics
    from warruru_local.daemon import careerview, checking

    wanted = careerview.demand(careerview.list_companies(ctx))
    후보 = []
    for key, label, slugs in topics.CS_GROUPS:
        공고수 = len({c for slug in slugs for c in wanted.get(slug, [])})
        for pick in checking.picks(ctx, key, today, limit=1):
            후보.append((공고수, {
                "kind": "cs", "axis": "CS",
                "title": pick["text"], "where": pick["label"],
                "url": f"/career/stack/{key}",
                "slug": pick["slug"], "hash": pick["hash"],
                "note": "" if not pick.get("stale") else "3개월 지남",
            }))
            break
    후보.sort(key=lambda row: -row[0])
    return [row[1] for row in 후보[:PER_AXIS]]


def _cert(ctx, today: str, 이미: set[str]) -> list[dict]:
    """자격증 — 마감이 가장 가까운 것의 오늘 한 줄.

    **위 마감 줄에 이미 선 것은 건너뛴다.** 접수 마감은 마감이기도 하고
    오늘 할 일이기도 해서, 그냥 두면 같은 줄이 화면에 두 번 뜬다.
    """
    from warruru_local.daemon import careerview

    made = []
    for cert in careerview.build_certs(ctx):
        if cert["held"] or cert["dropped"] or cert["done"]:
            continue
        for row in cert["today"]:
            if row["kind"] == "exam" and row["title"] in 이미:
                continue
            made.append({
                "kind": "cert" if row["kind"] == "item" else "due",
                "axis": "자격증",
                "title": row["title"], "where": cert["name"],
                "url": f"/career/cert/{cert['key']}",
                "days": row.get("days"),
                "note": row.get("note", ""),
                "link": row.get("url", ""),
            })
            break
        if made:
            break
    return made[:PER_AXIS]


def _book(ctx) -> list[dict]:
    """책 — 읽는 중인 것 중 **반납이 가까운 것**. 빌린 책은 시간이 정해져 있다."""
    from warruru_local.daemon import careerview

    읽는중 = [b for b in careerview.build_stack(ctx)["books"]
              if b.get("days") is not None]
    읽는중.sort(key=lambda b: b["days"])
    return [{
        "kind": "book", "axis": "책",
        "title": f"{b['label']} 읽기", "where": "오늘 읽기",
        "url": f"/career/book/{b['key']}/today",
        "days": b["days"],
        "note": f"덮는 주제 {b['have']}/{b['total']}",
    } for b in 읽는중[:PER_AXIS]]


def _stack(ctx) -> list[dict]:
    """스택 — **공고가 많이 찾는데 안 쓴 것**. 재료가 많은 절이 먼저다."""
    from warruru_local.daemon import stacking

    for row in stacking.build_index(ctx):
        if row["written"] >= row["total"]:
            continue
        view = stacking.build(ctx, row["key"])
        빈절 = next((s for s in view["toc"] if not s["written"]), None)
        if 빈절 is None:
            continue
        return [{
            "kind": "stack", "axis": "기술스택",
            "title": f"{row['name']} 정리 — {빈절['label']}",
            "where": row["name"],
            "url": f"/career/s/{row['key']}#s-{빈절['slug']}",
            "note": f"기록 {빈절['records']}건" if 빈절["records"] else "",
        }]
    return []


def build(ctx, today: str) -> dict:
    """홈이 받는 것. **어느 축이 비어도 화면은 뜬다** — 빈 것이 고장이 아니다."""
    from warruru_local.daemon import careerview

    급한것 = [row for row in careerview.deadlines(ctx) if row["days"] >= 0]
    선것 = {row["label"] for row in 급한것[:MAX_DUE]}
    할것: list[dict] = []
    for 뽑기 in (lambda: _cs(ctx, today), lambda: _cert(ctx, today, 선것),
                lambda: _book(ctx), lambda: _stack(ctx)):
        try:
            할것 += 뽑기()
        except Exception:      # noqa: BLE001
            # **한 축이 비어도 홈은 뜬다.** 홈이 안 뜨면 다른 모든 화면으로
            # 가는 길이 같이 막힌다 — 그것이 여기서 가장 나쁜 결말이다.
            continue
    # **키를 `items` 로 두지 마라.** Jinja 가 dict 의 메서드를 먼저 집어서
    # `view.items` 가 목록이 아니라 함수가 된다. 자격증 단계에서 이미 한 번
    # 밟은 자리다(`stage["plan"]`).
    return {
        "due": 급한것[:MAX_DUE],
        "todo": 할것[:MAX_ITEMS],
        "more_due": max(0, len(급한것) - MAX_DUE),
    }
