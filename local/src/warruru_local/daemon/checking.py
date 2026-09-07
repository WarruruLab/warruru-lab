"""CS 지식 — 답할 수 있나 점검한다 (명세 §2.10).

**체크의 목적은 "몇 개 했나" 가 아니라 오늘 볼 목록을 만드는 것이다.**
27개를 다 보면 아무것도 안 하고 5개면 한다. 체크가 0개였던 이유가 그것이다 —
눌러도 아무 일이 안 생겼다.
"""

from __future__ import annotations

from datetime import date as _date

from warruru_local import paths, topics
from warruru_local.daemon.topicview import ask_hash

# 과목마다 이만큼만 뽑는다(2026-09-08 확정).
PICKS = 5

# 이만큼 지나면 다시 묻는다. 한 번 체크했다고 3월까지 기억할 리 없다.
STALE_DAYS = 90


def _days_since(then: str, today: str) -> int | None:
    try:
        return _date.fromisoformat(today).toordinal() - \
            _date.fromisoformat(then[:10]).toordinal()
    except (TypeError, ValueError):
        return None


def is_stale(checked_at: str | None, today: str) -> bool:
    """체크가 낡았나. **체크를 지우지는 않는다** — 지우면 준비도가
    뒷걸음질 치고, 그건 사실이 아니다. 흐리게 하고 다시 물을 뿐이다."""
    if not checked_at:
        return False
    지남 = _days_since(checked_at, today)
    return 지남 is not None and 지남 >= STALE_DAYS


def picks(ctx, group_key: str, today: str, limit: int = PICKS) -> list[dict]:
    """이 과목에서 오늘 볼 것. 순서는 **안 한 것 먼저, 그다음 오래된 것**이다.

    아직 한 번도 안 본 질문이 낡은 체크보다 급하다 — 후자는 한 번은
    답할 수 있었던 것이다.
    """
    from warruru_local.daemon import topicview

    slugs = next((s for k, _, s in topics.CS_GROUPS if k == group_key), ())
    안한것, 낡은것 = [], []
    for slug in slugs:
        note = topicview.topic_note(ctx, slug)
        checked = ctx.records.checked_asks(slug)
        ages = ctx.records.check_ages(slug)
        for ask in note["asks"]:
            줄 = {
                "slug": slug, "label": topics.label_of(slug),
                "text": ask["text"], "hash": ask["hash"],
                "checked_at": ages.get(ask["hash"], ""),
            }
            if ask["hash"] not in checked:
                안한것.append(줄)
            elif is_stale(ages.get(ask["hash"]), today):
                줄["stale"] = True
                낡은것.append(줄)
    return (안한것 + 낡은것)[:limit]


def stale_count(ctx, group_key: str, today: str) -> int:
    """다시 봐야 할 것의 수. 과목 머리에 붙는다."""
    from warruru_local.daemon import topicview

    slugs = next((s for k, _, s in topics.CS_GROUPS if k == group_key), ())
    n = 0
    for slug in slugs:
        ages = ctx.records.check_ages(slug)
        n += sum(1 for at in ages.values() if is_stale(at, today))
    return n


def books_for(group_key: str) -> list[dict]:
    """이 과목을 덮는 책. **많이 덮는 순**이다.

    막힌 자리에서 책으로 가는 길이 한 번에 이어져야 그 책을 편다.
    """
    slugs = set(next((s for k, _, s in topics.CS_GROUPS if k == group_key), ()))
    made = []
    for key, label, book_slugs in topics.BOOK_GROUPS:
        겹침 = slugs & set(book_slugs)
        if 겹침:
            made.append({"key": key, "label": label, "count": len(겹침)})
    return sorted(made, key=lambda b: (-b["count"], b["label"]))


# ── 내가 쓴 답 ───────────────────────────────────────────────────
#
# 질문별로 한 파일. **기본으로 안 보인다** — 눌러야 펼쳐진다(명세 §2.10 d).
# 다시 물을 때 "그때 내 답" 과 "빠뜨렸던 것" 을 같이 보여주면 백지에서
# 시작하지 않고, 나아졌는지가 보인다.

def answer_path(ctx, slug: str, hash_: str):
    from warruru_local.daemon.reading import SLUG

    if not SLUG.match(slug) or not hash_.isalnum() or len(hash_) > 64:
        return None
    return paths.topic_note_dir(ctx.settings.home) / slug / "answers" / f"{hash_}.md"


def my_answers(ctx, slug: str, hash_: str) -> list[dict]:
    """이 질문에 내가 답한 것들. 최신순."""
    path = answer_path(ctx, slug, hash_)
    if path is None or not path.is_file():
        return []
    made = []
    for 덩이 in path.read_text(encoding="utf-8", errors="replace").split("\n---\n"):
        덩이 = 덩이.strip()
        if not 덩이:
            continue
        날짜, _, 본문 = 덩이.partition("\n")
        made.append({"day": 날짜.strip("# ").strip(), "text": 본문.strip()})
    return list(reversed(made))


def save_answer(ctx, slug: str, hash_: str, day: str, text: str,
                review: str = "") -> bool:
    """답 하나를 덧붙인다. **덮어쓰지 않는다** — 3개월 뒤에 그때 답과
    지금 답을 나란히 봐야 나아졌는지가 보인다."""
    path = answer_path(ctx, slug, hash_)
    if path is None or not text.strip():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    덩이 = f"# {day}\n{text.strip()}\n"
    if review.strip():
        덩이 += f"\n> {review.strip()}\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(("\n---\n" if path.stat().st_size else "") + 덩이)
    return True
