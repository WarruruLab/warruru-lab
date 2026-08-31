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

from warruru_local import paths
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
                "slugs": [{"slug": s, "count": counts.get(s, 0)} for s in slugs],
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
        "gaps": [s for s in seen if not counts.get(s)],
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
