"""책 노트 — 읽으며 쓰고, 기록으로 올린다 (명세 §2.9).

**노트는 내가 쓴 것이고 답은 받은 것이다.** 두 자리를 가르는 것이 이 파일의
이유다 — 섞이면 나중에 "내 말로 쓴 것" 만 골라낼 수 없고, 그 구분이 없으면
기록이 대화 사본이 된다.

노트는 `~/.warruru/career/books/{책}/notes/{날짜}.md` 다.
앞머리에 그날 이 노트에서 올린 `records:` 를 적어 둔다 — DB 에 컬럼을
더하지 않고도 "이 노트에서 몇 건 올렸나" 를 셀 수 있다.
"""

from __future__ import annotations

import re
from pathlib import Path

from warruru_local import paths, topics
from warruru_local.daemon.careerview import parse_front_matter
from warruru_local.publish import tistory_clipboard

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 노트 한 장의 상한. 넘으면 자른다 — 브라우저가 멈추는 것보다 낫고,
# 하루치 노트가 이만큼 넘을 일은 없다.
NOTE_MAX = 60_000


def note_path(ctx, key: str, day: str) -> Path | None:
    """`None` 이면 이름이 규칙 밖이다. **경로를 만들기 전에 거른다** —
    이 값이 그대로 디렉터리가 되므로 `..` 하나로 홈 밖에 앉는다."""
    if not SLUG.match(key) or not DAY.match(day):
        return None
    return paths.book_note_day_dir(ctx.settings.home, key) / f"{day}.md"


def read_note(ctx, key: str, day: str) -> dict:
    """없으면 빈 노트다. 빈 것이 고장이 아니라 시작이다."""
    path = note_path(ctx, key, day)
    if path is None or not path.is_file():
        return {"text": "", "records": [], "exists": False}
    meta, body = parse_front_matter(
        path.read_text(encoding="utf-8", errors="replace")
    )
    ids = meta.get("records")
    return {
        "text": body.strip("\n"),
        "records": [str(x).strip() for x in ids] if isinstance(ids, list) else [],
        "exists": True,
    }


def write_note(ctx, key: str, day: str, text: str,
               records: list[str] | None = None) -> bool:
    """자동 저장이 부르는 자리. **앞머리의 `records` 는 지키고 본문만 바꾼다** —
    글을 고치는 동안 올린 기록 목록이 날아가면 안 된다."""
    path = note_path(ctx, key, day)
    if path is None:
        return False
    keep = records if records is not None else read_note(ctx, key, day)["records"]
    path.parent.mkdir(parents=True, exist_ok=True)
    머리 = ""
    if keep:
        줄 = "\n".join(f"  - {rid}" for rid in keep)
        머리 = f"---\nrecords:\n{줄}\n---\n\n"
    path.write_text(머리 + text[:NOTE_MAX].strip("\n") + "\n", encoding="utf-8")
    return True


def days_of(ctx, key: str) -> list[str]:
    """이 책의 노트가 있는 날들. 최신순."""
    if not SLUG.match(key):
        return []
    root = paths.book_note_day_dir(ctx.settings.home, key)
    if not root.is_dir():
        return []
    return sorted((p.stem for p in root.glob("*.md") if DAY.match(p.stem)),
                  reverse=True)


def notes_on(ctx, day: str) -> list[dict]:
    """그날 **모든 책**의 노트. `/notes/{날짜}` 가 읽는다.

    노트 축과 기록 축은 다르다 — 개발하며 훅이 남긴 기록에는 노트가 없고,
    책을 읽고 쓴 노트에는 기록이 없을 수 있다. 그 차이가 보여야 한다.
    """
    if not DAY.match(day):
        return []
    root = paths.book_note_dir(ctx.settings.home)
    if not root.is_dir():
        return []
    made = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not SLUG.match(folder.name):
            continue
        note = read_note(ctx, folder.name, day)
        if not note["exists"] or not note["text"].strip():
            continue
        made.append({
            "key": folder.name,
            "label": _book_label(folder.name),
            "html": tistory_clipboard.to_html(note["text"]),
            "records": note["records"],
        })
    return made


def _book_label(key: str) -> str:
    for k, label, _ in topics.BOOK_GROUPS:
        if k == key:
            return label
    return key


def covered(ctx, key: str) -> dict:
    """진도 — **덮는 주제 중 기록이 있는 것**(명세 §2.9 a).

    몇 장 읽었나가 아니다. 손이 안 가고, 읽기만 하고 안 남기는 것이 잡힌다.
    """
    slugs = next((s for k, _, s in topics.BOOK_GROUPS if k == key), ())
    counts = {row["topic_slug"]: row["count"] for row in ctx.records.slug_summary()}
    have = [s for s in slugs if counts.get(s)]
    return {"covered": len(have), "total": len(slugs), "slugs": list(slugs)}


# ── 노트를 기록으로 ──────────────────────────────────────────────
#
# **받아 적은 문장은 올리지 않는다**(명세 §2.9 c). 이 한 줄이 이 프롬프트의
# 이유다 — 챗봇이 설명한 것을 내가 안 것으로 올리면 준비도는 오르는데
# 면접에서는 못 쓴다.
#
# 화면에서 만들지 않고 여기 둔다. 두 화면이 조금씩 다른 문장을 보내기
# 시작하면 어느 쪽이 옳은지 알 방법이 없다.
PROMOTE_PROMPT = """아래는 내가 책을 읽으며 쓴 노트다. 이걸 학습 기록으로 만들어라.

규칙:
- **내가 내 말로 쓴 것만** 기록으로 만든다. 네가(에이전트가) 설명해 준 것을
  내가 옮겨 적기만 한 문장은 **빼라.** 뺀 것은 `skipped` 에 이유와 함께 적어라.
- 본문은 **내 노트 문장을 그대로** 쓴다. 다듬지 말고 지어내지 마라.
- 주제는 아래 목록에서만 고른다.
- 최대 5건. 내용이 같으면 한 건으로 묶어라.

고를 수 있는 주제: {slugs}

JSON 만 출력해라. 다른 말을 붙이지 마라.
{{"records": [{{"title": "...", "topic": "<슬러그>", "kind": "CONCEPT", "body": "..."}}],
  "skipped": ["...(왜 뺐는지)"]}}

--- 노트 ---
{note}
"""


def promote_prompt(note: str, slugs: list[str]) -> str:
    return PROMOTE_PROMPT.format(slugs=" · ".join(slugs), note=note.strip())


def parse_candidates(text: str, slugs: list[str]) -> dict:
    """모델이 뱉은 것에서 JSON 을 건져 낸다.

    **코드펜스와 앞뒤 말을 견딘다.** "JSON 만 출력해라" 라고 적어도 설명을
    붙이는 일이 있고, 그때 통째로 실패하면 사용자는 노트를 다시 쓸 수 없다.
    모르는 슬러그는 버린다 — 목록 밖에 쌓인 기록은 어느 화면에서도 안 보인다.
    """
    import json

    조각 = text.strip()
    if "```" in 조각:
        조각 = max(조각.split("```"), key=len)
        조각 = 조각.split("\n", 1)[1] if 조각.lstrip().startswith("json") else 조각
    start, end = 조각.find("{"), 조각.rfind("}")
    if start < 0 or end <= start:
        return {"records": [], "skipped": [], "broken": True}
    try:
        made = json.loads(조각[start:end + 1])
    except json.JSONDecodeError:
        return {"records": [], "skipped": [], "broken": True}

    허용 = set(slugs)
    rows = []
    for row in (made.get("records") or [])[:5]:
        if not isinstance(row, dict):
            continue
        topic = str(row.get("topic") or "").strip()
        title = str(row.get("title") or "").strip()
        body = str(row.get("body") or "").strip()
        if topic not in 허용 or not title or not body:
            continue
        kind = str(row.get("kind") or "CONCEPT").strip().upper()
        rows.append({
            "title": title[:200], "topic": topic, "body": body[:4000],
            "kind": kind if kind in
            ("CONCEPT", "TROUBLESHOOTING", "TECH_CHOICE", "EXPERIMENT") else "CONCEPT",
        })
    skipped = [str(x)[:300] for x in (made.get("skipped") or []) if str(x).strip()]
    return {"records": rows, "skipped": skipped[:5], "broken": False}


# ── 목차와 장별 노트 (2026-09-08) ────────────────────────────────
#
# **책을 눌렀을 때 목차가 있어야 한다.** 전에는 책 화면이 "이 책이 덮는
# 주제 0/8" 과 반납일뿐이었다 — 실제로 무엇이 들어 있는 책인지가 화면
# 어디에도 없었다.
#
# 목차는 **사실이라 확인해서 적는다**(노트 앞머리의 `toc:`). 각 장의 본문은
# 내가 쓴다 — 남이 정리한 글을 옮겨 담으면 그건 기록이 아니라 사본이고,
# 이 도구가 계속 지켜 온 선을 여기서 깨게 된다(AGENTS.md §5).

CHAPTER = re.compile(r"^[0-9]{1,3}$")


def toc(ctx, key: str) -> list[dict]:
    """책의 목차. `장번호 | 제목 | 슬러그,슬러그` 로 적는다.

    슬러그는 비워도 된다 — **아직 어느 주제인지 모르는 장이 있는 것이
    정상이다.** 모르는 채로 두는 것이 틀리게 적는 것보다 낫다.
    """
    from warruru_local import topics
    from warruru_local.daemon.careerview import _fields, parse_front_matter

    path = paths.book_note_dir(ctx.settings.home) / f"{key}.md"
    if not path.is_file():
        return []
    meta, _ = parse_front_matter(path.read_text(encoding="utf-8", errors="replace"))
    쓴것 = chapters(ctx, key)
    made = []
    for item in meta.get("toc") or []:
        번호, 제목, 슬러그 = _fields(item, 3)
        if not 번호 or not CHAPTER.match(번호):
            continue
        붙은주제 = [s.strip() for s in 슬러그.split(",") if s.strip()]
        made.append({
            "num": 번호, "title": 제목,
            "slugs": [{"slug": s, "label": topics.label_of(s)} for s in 붙은주제],
            "text": 쓴것.get(번호, ""),
            "written": bool(쓴것.get(번호, "").strip()),
        })
    return made


def chapter_path(ctx, key: str, num: str):
    """장 노트 경로. 장 번호가 숫자가 아니면 `None` 이다 —
    이 값이 그대로 파일 이름이 된다."""
    if not SLUG.match(key) or not CHAPTER.match(num or ""):
        return None
    return paths.book_chapter_dir(ctx.settings.home, key) / f"{num}.md"


def chapters(ctx, key: str) -> dict[str, str]:
    """이 책에 내가 쓴 장 노트 전부."""
    root = paths.book_chapter_dir(ctx.settings.home, key)
    if not SLUG.match(key) or not root.is_dir():
        return {}
    made = {}
    for path in root.glob("*.md"):
        if CHAPTER.match(path.stem):
            made[path.stem] = path.read_text(
                encoding="utf-8", errors="replace").strip()
    return made


def save_chapter(ctx, key: str, num: str, text: str) -> bool:
    """장 노트 하나를 쓴다. 자동 저장이 부르는 자리다."""
    path = chapter_path(ctx, key, num)
    if path is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text[:NOTE_MAX].strip("\n") + "\n", encoding="utf-8")
    return True


def save_book(ctx, key: str, title: str, url: str, body: str) -> bool:
    """받아 본 목차를 책 노트로 앉힌다 (명세 §2.15 d).

    **있으면 앞머리의 `toc:` 만 갈아 끼운다.** 빌린 날 · 반납일 · 읽기 상태는
    사람이 적은 것이라 덮어쓰면 그 사실이 사라진다 — 자동화가 사람의 작업을
    지우는 것은 자동화가 아니라 사고다.
    """
    from warruru_local.daemon.careerview import parse_front_matter

    if not SLUG.match(key or "") or not title.strip():
        return False
    받은것, _ = parse_front_matter(f"---\n{body.strip()}\n---\n")
    새목차 = [str(x) for x in (받은것.get("toc") or [])]
    if not 새목차:
        return False

    path = paths.book_note_dir(ctx.settings.home) / f"{key}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    옛머리, 옛몸 = {}, ""
    if path.is_file():
        옛머리, 옛몸 = parse_front_matter(
            path.read_text(encoding="utf-8", errors="replace"))

    줄 = []
    for 이름 in ("name", "state", "reading", "due", "at", "site"):
        값 = 옛머리.get(이름)
        if isinstance(값, str) and 값:
            줄.append(f"{이름}: {값}")
    if "name" not in 옛머리:
        줄.insert(0, f"name: {title.strip()}")
    if url.strip().startswith(("http://", "https://")) and "site" not in 옛머리:
        줄.append(f"site: {url.strip()}")
    줄.append("toc:")
    줄 += [f"  - {item}" for item in 새목차]

    몸 = 옛몸.strip("\n")
    꼬리 = (받은것.get("_tail") or "").strip()
    path.write_text("---\n" + "\n".join(줄) + "\n---\n\n" + (몸 + "\n" if 몸 else ""),
                    encoding="utf-8")
    return True
