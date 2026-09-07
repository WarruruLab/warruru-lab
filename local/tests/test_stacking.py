"""기술스택 — 이력서와 공고에 적히는 말로 가른 축 (명세 §2.12).

축 셋(로드맵 · CS · AI)은 "만들면서 겪나 / 앉아서 공부하나" 로 갈랐다.
그 자름은 공부에는 맞지만 **이력서에 적을 때는 안 맞는다** — 공고는
`spring-di` 라고 쓰지 않고 Spring 이라고 쓴다.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths, topics
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import stacking
from warruru_local.daemon.app import create_app

START = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)


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


# ── 분류 ────────────────────────────────────────────────────────

def test_스택이_슬러그를_다_덮는다():
    """**남는 슬러그가 하나라도 있으면 그것은 어느 화면에서도 안 보인다.**

    180개가 14개로 빠짐없이 갈린다. 축을 늘리거나 슬러그를 더할 때
    이 테스트가 먼저 깨져야 한다.
    """
    전체 = topics.all_slugs()
    남은것 = [slug for slug in 전체 if not topics.stack_of(slug)]
    assert 남은것 == [], 남은것
    붙은수 = sum(len(topics.stack_slugs(key)) for key, *_ in topics.STACKS)
    assert 붙은수 == len(전체)     # 두 스택에 겹쳐 붙지도 않는다


def test_이름이_접두어를_이긴다():
    """`security-group-nacl` 은 AWS 것이지 웹 보안이 아니다."""
    assert topics.stack_of("security-group-nacl") == "aws"
    assert topics.stack_of("spring-di") == "spring"
    assert topics.stack_of("kafka-basics") == "mq"


def test_모르는_슬러그는_빈_값이다():
    assert topics.stack_of("없는-것") == ""


# ── 정리 한 장 ──────────────────────────────────────────────────

def test_목차는_슬러그가_만들고_절은_내가_쓴다(client, ctx):
    token = ctx.settings.token
    res = client.post("/web/stacks/spring/section", data={
        "_token": token, "slug": "spring-di",
        "text": "생성자 주입을 쓰는 이유는 불변과 테스트 때문이다.",
    })
    assert res.status_code == 200 and res.json()["saved_at"]
    view = stacking.build(ctx, "spring")
    쓴것 = {row["slug"]: row for row in view["toc"]}
    assert 쓴것["spring-di"]["written"] is True
    assert "생성자 주입" in 쓴것["spring-di"]["text"]
    assert 쓴것["spring-mvc"]["written"] is False
    assert view["written"] == 1 and view["total"] == len(topics.stack_slugs("spring"))


def test_빈_절이_위로_온다(ctx):
    """**채우러 오는 화면이다.** 다 쓴 것이 먼저 서면 스크롤을 내려야
    할 일이 나온다."""
    stacking.save_section(ctx, "spring", "spring-di", "썼다")
    순서 = [row["written"] for row in stacking.build(ctx, "spring")["toc"]]
    assert 순서[0] is False and 순서[-1] is True


def test_파일_한_장이_그대로_화면이다(client, ctx, home):
    """옵시디언에서 열어도 같은 것이 보여야 한다."""
    stacking.save_section(ctx, "spring", "spring-di", "내 글")
    text = (paths.stack_note_dir(home) / "spring.md").read_text(encoding="utf-8")
    assert "## spring-di" in text and "내 글" in text
    assert "slugs:" in text and "  - spring-mvc" in text


def test_절을_고쳐도_다른_절이_안_날아간다(ctx):
    stacking.save_section(ctx, "spring", "spring-di", "첫째")
    stacking.save_section(ctx, "spring", "spring-mvc", "둘째")
    stacking.save_section(ctx, "spring", "spring-di", "첫째 고침")
    절 = stacking.sections(ctx, "spring")
    assert 절["spring-di"] == "첫째 고침" and 절["spring-mvc"] == "둘째"


def test_근거는_시스템이_대고_문장은_내가_쓴다(client, ctx, home):
    """기록 건수 · 면접 질문 · 책이 슬러그로 자동으로 붙는다."""
    client.post("/v1/records", json={
        "record_id": "rec_1", "client_instance_id": "cli_X", "tool": "codex",
        "kind": "CONCEPT", "topic": "db-index", "title": "인덱스", "body": "본문",
    })
    row, = [r for r in stacking.build(ctx, "db")["toc"] if r["slug"] == "db-index"]
    assert row["records"] == 1
    assert row["books"], "이 주제를 덮는 책이 붙어야 한다"


# ── 화면에서 고치기 ─────────────────────────────────────────────

def test_주제를_다른_스택으로_옮긴다(client, ctx):
    """자동 분류를 사람이 고치는 자리다. **양쪽 노트가 다 생긴다** —
    한쪽만 쓰면 그 주제가 두 곳에 서거나 어느 곳에도 안 선다."""
    token = ctx.settings.token
    res = client.post("/web/stacks/spring/move", follow_redirects=False, data={
        "_token": token, "slug": "spring-di", "to": "arch",
    })
    assert res.status_code == 303
    assert "spring-di" not in stacking.slugs_of(ctx, "spring")
    assert "spring-di" in stacking.slugs_of(ctx, "arch")


def test_옮겨도_써_둔_글은_안_없어진다(ctx):
    """옮긴 주제의 글이 조용히 사라지는 것이 이 파일에서 가장 나쁜 결말이다."""
    stacking.save_section(ctx, "spring", "spring-di", "지키고 싶은 글")
    stacking.move(ctx, "spring-di", "spring", "arch")
    assert stacking.sections(ctx, "spring")["spring-di"] == "지키고 싶은 글"


def test_스택을_화면에서_더한다(client, ctx, home):
    token = ctx.settings.token
    res = client.post("/web/stacks/add", follow_redirects=False, data={
        "_token": token, "key": "elasticsearch", "name": "Elasticsearch",
    })
    assert res.status_code == 303
    assert (paths.stack_note_dir(home) / "elasticsearch.md").is_file()
    assert "Elasticsearch" in client.get("/career/stacks").text


def test_코드에_있는_스택을_빈_것으로_덮지_않는다(client, ctx):
    token = ctx.settings.token
    assert client.post("/web/stacks/add", data={
        "_token": token, "key": "spring", "name": "Spring",
    }).status_code == 400
    assert stacking.slugs_of(ctx, "spring")     # 목차가 살아 있다


@pytest.mark.parametrize("key", ["../etc", "Spring", "a b", ""])
def test_스택_키가_홈_밖으로_안_샌다(client, ctx, key):
    """이 값이 그대로 파일 이름이 된다."""
    token = ctx.settings.token
    assert client.post("/web/stacks/add", data={
        "_token": token, "key": key, "name": "무엇",
    }).status_code == 400


def test_절_저장도_토큰을_요구한다(client):
    assert client.post("/web/stacks/spring/section",
                       data={"slug": "spring-di", "text": "글"}).status_code == 401


def test_없는_스택은_404(client):
    assert client.get("/career/s/없는것").status_code == 404


# ── 목록 ────────────────────────────────────────────────────────

def test_공고가_많이_요구하는_순으로_선다(client, ctx, home):
    """'얼마나 했나' 로 세우면 이미 한 것이 위로 오는데,
    이 화면이 답할 것은 무엇을 채우느냐다."""
    root = paths.career_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / "acme.md").write_text(
        "---\ncompany: 에이콤\nrequired:\n  - Spring | spring-di, spring-mvc\n---\n",
        encoding="utf-8")
    목록 = stacking.build_index(ctx)
    assert 목록[0]["key"] == "spring"
    assert 목록[0]["companies"] == ["에이콤"]
