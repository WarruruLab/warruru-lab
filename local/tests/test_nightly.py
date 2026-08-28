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
