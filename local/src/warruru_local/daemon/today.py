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


def day_summary(ctx, day: str) -> dict:
    """그날 무엇을 했나. **주제로 묶어 보여준다** — 건수 하나로는
    "그날 뭘 했더라" 에 답이 안 된다.

    홈이 날짜 축을 갖는 이유가 이것이다(2026-09-08). 어제 무엇을 했는지
    보려고 다른 화면을 찾아가야 하면, 매일 무엇을 했는지가 안 쌓인다.
    """
    from warruru_local import topics
    from warruru_local.clock import local_day_bounds

    start, end = local_day_bounds(day)
    rows = ctx.records.slug_summary(since=start, until=end)
    made = []
    for row in rows:
        slug = row["topic_slug"]
        # **한글 이름이 있으면 그것을 쓴다.** 없으면 사람이 적은 원문,
        # 그것도 슬러그와 같으면 슬러그 하나만 남긴다 — 같은 글자를 두 번
        # 그리면 줄이 길어지기만 하고 새로 아는 것이 없다.
        이름 = topics.label_of(slug)
        if 이름 == slug:
            이름 = row["topic"] or slug
        made.append({
            "slug": slug, "label": 이름,
            "same": 이름 == slug,
            "count": row["count"],
        })
    return {"topics": made, "count": sum(row["count"] for row in made)}


def day_records(ctx, day: str) -> dict:
    """그날 **와르르랩에 전달된 기록**을 제목으로 읽는다 (명세 §2.14).

    전에 이 자리는 슬러그와 숫자만 있었다 — `db-index 9건 개념1 실험6
    재료 4/4`. **205건이 다 제목을 갖고 있는데 화면에는 하나도 없었고**,
    `재료 3/4` 가 무슨 뜻인지는 어디에도 안 적혀 있었다.

    글로 만들 수 있는 주제도 같이 센다. 여기가 '오늘 뭘 했나' 에서
    '그래서 뭘 쓰나' 로 넘어가는 자리다.
    """
    from warruru_local import topics
    from warruru_local.clock import local_day_bounds

    KIND = {"CONCEPT": "개념", "EXPERIMENT": "실험",
            "TECH_CHOICE": "기술선택", "TROUBLESHOOTING": "트러블슈팅"}

    start, end = local_day_bounds(day)
    rows = ctx.records.list_records(since=start, until=end, limit=200)
    기록 = [{
        "id": row["record_id"],
        "title": row["title"],
        "slug": row["topic_slug"],
        "label": topics.label_of(row["topic_slug"]),
        "kind": KIND.get(row["kind"], row["kind"]),
        # **면접 문장이 비었는지 그 자리에서 보인다.** 205건 중 43건뿐이라,
        # 목록에서 안 드러나면 영영 안 채운다.
        "interview": bool((row["interview"] or "").strip()),
    } for row in rows]

    # 그날 만진 주제. 주제 하나가 글 하나가 된다.
    주제: dict[str, dict] = {}
    for row in 기록:
        칸 = 주제.setdefault(row["slug"], {
            "slug": row["slug"], "label": row["label"], "count": 0, "draft": None,
        })
        칸["count"] += 1
    for slug, 칸 in 주제.items():
        초안 = ctx.records.latest_draft_of(slug)
        if 초안:
            칸["draft"] = {
                "id": 초안["draft_id"],
                "published": bool(초안["published_url"]),
            }
    return {
        "records": 기록,
        "topics": sorted(주제.values(), key=lambda row: -row["count"]),
        "count": len(기록),
        "filled": sum(1 for row in 기록 if row["interview"]),
    }


def writable(ctx, limit: int = 6) -> list[dict]:
    """**글로 쓸 수 있는 주제.** 날짜와 무관하다.

    `/t` 를 그날로만 자르면 0건인 날에 화면이 통째로 빈다 — 홈이 `/d/{오늘}`
    로 보내던 때와 같은 실패다. 그날 것이 없어도 **쓸 수 있는 것은 있다.**

    재료 막대 넷은 `rationale`(왜 그렇게 판단했나) · `outcome`(그래서 어떻게
    됐나) · `limitation`(어디까지만 맞나) · `interview`(면접에서 어떻게
    말할까)다. 넷이 다 차야 6단 초안의 빈 절이 안 생긴다 — 전에는 화면에
    `재료 3/4` 라고만 적혀 있고 **그게 무슨 뜻인지 어디에도 없었다.**
    """
    from warruru_local import topics

    by_slug: dict[str, list[dict]] = {}
    for row in ctx.records.material_rows():
        by_slug.setdefault(row["topic_slug"], []).append(row)

    made = []
    for slug, rows in by_slug.items():
        재료 = topics.material_fill(rows)
        찬것 = sum(1 for item in 재료 if item["filled"])
        초안 = ctx.records.latest_draft_of(slug)
        made.append({
            "slug": slug, "label": topics.label_of(slug),
            "count": len(rows), "material": 재료, "ready": 찬것,
            "draft": 초안["draft_id"] if 초안 else None,
            "published": bool(초안 and 초안["published_url"]),
        })
    # **재료가 찬 것 먼저, 그다음 기록이 많은 것.** 아직 안 쓴 것이 위로 온다 —
    # 이미 발행한 주제를 먼저 보여줄 이유가 없다.
    made.sort(key=lambda row: (row["published"], -row["ready"], -row["count"]))
    return made[:limit]
