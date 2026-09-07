"""CS 지식 점검 (명세 §2.10).

**체크의 목적은 "몇 개 했나" 가 아니라 오늘 볼 목록을 만드는 것이다.**
체크가 0개였던 이유가 그것이다 — 눌러도 아무 일이 안 생겼다.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import checking
from warruru_local.daemon.app import create_app
from warruru_local.daemon.topicview import ask_hash

START = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)
TODAY = "2026-09-08"


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


@pytest.fixture
def ctx(client):
    return client.app.state.ctx


def _note(home, slug, asks):
    root = paths.topic_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"  - {a}" for a in asks)
    (root / f"{slug}.md").write_text(f"---\nasks:\n{body}\n---\n\n본문\n",
                                     encoding="utf-8")


# ── 3개월이 지나면 다시 묻는다 ────────────────────────────────────

def test_체크가_3개월_지나면_낡는다():
    """한 번 체크했다고 3월까지 기억할 리 없다."""
    assert checking.is_stale("2026-06-01T00:00:00.000Z", TODAY) is True   # 99일
    assert checking.is_stale("2026-07-01T00:00:00.000Z", TODAY) is False  # 69일
    assert checking.is_stale("", TODAY) is False
    assert checking.is_stale(None, TODAY) is False


def test_낡은_체크를_지우지는_않는다(client, ctx, home):
    """지우면 준비도가 뒷걸음질 치는데, 그건 사실이 아니다.
    한 번은 답할 수 있었다."""
    _note(home, "net-tcp", ["TCP 와 UDP 의 차이는?"])
    h = ask_hash("TCP 와 UDP 의 차이는?")
    ctx.records.toggle_ask("net-tcp", h, "TCP 와 UDP 의 차이는?",
                           "2026-01-01T00:00:00.000Z")
    assert h in ctx.records.checked_asks("net-tcp")      # 여전히 체크돼 있다
    assert checking.is_stale(ctx.records.check_ages("net-tcp")[h], TODAY)


# ── 오늘 볼 N개 ─────────────────────────────────────────────────

def test_안_한_것이_낡은_것보다_먼저다(client, ctx, home):
    """아직 한 번도 안 본 질문이 낡은 체크보다 급하다 —
    후자는 한 번은 답할 수 있었던 것이다."""
    _note(home, "net-tcp", ["묻지 않은 것", "오래전에 체크한 것"])
    ctx.records.toggle_ask("net-tcp", ask_hash("오래전에 체크한 것"),
                           "오래전에 체크한 것", "2026-01-01T00:00:00.000Z")
    뽑힘 = checking.picks(ctx, "network", TODAY)
    assert [p["text"] for p in 뽑힘] == ["묻지 않은 것", "오래전에 체크한 것"]
    assert 뽑힘[1]["stale"] is True


def test_최근에_체크한_것은_안_뽑힌다(client, ctx, home):
    _note(home, "net-tcp", ["방금 체크한 것"])
    ctx.records.toggle_ask("net-tcp", ask_hash("방금 체크한 것"),
                           "방금 체크한 것", "2026-09-01T00:00:00.000Z")
    assert checking.picks(ctx, "network", TODAY) == []


def test_과목마다_다섯_개만(client, ctx, home):
    """27개를 다 보면 아무것도 안 하고 5개면 한다."""
    _note(home, "net-tcp", [f"질문 {n}" for n in range(12)])
    assert len(checking.picks(ctx, "network", TODAY)) == 5
    assert checking.PICKS == 5


def test_다시_봐야_할_것을_센다(client, ctx, home):
    _note(home, "net-tcp", ["하나", "둘"])
    for text, when in (("하나", "2026-01-01T00:00:00.000Z"),
                       ("둘", "2026-09-01T00:00:00.000Z")):
        ctx.records.toggle_ask("net-tcp", ask_hash(text), text, when)
    assert checking.stale_count(ctx, "network", TODAY) == 1


# ── 막히면 이 책 ────────────────────────────────────────────────

def test_이_과목을_덮는_책이_많이_덮는_순으로(client):
    """막힌 자리에서 책으로 가는 길이 한 번에 이어져야 그 책을 편다."""
    books = checking.books_for("network")
    assert books, "네트워크를 덮는 책이 있어야 한다"
    assert [b["count"] for b in books] == sorted(
        (b["count"] for b in books), reverse=True)
    assert "컴퓨터 네트워킹 하향식 접근" in [b["label"] for b in books]


# ── 내가 쓴 답 ──────────────────────────────────────────────────

def test_답을_덧붙인다_덮어쓰지_않는다(ctx):
    """3개월 뒤에 그때 답과 지금 답을 나란히 봐야 나아졌는지가 보인다."""
    h = ask_hash("TCP 3-way handshake 가 왜 세 번인가?")
    checking.save_answer(ctx, "net-tcp", h, "2026-06-12", "예전 답",
                         review="ISN 이 빠졌다")
    checking.save_answer(ctx, "net-tcp", h, "2026-09-08", "지금 답")
    답 = checking.my_answers(ctx, "net-tcp", h)
    assert [a["day"] for a in 답] == ["2026-09-08", "2026-06-12"]   # 최신순
    assert "ISN 이 빠졌다" in 답[1]["text"]


def test_빈_답은_안_남긴다(ctx):
    assert checking.save_answer(ctx, "net-tcp", "abc", "2026-09-08", "  ") is False


@pytest.mark.parametrize("slug,h", [
    ("..", "abc"), ("../etc", "abc"), ("net-tcp", "../x"), ("net-tcp", "a" * 90),
])
def test_답_경로가_홈_밖으로_안_샌다(ctx, slug, h):
    assert checking.answer_path(ctx, slug, h) is None
    assert checking.save_answer(ctx, slug, h, "2026-09-08", "본문") is False
