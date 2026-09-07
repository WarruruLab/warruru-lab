"""회사별 준비 노트 화면.

여기서 데몬이 하는 일은 `~/.warruru/career/*.md` 를 읽고 **숫자를 그 자리에서
세는 것**이다. 노션에는 닿지 않는다 — 공고를 읽고 요약하는 쪽은 사용자 앞의
에이전트이고, 데몬이 외부 네트워크나 모델에 의존하기 시작하면 비행기 안에서
이 화면이 무너진다.

**파일과 화면이 나눠 갖는 것이 다르다.** 파일에는 공고가 요구하는 것만 적힌다
— 공고 뜰 때 한 번 정해지고 잘 안 변한다. 내가 얼마나 갖췄는지는 매일 변하므로
파일에 적지 않고 열 때마다 DB 에서 센다. 파일에 숫자를 박아 두면 기록을 하나
남긴 다음에도 화면이 옛 숫자를 말한다 — 확인하러 여는 화면이 거짓말을 하면
확인용이 아니다.
"""

from __future__ import annotations

import re
from pathlib import Path

from warruru_local import paths, topics
from warruru_local.clock import local_date_of, to_iso
from warruru_local.publish import tistory_clipboard

# 파일 이름이 곧 URL 이다. **여기를 느슨하게 두면 경로 탈출이 된다** —
# `/career/..%2f..%2f.ssh%2fid_rsa` 같은 요청이 홈 디렉터리 밖을 읽는다.
# 화이트리스트로 받고, 그 뒤에 실제 경로가 career 디렉터리 안인지 한 번 더 본다.
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_FENCE = "---"
_SCALAR = re.compile(r"^([a-z_]+):\s*(.*)$")
_ITEM = re.compile(r"^\s+-\s+(.*)$")

# 목록 항목의 두 칸을 가르는 문자. `|` 는 YAML 평문 스칼라 안에서 특별하지
# 않아서, 이 앞머리는 그대로 YAML 로도 읽힌다. 나중에 파서를 바꿔도 파일은
# 그대로 쓸 수 있다는 뜻이다.
_SPLIT = "|"

# 게이트가 '충족' 이 아니면 전부 막힌 것으로 본다. **모르는 것은 갖춘 것이
# 아니다** — 삼성SDS 의 어학 자격처럼, 확인 안 한 전제조건 하나가 서류 자체를
# 막는다. 기술 준비가 아무리 되어 있어도 그 앞에서 끝난다.
_GATE_OK = "충족"

# 자격증 일정 중 **내가 지금 할 수 없는 것**. 앞 단계 합격자만 보는 실기,
# 이미 접수가 끝난 회차의 시험 같은 것이다.
_NOT_MINE = "해당없음"

# 자격증을 이미 딴 상태. 목록에서 조용해지고 D-day 를 세지 않는다.
_CERT_DONE = "합격"

# 링크는 `|safe` 로 그려지지 않지만 href 로는 들어간다. 노트를 쓰는 쪽이
# 에이전트라 `javascript:` 가 섞일 이유가 없어야 하는데, "없어야 한다" 를
# 검사 없이 믿지 않는다.
_SAFE_LINK = re.compile(r"^https?://", re.I)


def _root(ctx) -> Path:
    return paths.career_dir(ctx.settings.home)


def parse_front_matter(text: str) -> tuple[dict, str]:
    """앞머리와 본문을 가른다. 앞머리가 없으면 전부 본문이다.

    **완전한 YAML 파서가 아니다.** 스칼라와 한 겹 목록만 읽는다. 새 의존성을
    들이지 않기 위해서이고, 이 파일을 쓰는 쪽이 사람이 아니라 스킬을 따르는
    에이전트라 모양이 좁게 유지된다. 읽을 수 없는 줄은 조용히 버리지 않고
    그냥 무시하되, 본문은 언제나 온전히 남는다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _FENCE)
    except StopIteration:
        # 닫히지 않은 앞머리. 본문을 잃는 것보다 앞머리를 포기하는 편이 낫다.
        return {}, text

    meta: dict = {}
    key: str | None = None
    for line in lines[1:end]:
        item = _ITEM.match(line)
        if item and key:
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(_unquote(item.group(1)))
            continue
        scalar = _SCALAR.match(line)
        if scalar:
            key, value = scalar.group(1), _unquote(scalar.group(2))
            meta[key] = value if value else []
    return meta, "\n".join(lines[end + 1:])


def _unquote(value: str) -> str:
    """값 전체를 감싼 따옴표를 벗긴다.

    **옵시디언 때문이다**(2026-09-07). 프로퍼티 UI 로 한 번만 건드리면
    `deadline: 2026-10-02` 가 `deadline: "2026-10-02"` 로 저장되는데,
    그러면 날짜 정규식에 안 맞아 **D-day 가 조용히 사라진다.**
    화면이 아무 말도 없이 마감을 잊는 것이 이 파일에서 가장 나쁜 결말이다.

    한쪽만 있는 따옴표는 값의 일부로 본다 — 벗기면 없던 값이 만들어진다.
    """
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("\"", "'"):
        return text[1:-1].strip()
    return text


def _pair(item: str) -> tuple[str, str]:
    left, _, right = item.partition(_SPLIT)
    return left.strip(), right.strip()


def _fields(item: str, count: int) -> list[str]:
    parts = [part.strip() for part in item.split(_SPLIT)]
    return (parts + [""] * count)[:count]


def parse_links(items) -> list[dict]:
    """`라벨 | URL` 목록. **`http(s)` 가 아니면 걸지 않는다.**

    자격증 노트와 주제 노트가 같은 모양을 쓴다. 각자 파싱하면 한쪽만
    검사가 빠지고, 빠진 쪽은 아무도 눈치채지 못한다.
    """
    made = []
    for item in items or []:
        label, url = _pair(item)
        if url and _SAFE_LINK.match(url):
            made.append({"label": label or url, "url": url})
    return made


def _many(value) -> list[str]:
    """`a, b` 한 줄로 적든 목록으로 적든 같은 리스트가 나온다.

    쓰는 쪽이 매번 어느 모양인지 기억하게 만들면 그 자리가 비뚤어진다.
    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _title_of(meta: dict, body: str, slug: str) -> str:
    company = (meta.get("company") or "").strip() if isinstance(meta.get("company"), str) else ""
    if company:
        role = meta.get("role") if isinstance(meta.get("role"), str) else ""
        return f"{company} · {role}".strip(" ·") if role else company
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or slug
    return slug


def _counts(ctx) -> dict[str, int]:
    """슬러그별 기록 건수. **화면을 열 때마다 다시 센다.**"""
    return {row["topic_slug"]: row["count"] for row in ctx.records.slug_summary()}


def _coverage(meta: dict, counts: dict[str, int]) -> dict:
    """`required` 의 슬러그 중 기록이 하나라도 있는 것의 비율."""
    required = meta.get("required")
    groups, seen = [], []
    if isinstance(required, list):
        for item in required:
            keyword, joined = _pair(item)
            slugs = [s.strip() for s in joined.split(",") if s.strip()]
            groups.append({
                "keyword": keyword,
                "slugs": [
                    {"slug": s, "label": topics.label_of(s), "count": counts.get(s, 0)}
                    for s in slugs
                ],
                "total": len(slugs),
                "have": sum(counts.get(s, 0) for s in slugs),
            })
            seen += slugs
    total = len(seen)
    covered = sum(1 for s in seen if counts.get(s))
    return {
        "groups": groups,
        "slugs": seen,
        "total": total,
        "covered": covered,
        # 0/0 을 100% 로 만들지 않는다. 요구 기술을 아직 못 적은 것과
        # 다 갖춘 것은 완전히 다른 상태다.
        "percent": round(covered * 100 / total) if total else 0,
        "gaps": [
            {"slug": s, "label": topics.label_of(s)}
            for s in seen if not counts.get(s)
        ],
    }


def _gates(meta: dict) -> list[dict]:
    made = []
    for item in meta.get("gates") or []:
        text, label = _pair(item)
        made.append({"text": text, "label": label or "미확인", "ok": label == _GATE_OK})
    return made


def _deadline(meta: dict, today: str) -> dict | None:
    value = meta.get("deadline")
    if not isinstance(value, str) or not value.strip():
        return None
    date = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return None
    from datetime import date as _date

    left = (_date.fromisoformat(date) - _date.fromisoformat(today)).days
    return {"date": date, "days": left, "past": left < 0}


def _essays(ctx, meta: dict, counts: dict[str, int]) -> list[dict]:
    """자소서 문항과 **거기 붙일 기록**.

    이 화면이 답할 것 둘 중 하나가 "자소서를 어떻게 준비하나" 다(2026-09-01
    확정). 문항만 적어 두면 지원서 쓸 때 다시 기록을 뒤져야 한다 — 무엇을
    붙일지가 문항 옆에 있어야 한다.

    **붙일 기록이 없으면 없다고 말한다.** 비슷한 것으로 채우면 지원서에
    그대로 나가고, 면접에서 되물으면 답이 없다.
    """
    made = []
    for item in meta.get("essays") or []:
        question, limit, joined = _fields(item, 3)
        if not question:
            continue
        slugs = [s.strip() for s in joined.split(",") if s.strip()]
        rows = []
        for slug in slugs:
            for row in ctx.records.list_records(topic_slug=slug, limit=20):
                rows.append({
                    "slug": slug,
                    "label": topics.label_of(slug),
                    "title": row["title"],
                    "interview": (row.get("interview") or "").strip(),
                    "record_id": row["record_id"],
                })
        made.append({
            "question": question,
            "limit": limit,
            "slugs": [{"slug": s, "label": topics.label_of(s), "count": counts.get(s, 0)}
                      for s in slugs],
            "records": rows,
        })
    return made


def _says(ctx, slugs: list[str], counts: dict[str, int]) -> list[dict]:
    """이 회사 키워드에 붙일 수 있는 면접 문장. 기록이 있는 슬러그만 훑는다."""
    made = []
    for slug in [s for s in slugs if counts.get(s)]:
        for row in ctx.records.list_records(topic_slug=slug, limit=20):
            if (row.get("interview") or "").strip():
                made.append({
                    "slug": slug,
                    "title": row["title"],
                    "interview": row["interview"].strip(),
                    "record_id": row["record_id"],
                })
    return made


def _read(ctx, path: Path, slug: str) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_front_matter(text)
    counts = _counts(ctx)
    coverage = _coverage(meta, counts)
    today = local_date_of(to_iso(ctx.clock.now()))
    gates = _gates(meta)
    return {
        "slug": slug,
        "name": path.name,
        "title": _title_of(meta, body, slug),
        "company": meta.get("company") or slug,
        "role": meta.get("role") or "",
        "confidence": meta.get("confidence") or "",
        "source": meta.get("source") or "",
        "posting": meta.get("posting") or "",
        # 인재상·평가 항목. **요구 기술과 나란히 둔다** — 기술만 맞추고
        # 이쪽을 모르면 자소서와 면접에서 그대로 드러난다.
        #
        # 키 이름이 `values` 면 Jinja 가 dict 의 메서드를 먼저 집는다.
        # 앞머리 쪽 이름은 `values` 로 두되 화면에 넘길 때 바꾼다.
        "traits": _many(meta.get("values")),
        "gates": gates,
        "blocked": [gate for gate in gates if not gate["ok"]],
        "deadline": _deadline(meta, today),
        "coverage": coverage,
        "unmapped": _many(meta.get("unmapped")),
        "says": _says(ctx, coverage["slugs"], counts),
        "essays": _essays(ctx, meta, counts),
        "markdown": text,
        "html": tistory_clipboard.to_html(body),
    }


def demand(companies: list[dict]) -> dict[str, list[str]]:
    """슬러그마다 **어느 회사가 요구하는가.** 회사 노트를 거꾸로 모은 것이다.

    공부 순서를 정하는 값이다 — 두 회사가 함께 요구하는 슬러그 하나를 채우면
    두 화면의 막대가 같이 오른다.
    """
    made: dict[str, list[str]] = {}
    for row in companies:
        name = row.get("company") or row.get("title")
        for slug in (row.get("coverage") or {}).get("slugs", []):
            names = made.setdefault(slug, [])
            if name not in names:
                names.append(name)
    return made


def _group_rows(source, counts, wanted, *, ordered: bool = False) -> list[dict]:
    """`ordered` 면 로드맵 순서로 세운다 — 묶음도, 묶음 안 슬러그도.

    로드맵 화면이 답할 것은 "어디까지 왔는가" 라(2026-09-01 확정) 순서가
    보여야 한다. 공고에 나오는 말로 묶은 순서로는 다음에 뭘 할지가 안 나온다.
    """
    groups = []
    for key, label, slugs in source:
        if ordered:
            slugs = tuple(sorted(slugs, key=topics.roadmap_index))
        # 키 이름이 `items` 면 Jinja 가 dict 의 메서드를 먼저 집는다.
        rows = [
            {
                "slug": slug,
                "label": topics.label_of(slug),
                "count": counts.get(slug, 0),
                "companies": wanted.get(slug, []),
            }
            for slug in slugs
        ]
        groups.append({
            "key": key,
            "label": label,
            "order": min((topics.roadmap_index(row["slug"]) for row in rows), default=0),
            "slugs": rows,
            "have": sum(1 for item in rows if item["count"]),
            "total": len(rows),
        })
    return sorted(groups, key=lambda g: g["order"]) if ordered else groups


def _tally(groups: list[dict]) -> dict:
    every = [item for group in groups for item in group["slugs"]]
    covered = sum(1 for item in every if item["count"])
    return {
        "total": len(every),
        "covered": covered,
        "percent": round(covered * 100 / len(every)) if every else 0,
    }


def _book_notes(ctx, today: str) -> dict[str, dict]:
    """책마다의 내 사정. **없는 책이 대부분이고, 없어도 화면은 뜬다.**

    앞머리는 셋뿐이다 — `state`(빌림/소장/전자책/문서) · `due`(반납일) ·
    `at`(어디까지). 반납일이 지난 것을 지우지 않는다. 연장했는지 반납했는지는
    사람만 알고, 화면이 임의로 지우면 그 사실이 조용히 사라진다.
    """
    root = paths.book_note_dir(ctx.settings.home)
    if not root.is_dir():
        return {}
    made: dict[str, dict] = {}
    for path in root.glob("*.md"):
        if not SLUG.match(path.stem):
            continue
        meta, body = parse_front_matter(
            path.read_text(encoding="utf-8", errors="replace")
        )
        due = (meta.get("due") or "").strip() if isinstance(meta.get("due"), str) else ""
        left = None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", due):
            left = _days(due) - _days(today)
        else:
            due = ""
        made[path.stem] = {
            "state": (meta.get("state") or "").strip() if isinstance(meta.get("state"), str) else "",
            "due": due,
            "days": left,
            "at": (meta.get("at") or "").strip() if isinstance(meta.get("at"), str) else "",
            "note": tistory_clipboard.to_html(body) if body.strip() else "",
        }
    return made


# 책이 가질 수 있는 상태. **'안 정한 것' 은 상태가 아니라 상태가 없는 것**이라
# 여기 없다 — 목록에서 마지막 칸으로 모인다.
BOOK_STATES = ("읽는 중", "다음에", "중단", "다 읽음")


def set_book_state(ctx, key: str, state: str) -> None:
    """앞머리의 `state` 만 고친다. 본문과 나머지 필드는 그대로 둔다 —
    사람이 손으로 적어 둔 것을 화면이 지우면 안 된다."""
    path = paths.book_note_dir(ctx.settings.home) / f"{key}.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    meta, body = parse_front_matter(text)
    meta["state"] = state
    줄 = []
    for name, value in meta.items():
        if isinstance(value, list):
            줄.append(f"{name}:")
            줄 += [f"  - {item}" for item in value]
        else:
            줄.append(f"{name}: {value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(줄) + "\n---\n" + (body or "\n"),
                    encoding="utf-8")


def build_books(ctx) -> dict:
    """책 목록. 상태로 갈라 놓고, '다음에' 는 **공고가 요구하는 주제를 많이
    덮는 순**으로 세운다(명세 §2.9 f).

    27권을 한 줄로 세우면 무엇부터 볼지 여전히 모른다. 순서가 곧 답이다.
    """
    from warruru_local.daemon import reading

    stack = build_stack(ctx)
    wanted = demand(list_companies(ctx))
    certs = {key: set(slugs) for key, _, slugs in topics.CERTIFICATIONS}

    made = []
    for book in stack["books"]:
        slugs = next((s for k, _, s in topics.BOOK_GROUPS if k == book["key"]), ())
        공고 = {c for slug in slugs for c in wanted.get(slug, [])}
        자격증 = [name for key, name, cs in topics.CERTIFICATIONS
                  if set(slugs) & set(cs)]
        made.append({
            **book,
            "companies": sorted(공고),
            "certs": 자격증[:2],
            "progress": reading.covered(ctx, book["key"]),
            "note_days": len(reading.days_of(ctx, book["key"])),
        })

    def 급한순(row):
        return (row["days"] if row["days"] is not None else 9999, row["label"])

    def 요구순(row):
        return (-len(row["companies"]), -len(row["certs"]), row["label"])

    통 = {"읽는 중": [], "다음에": [], "중단": [], "다 읽음": [], "안 정한 것": []}
    for row in made:
        통[row["state"] if row["state"] in BOOK_STATES else "안 정한 것"].append(row)
    통["읽는 중"].sort(key=급한순)
    통["다음에"].sort(key=요구순)
    통["안 정한 것"].sort(key=요구순)
    return {"groups": 통, "states": BOOK_STATES}


def deadlines(ctx) -> list[dict]:
    """자격증과 공고의 마감을 **한 줄로 섞어** 가까운 순으로 세운다.

    지금까지 둘을 따로 놓았는데(2026-09-07 이전), 사람이 아침에 묻는 것은
    "자격증이 언제인가" 도 "공고가 언제인가" 도 아니라 **"다음에 뭐가 닥치나"**
    하나다. 두 목록을 번갈아 보며 머릿속에서 합치게 두면 그게 곧 놓치는 자리다.

    지난 것과 내가 못 하는 것(`해당없음`)은 빼고, 준비도를 함께 들고 온다 —
    D-day 옆에 준비도가 없으면 급한지 아닌지를 판단할 수 없다.
    """
    made: list[dict] = []

    for cert in build_certs(ctx):
        if cert["done"] or not cert["next"]:
            continue
        made.append({
            "kind": "자격증",
            "name": cert["name"],
            "url": f"/career/cert/{cert['key']}",
            "label": cert["next"]["label"],
            "date": cert["next"]["date"],
            "days": cert["next"]["days"],
            "have": cert["coverage"]["covered"],
            "total": cert["coverage"]["total"],
            "blocked": 0,
        })

    for row in list_companies(ctx):
        due = row.get("deadline")
        if not row.get("slug") or not due or due["past"]:
            continue
        made.append({
            "kind": "공고",
            "name": row["company"] or row["title"],
            "url": f"/career/c/{row['slug']}",
            "label": "지원 마감",
            "date": due["date"],
            "days": due["days"],
            "have": row["coverage"]["covered"],
            "total": row["coverage"]["total"],
            "blocked": len(row.get("blocked") or []),
        })

    return sorted(made, key=lambda item: (item["days"], item["name"]))


def build_stack(ctx) -> dict:
    """기술스택 화면.

    **두 축을 섞지 않는다.** 로드맵 100개는 *직접 만들어 보는 것* 이고
    CS 49개는 *면접에서 묻는 것* 이라, 한 막대로 합치면 어느 쪽이 비었는지
    알 수 없다.
    """
    counts = _counts(ctx)
    wanted = demand(list_companies(ctx))
    groups = _group_rows(topics.SLUG_GROUPS, counts, wanted, ordered=True)
    cs_groups = _group_rows(topics.CS_GROUPS, counts, wanted)
    ai_groups = _group_rows(topics.AI_GROUPS, counts, wanted)
    books = _group_rows(topics.BOOK_GROUPS, counts, wanted)
    notes = _book_notes(ctx, local_date_of(to_iso(ctx.clock.now())))
    for book in books:
        # 노트가 없는 책이 대부분이다. **빈 값을 먼저 채운다** — 템플릿에서
        # `book.days` 가 Undefined 면 비교하는 순간 화면이 통째로 500 이 된다.
        book.update({"state": "", "due": "", "days": None, "at": "", "note": ""})
        book.update(notes.get(book["key"], {}))
    # **반납일이 있는 것이 맨 위다.** 빌린 책은 기한이 지나면 그냥 사라지고,
    # 소장한 책은 언제든 다시 펴면 된다. 둘을 같은 순서로 두면 그 차이가
    # 화면에서 없어진다.
    books.sort(key=lambda b: (b.get("days") is None, b.get("days", 0), b["label"]))

    every = [item for group in groups for item in group["slugs"]]
    # 먼저 할 것 — **요구하는 회사가 많은데 기록이 0건인 것.** 하나를 채우면
    # 여러 회사의 막대가 같이 오르므로, 같은 노력으로 가장 많이 움직인다.
    first = sorted(
        [item for item in every if not item["count"] and item["companies"]],
        key=lambda item: (-len(item["companies"]), item["slug"]),
    )
    known = ({item["slug"] for item in every}
             | set(topics.CS_SLUGS) | set(topics.AI_SLUGS))
    # **다음에 할 것.** 로드맵 순서에서 아직 0건인 첫 주제들이다.
    # "먼저 할 것"(회사가 많이 요구하는 것)과 다른 값이다 — 이쪽은 순서를,
    # 저쪽은 겹침을 본다.
    ahead = [item for item in sorted(every, key=lambda i: topics.roadmap_index(i["slug"]))
             if not item["count"]][:5]

    return {
        "groups": groups,
        "cs_groups": cs_groups,
        "ai_groups": ai_groups,
        "books": books,
        "first": first,
        "ahead": ahead,
        "coverage": _tally(groups),
        "cs_coverage": _tally(cs_groups),
        "ai_coverage": _tally(ai_groups),
        # 어느 목록에도 없는 주제. 기록은 있는데 갈 곳이 없는 것들이다.
        "outside": sorted(slug for slug in counts if slug not in known),
    }


def _cert_note(ctx, key: str, today: str) -> dict:
    """자격증 노트 파일. **없어도 화면은 뜬다.**

    시험 일정은 사람이 확인해 적는 값이라 코드 상수로 둘 수 없다 —
    해마다 바뀌고, 틀리면 접수를 놓친다.
    """
    path = paths.cert_dir(ctx.settings.home) / f"{key}.md"
    if not path.is_file():
        return {
            "exams": [], "links": [], "stages": [], "curriculum": [],
            "next": None, "status": "미시작",
            "done": False, "html": "", "markdown": "", "meta": {},
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_front_matter(text)
    exams = []
    for item in meta.get("exams") or []:
        date, label, note, mine, stage = _fields(item, 5)
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            continue
        exams.append({
            "date": date, "label": label, "note": note,
            # 넷째 칸이 `해당없음` 이면 내가 못 하는 일정이다. 앞 단계에
            # 합격해야 볼 수 있는 실기 같은 것. 목록에는 남기되 D-day 로는
            # 안 쓴다 — 못 하는 일을 카운트다운하면 그 숫자가 거짓말이다.
            "mine": mine != _NOT_MINE,
            "stage": stage,
            "past": date < today,
            "days": (_days(date) - _days(today)),
        })
    exams.sort(key=lambda row: row["date"])

    links = parse_links(meta.get("links"))

    # 커리큘럼. **하루 분량을 계산하는 것이 목적이다** — "3주 남았네" 가
    # "오늘 반 회분" 이 되어야 오늘 손이 움직인다.
    from warruru_local.daemon.topicview import ask_hash

    progress = ctx.records.cert_progress(key)
    curriculum = []
    for item in meta.get("curriculum") or []:
        stage, title, amount = _fields(item, 3)
        if not title:
            continue
        try:
            total = int(amount)
        except ValueError:
            total = 0
        done = progress.get(ask_hash(title), 0)
        curriculum.append({
            "stage": stage, "title": title, "hash": ask_hash(title),
            "total": total, "done": done, "left": max(0, total - done),
            "percent": round(done * 100 / total) if total else 0,
        })

    # 단계(필기·실기 · 1차·2차). **이 화면의 주인공이다** — 자격증은 슬러그
    # 목록이 아니라 시험이고, 시험은 단계마다 유형도 공부법도 다르다.
    stages = []
    for item in meta.get("stages") or []:
        name, state = _fields(item, 2)
        if name:
            stages.append({"name": name, "state": state or "미시작",
                           "done": state == _CERT_DONE})
    for stage in stages:
        # 키 이름이 `items` 면 Jinja 가 dict 의 메서드를 먼저 집는다(두 번째다).
        stage["plan"] = [row for row in curriculum if row["stage"] == stage["name"]]
        stage["next"] = next(
            (row for row in exams
             if not row["past"] and row["mine"] and row["stage"] == stage["name"]),
            None,
        )
        # **항목마다 따로 센다.** 회차와 문항과 회독은 단위가 달라서, 더하면
        # "오늘 2.2만큼" 처럼 아무 뜻도 없는 숫자가 나온다.
        days = max(1, stage["next"]["days"]) if stage["next"] else 0
        for row in stage["plan"]:
            # 남은 날을 모르면(일정 미정) 하루 분량을 말하지 않는다.
            # 모르는 것을 그럴듯한 숫자로 채우면 그 숫자를 믿게 된다.
            row["per_day"] = round(row["left"] / days, 1) if days and row["left"] else 0
        stage["left_items"] = sum(1 for row in stage["plan"] if row["left"])

    return {
        "meta": meta,
        "status": meta.get("status") or "미시작",
        "done": (meta.get("status") or "") == _CERT_DONE,
        "issuer": meta.get("issuer") or "",
        # 목표. **점수제 시험에만 뜻이 있다** — 합격/불합격이면 목표는
        # 하나뿐이라 적을 것이 없고, TOPCIT 처럼 점수가 나오는 시험은
        # 목표를 안 정하면 무엇을 버릴지 못 고른다.
        "goal": meta.get("goal") or "",
        "site": meta.get("site") or "",
        "checked": meta.get("checked") or "",
        "exams": exams,
        "links": links,
        "stages": stages,
        "curriculum": curriculum,
        # 다음에 실제로 할 수 있는 것. 지난 회차는 지나간 대로 남겨 둔다 —
        # 지워 버리면 "이번에 놓쳤다" 는 사실까지 사라진다.
        "next": next(
            (row for row in exams if not row["past"] and row["mine"]), None
        ),
        "markdown": text,
        "html": tistory_clipboard.to_html(body),
    }


def _days(date: str) -> int:
    from datetime import date as _date

    return _date.fromisoformat(date).toordinal()


def build_certs(ctx) -> list[dict]:
    """자격증마다 로드맵과 겹치는 부분의 준비도.

    **시험 범위가 아니다.** 여기가 다 차도 합격을 뜻하지 않는다 —
    시험에는 나오지만 로드맵에 없는 것이 있다.
    """
    counts = _counts(ctx)
    today = local_date_of(to_iso(ctx.clock.now()))
    made = []
    for key, name, slugs in topics.CERTIFICATIONS:
        rows = [
            {"slug": slug, "label": topics.label_of(slug), "count": counts.get(slug, 0)}
            for slug in slugs
        ]
        covered = sum(1 for row in rows if row["count"])
        note = _cert_note(ctx, key, today)
        made.append({
            "key": key,
            "name": name,
            "slugs": rows,
            "coverage": {
                "total": len(rows),
                "covered": covered,
                "percent": round(covered * 100 / len(rows)) if rows else 0,
            },
            **note,
        })
    # **접수일이 가까운 순.** 이 화면이 먼저 답해야 하는 것은 "언제 접수하나"
    # 다 — 정처기 실기는 사흘, 네트워크관리사는 나흘뿐이고 놓치면 몇 달이
    # 밀린다. 딴 것과 일정을 모르는 것은 뒤로 보낸다.
    return sorted(
        made,
        key=lambda cert: (
            cert["done"],
            cert["next"] is None,
            cert["next"]["days"] if cert["next"] else 0,
        ),
    )


def build_cert(ctx, key: str) -> dict | None:
    for cert in build_certs(ctx):
        if cert["key"] == key:
            wanted = demand(list_companies(ctx))
            for row in cert["slugs"]:
                row["companies"] = wanted.get(row["slug"], [])
            return cert
    return None


def build_group(ctx, key: str) -> dict | None:
    """묶음 하나. **면접 문서다** — 이 묶음에서 뭘 묻는지가 주인공이고
    기록 건수는 아래에 작게 남는다(2026-09-01 확정).
    """
    from warruru_local.daemon import topicview

    stack = build_stack(ctx)
    every = (stack["groups"] + stack["cs_groups"]
             + stack["ai_groups"] + stack["books"])
    for group in every:
        if group["key"] != key:
            continue
        group["axis"] = (
            "roadmap" if group in stack["groups"]
            else "book" if group in stack["books"]
            else "ai" if group in stack["ai_groups"]
            else "cs"
        )
        checked = ctx.records.checked_asks()
        for row in group["slugs"]:
            note = topicview.topic_note(ctx, row["slug"])
            row["asks"] = [
                dict(ask, checked=ask["hash"] in checked) for ask in note["asks"]
            ]
            row["refs"] = note["refs"]
            row["asked"] = sum(1 for ask in row["asks"] if ask["checked"])
        group["asks_total"] = sum(len(row["asks"]) for row in group["slugs"])
        group["asked_total"] = sum(row["asked"] for row in group["slugs"])
        group["intro"] = _group_intro(ctx, key)
        # **책과 묶음도 대화 상대다.** 공부는 주제 하나가 아니라 "이 책을
        # 읽는 중" 으로 흐를 때가 많아서, 그 자리에 물을 칸이 없으면
        # 터미널로 나가야 한다. 키가 겹치지 않게 접두사를 붙인다.
        group["ask_key"] = f"{group['axis']}-{key}"
        group["thread"] = ctx.records.ask_thread(group["ask_key"])
        group["answers"] = topicview.answers(ctx, group["ask_key"])
        # **주제를 자동으로 정하지 않는다**(2026-09-08 확정). 책 하나가
        # 주제 열한 개를 덮는데 임의로 고르면 틀린 자리에 쌓이고,
        # 틀린 자리에 쌓인 기록은 아무 화면에서도 안 보인다.
        group["ask_slugs"] = [{"slug": row["slug"], "label": row["label"]}
                              for row in group["slugs"]]
        return group
    return None


def _group_intro(ctx, key: str) -> str:
    """묶음 머리말. 없으면 빈 문자열이다 — 있으면 좋은 것이지 관문이 아니다."""
    path = paths.group_note_dir(ctx.settings.home) / f"{key}.md"
    if not path.is_file():
        return ""
    _, body = parse_front_matter(path.read_text(encoding="utf-8", errors="replace"))
    return tistory_clipboard.to_html(body)


def list_companies(ctx) -> list[dict]:
    root = _root(ctx)
    if not root.is_dir():
        return []
    made = []
    for path in sorted(root.glob("*.md")):
        if not SLUG.match(path.stem):
            # 사람이 손으로 넣은 파일도 목록에는 보이게 하되 링크는 걸지 않는다.
            made.append({"slug": None, "name": path.name, "title": path.stem})
            continue
        made.append(_read(ctx, path, path.stem))
    return sorted(made, key=lambda row: row["title"])


def build_company(ctx, slug: str) -> dict | None:
    if not SLUG.match(slug):
        return None
    root = _root(ctx)
    path = root / f"{slug}.md"
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        # 심볼릭 링크로 밖을 가리키는 경우까지 여기서 걸린다.
        return None
    if not resolved.is_file():
        return None
    return _read(ctx, resolved, slug)
