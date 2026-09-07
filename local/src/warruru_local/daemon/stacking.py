"""기술스택 — **목차는 슬러그가 만들고, 절은 내가 쓴다** (명세 §2.12).

축 셋(로드맵 · CS · AI)은 "만들면서 겪나 / 앉아서 공부하나" 로 갈랐다.
이쪽은 **이력서와 공고에 적히는 말**로 가른다 — Java · Spring · RDBMS ·
Redis · Kubernetes · AWS. 공고 8곳의 `required` 가 쓰는 단어 그대로다.

**정리 한 장이 화면이다.** 파일 하나가 스택 하나이고, 그 파일의 `## 슬러그`
절이 화면의 절이 된다. 기록·질문·책은 슬러그로 자동으로 붙는다 —
근거는 시스템이 대고 문장은 내가 쓴다.

**날짜로 자르지 않는다.** 책 노트는 하루치가 한 장이지만 스택 정리는
쌓이는 것이 아니라 고쳐 쓰는 것이라, 하루치로 자르면 이어지지 않는다.
"""

from __future__ import annotations

import re

from warruru_local import paths, topics
from warruru_local.daemon.careerview import parse_front_matter

KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# 절 하나의 상한. 넘으면 자른다 — 화면을 멈추게 하는 글보다 잘린 글이 낫다.
SECTION_MAX = 20_000

# `## 슬러그` 로 절이 열린다. 뒤에 무엇이 붙어도(제목 등) 슬러그만 읽는다.
_HEAD = re.compile(r"^##\s+([a-z0-9][a-z0-9-]*)\s*(.*)$")


def note_path(ctx, key: str):
    """이 값이 그대로 파일 이름이 된다. 규칙 밖이면 `None`."""
    if not KEY.match(key or ""):
        return None
    return paths.stack_note_dir(ctx.settings.home) / f"{key}.md"


def defined(ctx) -> list[tuple[str, str]]:
    """스택 목록. **코드 상수 ∪ 노트 파일**이다.

    화면에서 더한 스택은 코드에 없으므로, 상수만 읽으면 방금 만든 것이
    안 보인다. 자격증이 같은 이유로 같은 모양을 쓴다.
    """
    made = [(key, name) for key, name, _, _ in topics.STACKS]
    있는키 = {key for key, _ in made}
    root = paths.stack_note_dir(ctx.settings.home)
    if root.is_dir():
        for path in sorted(root.glob("*.md")):
            if path.stem in 있는키 or not KEY.match(path.stem):
                continue
            meta, _ = parse_front_matter(
                path.read_text(encoding="utf-8", errors="replace"))
            made.append((path.stem, meta.get("name") or path.stem))
    return made


def slugs_of(ctx, key: str) -> list[str]:
    """이 스택이 안는 주제. **노트가 있으면 노트가 이긴다** —
    화면에서 옮긴 것이 코드 상수에 눌리면 옮긴 뜻이 없다."""
    path = note_path(ctx, key)
    if path is not None and path.is_file():
        meta, _ = parse_front_matter(
            path.read_text(encoding="utf-8", errors="replace"))
        적힌것 = meta.get("slugs")
        if isinstance(적힌것, list):
            return [str(s).strip() for s in 적힌것 if str(s).strip()]
    return list(topics.stack_slugs(key))


def sections(ctx, key: str) -> dict[str, str]:
    """내가 쓴 절들. `## 슬러그` 로 갈린다."""
    path = note_path(ctx, key)
    if path is None or not path.is_file():
        return {}
    _, body = parse_front_matter(
        path.read_text(encoding="utf-8", errors="replace"))
    made: dict[str, list[str]] = {}
    지금 = None
    for line in body.splitlines():
        머리 = _HEAD.match(line)
        if 머리:
            지금 = 머리.group(1)
            made.setdefault(지금, [])
            continue
        if 지금 is not None:
            made[지금].append(line)
    return {slug: "\n".join(줄).strip() for slug, 줄 in made.items()}


def _write(ctx, key: str, name: str, slugs: list[str],
           절: dict[str, str]) -> bool:
    """파일 한 장을 다시 쓴다. **순서는 `slugs` 가 정한다** —
    내가 쓴 순서가 아니라 목차 순서라야 화면과 파일이 같아 보인다."""
    path = note_path(ctx, key)
    if path is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    머리 = [f"name: {name}"] if name else []
    머리.append("slugs:")
    머리 += [f"  - {slug}" for slug in slugs]
    몸 = []
    for slug in slugs:
        글 = (절.get(slug) or "").strip()
        if 글:
            몸.append(f"## {slug}\n\n{글}\n")
    # 목차에서 빠졌는데 글이 남은 것을 버리지 않는다. 옮긴 주제의 글이
    # 조용히 사라지는 것이 이 파일에서 가장 나쁜 결말이다.
    for slug, 글 in 절.items():
        if slug not in slugs and 글.strip():
            몸.append(f"## {slug}\n\n{글.strip()}\n")
    path.write_text("---\n" + "\n".join(머리) + "\n---\n\n" + "\n".join(몸),
                    encoding="utf-8")
    return True


def save_section(ctx, key: str, slug: str, text: str) -> bool:
    """절 하나를 쓴다. 나머지 절과 목차는 그대로 둔다."""
    if note_path(ctx, key) is None or not KEY.match(slug or ""):
        return False
    절 = sections(ctx, key)
    절[slug] = text[:SECTION_MAX]
    return _write(ctx, key, name_of(ctx, key), slugs_of(ctx, key), 절)


def name_of(ctx, key: str) -> str:
    return dict(defined(ctx)).get(key, key)


def add(ctx, key: str, name: str) -> bool:
    """스택 하나를 늘린다. **있으면 덮지 않는다.**"""
    path = note_path(ctx, key)
    if path is None or not name.strip() or path.exists():
        return False
    if key in {k for k, _, _, _ in topics.STACKS}:
        return False
    return _write(ctx, key, name.strip(), [], {})


def move(ctx, slug: str, frm: str, to: str) -> bool:
    """주제를 다른 스택으로 옮긴다. **양쪽 노트가 다 생긴다** —
    한쪽만 쓰면 그 주제가 두 곳에 서거나 어느 곳에도 안 선다."""
    if not KEY.match(slug or "") or frm == to:
        return False
    if note_path(ctx, frm) is None or note_path(ctx, to) is None:
        return False
    남은것 = [s for s in slugs_of(ctx, frm) if s != slug]
    if len(남은것) == len(slugs_of(ctx, frm)):
        return False            # 원래 그 스택에 없던 주제다
    받는쪽 = slugs_of(ctx, to)
    if slug not in 받는쪽:
        받는쪽 = 받는쪽 + [slug]
    return (_write(ctx, frm, name_of(ctx, frm), 남은것, sections(ctx, frm))
            and _write(ctx, to, name_of(ctx, to), 받는쪽, sections(ctx, to)))


# ── 화면이 받는 것 ──────────────────────────────────────────────

def build_index(ctx) -> list[dict]:
    """스택 목록. **공고가 많이 요구하는 순**이다.

    "얼마나 했나" 로 세우면 이미 한 것이 위로 오는데, 이 화면이 답할 것은
    무엇을 채우느냐다.
    """
    from warruru_local.daemon import careerview

    counts = {row["topic_slug"]: row["count"]
              for row in ctx.records.slug_summary()}
    wanted = careerview.demand(careerview.list_companies(ctx))
    made = []
    for key, name in defined(ctx):
        slugs = slugs_of(ctx, key)
        절 = sections(ctx, key)
        회사 = {c for slug in slugs for c in wanted.get(slug, [])}
        made.append({
            "key": key, "name": name,
            "total": len(slugs),
            "written": sum(1 for s in slugs if 절.get(s, "").strip()),
            "records": sum(counts.get(s, 0) for s in slugs),
            "companies": sorted(회사),
        })
    return sorted(made, key=lambda row: (-len(row["companies"]), -row["records"]))


def build(ctx, key: str) -> dict | None:
    """정리 한 장. 목차는 슬러그가 만들고, 절마다 근거가 붙는다."""
    from warruru_local.daemon import careerview, topicview

    이름들 = dict(defined(ctx))
    if key not in 이름들:
        return None
    counts = {row["topic_slug"]: row["count"]
              for row in ctx.records.slug_summary()}
    checked = ctx.records.checked_asks()
    wanted = careerview.demand(careerview.list_companies(ctx))
    책 = {}
    for 책키, 책이름, 책슬러그 in topics.BOOK_GROUPS:
        for slug in 책슬러그:
            책.setdefault(slug, []).append({"key": 책키, "label": 책이름})

    슬러그들 = slugs_of(ctx, key)
    절 = sections(ctx, key)
    목차 = []
    for slug in 슬러그들:
        note = topicview.topic_note(ctx, slug)
        asks = note["asks"]
        목차.append({
            "slug": slug, "label": topics.label_of(slug),
            "text": 절.get(slug, "").strip(),
            "written": bool(절.get(slug, "").strip()),
            "records": counts.get(slug, 0),
            "asks": len(asks),
            "asked": sum(1 for a in asks if a["hash"] in checked),
            "companies": wanted.get(slug, []),
            "books": 책.get(slug, [])[:2],
        })
    # 빈 절이 위로 온다. **채우러 오는 화면이다** — 다 쓴 것이 먼저 서면
    # 스크롤을 내려야 할 일이 나온다. 같은 조건이면 공고가 많이 찾는 것.
    목차.sort(key=lambda row: (row["written"], -len(row["companies"]),
                              -row["records"]))
    return {
        "key": key, "name": 이름들[key],
        "toc": 목차,
        "total": len(목차),
        "written": sum(1 for row in 목차 if row["written"]),
        "records": sum(row["records"] for row in 목차),
        "companies": sorted({c for row in 목차 for c in row["companies"]}),
        "others": [(k, n) for k, n in 이름들.items() if k != key],
    }
