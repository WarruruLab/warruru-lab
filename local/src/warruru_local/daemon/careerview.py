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
                meta[key].append(item.group(1).strip())
            continue
        scalar = _SCALAR.match(line)
        if scalar:
            key, value = scalar.group(1), scalar.group(2).strip()
            meta[key] = value if value else []
    return meta, "\n".join(lines[end + 1:])


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
        "gates": gates,
        "blocked": [gate for gate in gates if not gate["ok"]],
        "deadline": _deadline(meta, today),
        "coverage": coverage,
        "unmapped": _many(meta.get("unmapped")),
        "says": _says(ctx, coverage["slugs"], counts),
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


def _group_rows(source, counts, wanted) -> list[dict]:
    groups = []
    for key, label, slugs in source:
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
            "slugs": rows,
            "have": sum(1 for item in rows if item["count"]),
            "total": len(rows),
        })
    return groups


def _tally(groups: list[dict]) -> dict:
    every = [item for group in groups for item in group["slugs"]]
    covered = sum(1 for item in every if item["count"])
    return {
        "total": len(every),
        "covered": covered,
        "percent": round(covered * 100 / len(every)) if every else 0,
    }


def build_stack(ctx) -> dict:
    """기술스택 화면.

    **두 축을 섞지 않는다.** 로드맵 100개는 *직접 만들어 보는 것* 이고
    CS 49개는 *면접에서 묻는 것* 이라, 한 막대로 합치면 어느 쪽이 비었는지
    알 수 없다.
    """
    counts = _counts(ctx)
    wanted = demand(list_companies(ctx))
    groups = _group_rows(topics.SLUG_GROUPS, counts, wanted)
    cs_groups = _group_rows(topics.CS_GROUPS, counts, wanted)

    every = [item for group in groups for item in group["slugs"]]
    # 먼저 할 것 — **요구하는 회사가 많은데 기록이 0건인 것.** 하나를 채우면
    # 여러 회사의 막대가 같이 오르므로, 같은 노력으로 가장 많이 움직인다.
    first = sorted(
        [item for item in every if not item["count"] and item["companies"]],
        key=lambda item: (-len(item["companies"]), item["slug"]),
    )
    known = {item["slug"] for item in every} | set(topics.CS_SLUGS)
    return {
        "groups": groups,
        "cs_groups": cs_groups,
        "first": first,
        "coverage": _tally(groups),
        "cs_coverage": _tally(cs_groups),
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
            "exams": [], "links": [], "stages": [], "next": None, "status": "미시작",
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

    # 단계(필기·실기 · 1차·2차). **이 화면의 주인공이다** — 자격증은 슬러그
    # 목록이 아니라 시험이고, 시험은 단계마다 유형도 공부법도 다르다.
    stages = []
    for item in meta.get("stages") or []:
        name, state = _fields(item, 2)
        if name:
            stages.append({"name": name, "state": state or "미시작",
                           "done": state == _CERT_DONE})
    for stage in stages:
        stage["next"] = next(
            (row for row in exams
             if not row["past"] and row["mine"] and row["stage"] == stage["name"]),
            None,
        )

    return {
        "meta": meta,
        "status": meta.get("status") or "미시작",
        "done": (meta.get("status") or "") == _CERT_DONE,
        "issuer": meta.get("issuer") or "",
        "site": meta.get("site") or "",
        "checked": meta.get("checked") or "",
        "exams": exams,
        "links": links,
        "stages": stages,
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
    for group in stack["groups"] + stack["cs_groups"]:
        if group["key"] != key:
            continue
        for row in group["slugs"]:
            note = topicview.topic_note(ctx, row["slug"])
            row["asks"] = note["asks"]
            row["refs"] = note["refs"]
        group["asks_total"] = sum(len(row["asks"]) for row in group["slugs"])
        group["intro"] = _group_intro(ctx, key)
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
