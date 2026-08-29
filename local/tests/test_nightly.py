"""하루가 끝나면 어제 주제로 초안을 만들어 둔다.

**새 프로세스도 새 포트도 만들지 않는다** — 이미 도는 스위퍼 안에 함수로 들어간다
(`AGENTS.md` §3). cron 을 쓰지 않는 이유도 같다. 데몬은 화면 때문에 어차피 떠 있다.

경계 하나가 이 기능의 전부다. **이미 초안이 있는 주제는 건드리지 않는다.**
`upsert_draft` 는 미발행 초안을 덮어쓰므로, 사람이 `save_draft` 로 다듬어 둔 글이
다음 날 밤 조립기 출력으로 덮이면 그 문장은 복원되지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import nightly
from warruru_local.daemon.app import create_app

# KST 2026-08-28 18:00 — 어제는 2026-08-27 이다.
START = datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def client(home, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _record(client, record_id, topic="connection pool", *, when="2026-08-27T09:00:00.000Z", **extra):
    body = {
        "record_id": record_id, "client_instance_id": CLIENT, "tool": "codex",
        "kind": "EXPERIMENT", "topic": topic, "title": "제목", "body": "본문",
        "occurred_at": when,
    }
    body.update(extra)
    return client.post("/v1/records", json=body)


def test_어제_주제로_초안을_만든다(client):
    """오늘은 아직 기록이 더 들어올 수 있다. 어제는 확정된 하루다."""
    _record(client, "rec_A")
    _record(client, "rec_B")
    made = nightly.run(client.app.state.ctx)
    assert made["drafted"] == ["connection-pool"]
    assert client.app.state.ctx.records.latest_draft_of("connection-pool") is not None


def test_같은_날_두_번_돌아도_한_번만_만든다(client):
    """스위퍼는 5분마다 돈다. 표식이 없으면 하루에 288번 만든다."""
    _record(client, "rec_A")
    first = nightly.run(client.app.state.ctx)
    second = nightly.run(client.app.state.ctx)
    assert first["drafted"] == ["connection-pool"]
    assert second["skipped"] == "이미 돌았다"


def test_이미_초안이_있으면_건드리지_않는다(client):
    """사람이 save_draft 로 다듬어 둔 글을 조립기 출력으로 덮으면
    그 문장은 복원되지 않는다. 이 경계가 이 기능의 전부다.
    """
    _record(client, "rec_A")
    client.post("/v1/drafts", json={
        "topic_slug": "connection-pool", "markdown": "# 사람이 다듬은 글\n\n손으로 쓴 문장",
    })
    nightly.run(client.app.state.ctx)
    row = client.app.state.ctx.records.latest_draft_of("connection-pool")
    assert "손으로 쓴 문장" in row["markdown"]


def test_어제_기록이_없으면_아무것도_안_한다(client):
    _record(client, "rec_A", when="2026-08-28T09:00:00.000Z")   # 오늘 것
    made = nightly.run(client.app.state.ctx)
    assert made["drafted"] == []


def test_주제가_여럿이면_각각_만든다(client):
    _record(client, "rec_A", topic="connection pool")
    _record(client, "rec_B", topic="net tcp")
    made = nightly.run(client.app.state.ctx)
    assert sorted(made["drafted"]) == ["connection-pool", "net-tcp"]


def test_한_주제가_실패해도_나머지는_만든다(client, monkeypatch):
    """한 주제의 조립이 터졌다고 그날 밤 전체를 잃지 않는다."""
    _record(client, "rec_A", topic="connection pool")
    _record(client, "rec_B", topic="net tcp")

    from warruru_local.daemon import drafting

    real = drafting.create

    def 가끔_터진다(ctx, topic_slug, **kw):
        if topic_slug == "connection-pool":
            raise RuntimeError("조립 실패")
        return real(ctx, topic_slug, **kw)

    monkeypatch.setattr(nightly.drafting, "create", 가끔_터진다)
    made = nightly.run(client.app.state.ctx)
    assert made["drafted"] == ["net-tcp"]
    assert made["failed"] == ["connection-pool"]


def test_꺼_두면_돌지_않는다(client):
    import dataclasses

    ctx = client.app.state.ctx
    ctx.settings = dataclasses.replace(ctx.settings, nightly_draft=False)
    _record(client, "rec_A")
    assert nightly.run(ctx)["skipped"] == "꺼져 있다"


def test_스위퍼가_이것을_부른다():
    """붙여 두지 않으면 함수만 있고 아무 일도 일어나지 않는다."""
    import inspect

    from warruru_local.daemon import sweeper

    assert "nightly.run" in inspect.getsource(sweeper)


# ── 데몬이 꺼져 있던 날들 ────────────────────────────────────────────────
#
# 이 저장소에는 데몬을 자동으로 띄우는 장치가 없다(launchd 도 cron 도 두지
# 않기로 했다). 그래서 재부팅하면 데몬은 다음 대화까지 죽어 있고, 어제 하루만
# 보면 그 사이 날짜가 영영 잡히지 않는다. 아래가 그 구멍을 막는 테스트다.


def _표식(home, day: str) -> None:
    import json

    from warruru_local import paths

    path = paths.run_dir(home) / nightly.MARKER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": day}), encoding="utf-8")


def test_며칠_꺼져_있었으면_그_사이_날짜도_마감한다(client, home):
    """재부팅하고 사흘 만에 데몬이 떴다. 그 사흘도 마감해야 한다."""
    _표식(home, "2026-08-25")
    _record(client, "rec_A", topic="connection pool", when="2026-08-25T09:00:00.000Z")
    _record(client, "rec_B", topic="net tcp", when="2026-08-26T09:00:00.000Z")
    _record(client, "rec_C", topic="index scan", when="2026-08-27T09:00:00.000Z")

    made = nightly.run(client.app.state.ctx)

    assert sorted(made["drafted"]) == ["connection-pool", "index-scan", "net-tcp"]
    assert (made["from"], made["to"]) == ("2026-08-25", "2026-08-27")


def test_표식의_날짜부터_마감한다(client, home):
    """표식의 날 `D` 에 돈 스위프는 `D-1` 까지 마감했다. `D` 는 아직 남았다.

    첫날을 `D+1` 로 잡으면 데몬이 그날 하루만 떠 있다 꺼진 경우가 샌다.
    """
    _표식(home, "2026-08-27")
    _record(client, "rec_A", when="2026-08-27T09:00:00.000Z")

    made = nightly.run(client.app.state.ctx)

    assert made["drafted"] == ["connection-pool"]
    assert made["from"] == "2026-08-27"


def test_여러_날에_걸친_주제는_한_번만_만든다(client, home):
    """이틀에 걸쳐 같은 주제를 기록했다. 초안은 한 편이다."""
    _표식(home, "2026-08-26")
    _record(client, "rec_A", when="2026-08-26T09:00:00.000Z")
    _record(client, "rec_B", when="2026-08-27T09:00:00.000Z")

    made = nightly.run(client.app.state.ctx)

    assert made["drafted"] == ["connection-pool"]


def test_표식이_없으면_어제만_본다(client):
    """첫 기동에 과거를 통째로 쏟지 않는다. '모르겠으니 넓게' 의 반대로 간다."""
    _record(client, "rec_A", topic="connection pool", when="2026-08-20T09:00:00.000Z")
    _record(client, "rec_B", topic="net tcp", when="2026-08-27T09:00:00.000Z")

    made = nightly.run(client.app.state.ctx)

    assert made["drafted"] == ["net-tcp"]


def test_되돌아보기는_바닥에서_멈춘다(client, home):
    """표식이 아주 오래됐어도 `LOOKBACK_DAYS` 너머는 자동으로 잡지 않는다.

    바닥 너머의 날은 사람이 `/t` 에서 직접 만든다. 초안은 어차피 그 주제의
    기록 전부를 재료로 쓰므로 잃는 것은 편의지 기록이 아니다.
    """
    _표식(home, "2026-01-01")
    # 어제(08-27) 기준 바닥은 08-14 다.
    _record(client, "rec_밖", topic="connection pool", when="2026-08-13T09:00:00.000Z")
    _record(client, "rec_안", topic="net tcp", when="2026-08-14T09:00:00.000Z")

    made = nightly.run(client.app.state.ctx)

    assert made["drafted"] == ["net-tcp"]
    assert made["from"] == "2026-08-14"


def test_표식이_미래면_아무것도_안_한다(client, home):
    """시계가 되돌아간 경우. 마감할 날이 없으므로 조용히 표식만 옮긴다."""
    _표식(home, "2026-09-01")
    _record(client, "rec_A")

    made = nightly.run(client.app.state.ctx)

    assert made["skipped"] == "마감할 날이 없다"
    assert made["drafted"] == []
    assert nightly._last_run(client.app.state.ctx) == "2026-08-28"


def test_밀린_날에도_사람_글은_보존된다(client, home):
    """구간이 넓어져도 경계는 그대로다. 이것이 이 기능의 전부다."""
    _표식(home, "2026-08-25")
    _record(client, "rec_A", when="2026-08-26T09:00:00.000Z")
    client.post("/v1/drafts", json={
        "topic_slug": "connection-pool", "markdown": "# 사람이 다듬은 글\n\n손으로 쓴 문장",
    })

    nightly.run(client.app.state.ctx)

    row = client.app.state.ctx.records.latest_draft_of("connection-pool")
    assert "손으로 쓴 문장" in row["markdown"]


def test_기동만_해도_밀린_날이_마감된다(home, monkeypatch):
    """데몬을 켜는 행위 자체가 '지금 해달라' 는 뜻이다.

    스위퍼에만 맡기면 켜고 나서 한 바퀴(기본 300초)를 기다리게 된다.
    바탕화면 실행 파일로 켜는 경우 그 5분이 곧 '버튼이 안 먹는다' 다.
    """
    monkeypatch.setenv("TZ", "Asia/Seoul")
    import time

    time.tzset()
    settings = load_settings(home)

    # 1차 — 기록만 남기고 닫는다. 배경 작업이 꺼져 있으니 초안은 안 생긴다.
    first = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(first) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        _record(made, "rec_A")
        assert made.app.state.ctx.records.latest_draft_of("connection-pool") is None

    # 2차 — 배경 작업을 켜고 다시 띄운다. 스위프를 기다리지 않는다.
    again = create_app(settings, clock=FixedClock(START), start_background=True)
    with TestClient(again):
        assert again.state.ctx.records.latest_draft_of("connection-pool") is not None
        assert nightly._last_run(again.state.ctx) == "2026-08-28"


def test_배경_작업을_끈_채_띄우면_초안을_만들지_않는다(client):
    """`client` 픽스처가 `start_background=False` 다. 기동만으로 초안이
    생긴다면 이 단언이 깨진다 — 부른 적 없는 부작용이라는 뜻이다.
    """
    assert client.app.state.ctx.records.latest_draft_of("connection-pool") is None
    assert nightly._last_run(client.app.state.ctx) is None
