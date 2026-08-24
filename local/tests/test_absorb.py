import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths, spool
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import absorb
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"
THREE = ["ckp_첫째", "ckp_둘째", "ckp_셋째"]
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _age(home, seconds=60):
    """방금 쓴 파일을 조용해진 것으로 만든다."""
    import os
    import time

    for path in paths.spool_dir(home).glob("*.jsonl"):
        stamp = time.time() - seconds
        os.utime(path, (stamp, stamp))


def test_조용해진_파일만_흡수한다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    assert absorb.absorb_all(client.app.state.ctx) == 0  # 아직 쓰는 중일 수 있다
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1


def test_흡수한_기록의_출처는_SPOOL_이다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert client.app.state.ctx.repo.get_checkpoint(CKP)["source"] == "SPOOL"


def test_흡수한_파일은_absorbed_로_옮긴다(client, home):
    spool.append(home, CLIENT, "start_work",
                 {"work_id": WORK, "title": "제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert list(paths.spool_dir(home).glob("*.jsonl")) == []
    assert len(list(paths.absorbed_dir(home).glob("*.jsonl"))) == 1


def test_한_파일_안에_같은_봉투가_두_번_있어도_중복이_생기지_않는다(client, home):
    """같은 파일을 한 번 흡수하는 동안의 멱등성(recording 쪽 책임)을 확인한다."""
    payload = {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON}
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    ctx = client.app.state.ctx
    work_id = ctx.repo.get_checkpoint(CKP)["work_id"]
    assert ctx.repo.count_checkpoints(work_id) == 1


def test_두_번_흡수해도_중복이_생기지_않는다(client, home):
    """path.replace 가 실패해 흡수한 파일이 spool 에 그대로 남는 상황을 흉내낸다.

    다음 스윕이 같은 파일을 다시 집어 들어도 checkpoint 행이 늘어나면 안 된다.
    """
    payload = {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON}
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    ctx = client.app.state.ctx
    assert absorb.absorb_all(ctx) == 1
    assert list(paths.spool_dir(home).glob("*.jsonl")) == []  # 첫 흡수는 정상적으로 옮겨졌다

    # path.replace 실패를 흉내내 같은 봉투를 spool 에 다시 등장시킨다.
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    assert absorb.absorb_all(ctx) == 1  # 두 번째 스윕도 봉투를 처리는 한다

    work_id = ctx.repo.get_checkpoint(CKP)["work_id"]
    assert ctx.repo.count_checkpoints(work_id) == 1


def test_체크포인트가_start_work_보다_먼저_와도_붙는다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "work_id": WORK, "type": "NOTE", "title": "제목",
         **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    ctx = client.app.state.ctx
    assert ctx.repo.get_work(WORK) is not None
    assert ctx.repo.get_checkpoint(CKP)["work_id"] == WORK


def test_봉투는_enqueue_시각_순으로_적용한다(client, home):
    spool.append(home, CLIENT, "record_checkpoint",
                 {"checkpoint_id": "ckp_늦음", "work_id": WORK, "type": "NOTE",
                  "title": "늦음", **COMMON},
                 "2026-07-22T10:00:00.000Z", "evt_B")
    spool.append(home, CLIENT, "start_work",
                 {"work_id": WORK, "title": "원래 제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert client.app.state.ctx.repo.get_work(WORK)["title"] == "원래 제목"


def test_깨진_봉투가_있어도_나머지를_반영한다(client, home):
    target = spool.spool_path(home, CLIENT)
    spool.append(home, CLIENT, "record_checkpoint",
                 {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("{깨짐\n")
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1


def _spool_three(home):
    for index, checkpoint_id in enumerate(THREE):
        spool.append(
            home, CLIENT, "record_checkpoint",
            {"checkpoint_id": checkpoint_id, "type": "NOTE", "title": f"제목{index}",
             **COMMON},
            f"2026-07-22T09:0{index}:00.000Z", f"evt_{index}",
        )
    _age(home)


def _breaking(repo, checkpoint_id, monkeypatch):
    """지정한 체크포인트에서만 저장이 실패하게 만든다."""
    real = repo.insert_checkpoint

    def flaky(**kwargs):
        if kwargs["checkpoint_id"] == checkpoint_id:
            raise sqlite3.OperationalError("database or disk is full")
        return real(**kwargs)

    monkeypatch.setattr(repo, "insert_checkpoint", flaky)
    return real


def test_반영하지_못한_봉투는_사라지지_않고_다시_시도된다(client, home, monkeypatch):
    """저장이 한 번 실패했다고 그 기록이 영원히 사라지면 안 된다."""
    ctx = client.app.state.ctx
    _spool_three(home)
    real = _breaking(ctx.repo, THREE[1], monkeypatch)

    assert absorb.absorb_all(ctx) == 2
    assert ctx.repo.get_checkpoint(THREE[1]) is None

    monkeypatch.setattr(ctx.repo, "insert_checkpoint", real)
    _age(home)
    absorb.absorb_all(ctx)
    assert ctx.repo.get_checkpoint(THREE[1]) is not None


def test_실패한_봉투가_남으면_파일을_보관하지_않는다(client, home, monkeypatch):
    ctx = client.app.state.ctx
    _spool_three(home)
    _breaking(ctx.repo, THREE[1], monkeypatch)

    absorb.absorb_all(ctx)
    assert list(paths.absorbed_dir(home).glob("*.jsonl")) == []


def test_계속_실패하는_봉투는_결국_따로_치운다(client, home, monkeypatch):
    """고칠 수 없는 봉투 하나가 영원히 재시도되지 않게 한다."""
    ctx = client.app.state.ctx
    _spool_three(home)
    _breaking(ctx.repo, THREE[1], monkeypatch)

    for _ in range(absorb.MAX_ATTEMPTS):
        _age(home)
        absorb.absorb_all(ctx)

    dead = list(paths.dead_letter_dir(home).glob("*.jsonl"))
    assert len(dead) == 1
    assert THREE[1] in dead[0].read_text(encoding="utf-8")
    assert len(list(paths.absorbed_dir(home).glob("*.jsonl"))) == 1


def test_흡수하는_동안_덧붙은_줄도_결국_반영된다(client, home, monkeypatch):
    """읽은 뒤에 어댑터가 덧붙인 줄이 읽히지도 않은 채 보관되면 안 된다."""
    ctx = client.app.state.ctx
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "먼저", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)

    real = ctx.repo.insert_checkpoint
    raced = []

    def racy(**kwargs):
        if not raced:  # 첫 봉투를 처리하는 동안 어댑터가 한 줄 덧붙인다
            raced.append(True)
            spool.append(
                home, CLIENT, "record_checkpoint",
                {"checkpoint_id": "ckp_뒤늦게", "type": "NOTE", "title": "나중",
                 **COMMON},
                "2026-07-22T09:01:00.000Z", "evt_B",
            )
        return real(**kwargs)

    monkeypatch.setattr(ctx.repo, "insert_checkpoint", racy)
    absorb.absorb_all(ctx)
    monkeypatch.setattr(ctx.repo, "insert_checkpoint", real)

    # 새로 생긴 대화 파일은 이번 흡수에 휩쓸리지 않는다
    assert spool.spool_path(home, CLIENT).exists()
    _age(home)
    absorb.absorb_all(ctx)
    assert ctx.repo.get_checkpoint("ckp_뒤늦게") is not None


def test_늦게_도착한_start_work_가_자동으로_만든_세션을_올린다(client, home):
    """사용자가 적은 값이 시스템 추측으로 덮여서는 안 된다(FR-05).

    데몬이 꺼져 있을 때 start_work 가 spool 로 갔고, 그 사이 체크포인트는
    HTTP 로 들어와 같은 식별자의 INFERRED 세션을 만든 순서다.
    """
    ctx = client.app.state.ctx
    spool.append(
        home, CLIENT, "start_work",
        {"work_id": WORK, "title": "사용자가 적은 제목", "goal": "목표",
         "started_at": "2026-07-22T09:00:00.000Z", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    client.post(
        "/v1/checkpoints",
        json={"checkpoint_id": CKP, "work_id": WORK, "type": "NOTE",
              "title": "체크포인트 제목", **COMMON},
    )
    _age(home)
    absorb.absorb_all(ctx)

    row = ctx.repo.get_work(WORK)
    assert row["origin"] == "EXPLICIT"
    assert row["title"] == "사용자가 적은 제목"
    assert row["title_origin"] == "USER"
    assert row["goal"] == "목표"
    assert row["started_at"] == "2026-07-22T09:00:00.000Z"


def test_모르는_봉투_버전은_남겨_둔다(client, home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    target.write_text(
        '{"envelope_version": 99, "event_id": "evt_A", "kind": "start_work",'
        ' "enqueued_at": "2026-07-22T09:00:00.000Z", "payload": {}}\n',
        encoding="utf-8",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert target.exists()


def test_학습기록_봉투가_흡수되어_DB_에_들어온다(client, home):
    """온라인 경로와 같은 함수(learning.record)를 부른다. 갈라지면 안 된다."""
    spool.append(
        home, CLIENT, "learning_record",
        {"record_id": "rec_스풀A", "kind": "EXPERIMENT",
         "topic": "connection pool", "title": "제목", "body": "본문", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1
    row = client.app.state.ctx.records.get_record("rec_스풀A")
    assert row["source"] == "SPOOL"
    assert row["topic_slug"] == "connection-pool"


def test_학습기록_봉투를_두_번_흡수해도_한_건이다(client, home):
    for event in ("evt_A", "evt_B"):
        spool.append(
            home, CLIENT, "learning_record",
            {"record_id": "rec_스풀A", "kind": "EXPERIMENT",
             "topic": "connection pool", "title": "제목", "body": "본문", **COMMON},
            "2026-07-22T09:00:00.000Z", event,
        )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    rows = client.app.state.ctx.records.list_records()
    assert len(rows) == 1


def test_모르는_버전이_섞이면_파일을_건드리지_않는다(client, home):
    """한 줄만 모르는 버전이어도 파일 전체를 남긴다. 유실보다 대기가 낫다."""
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            '{"envelope_version": 99, "event_id": "evt_B", "kind": "start_work",'
            ' "enqueued_at": "2026-07-22T09:00:00.000Z", "payload": {}}\n'
        )
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 0
    assert target.exists()


def test_모르는_kind_는_바로_버리지_않고_재시도한다(client, home):
    """데몬 업그레이드 창에서는 재시도가 결과를 바꾼다 — 새 데몬이 뜨면 읽힌다.

    "재시도해도 결과가 달라질 수 없다" 는 처음 판단은 그 창을 빼먹은 것이었다.
    버전 게이트가 있는 kind 는 애초 여기 오지 않으므로, 이 분기는 게이트를
    거치지 않은(버전 1 그대로인) 새 kind 를 위한 안전망이다.
    """
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "그런_봉투는_없다", {"a": 1},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)

    assert list(paths.dead_letter_dir(home).glob("*.jsonl")) == []
    # absorbed/ 디렉터리가 spool/ 안에 살므로 파일만 센다.
    kept = [p for p in paths.spool_dir(home).glob("*") if p.is_file()]
    assert len(kept) == 1
    assert "그런_봉투는_없다" in kept[0].read_text(encoding="utf-8")


def test_모르는_kind_봉투는_결국_dead_letter_로_간다(client, home):
    """영영 모르는 kind 를 무한정 안고 있을 수도 없다. 실패 봉투와 같은 상한이다.

    예전에는 경고만 남기고 `continue` 해서 remaining 에도 dead 에도 들어가지
    않은 채 파일이 absorbed/ 로 옮겨졌다 — 조용히 사라졌다.
    """
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "그런_봉투는_없다", {"a": 1},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    for _ in range(absorb.MAX_ATTEMPTS):
        _age(home)
        absorb.absorb_all(client.app.state.ctx)

    dead = list(paths.dead_letter_dir(home).glob("*.jsonl"))
    assert len(dead) == 1
    assert "그런_봉투는_없다" in dead[0].read_text(encoding="utf-8")


def test_모르는_kind_가_있어도_아는_봉투는_반영된다(client, home):
    paths.ensure_layout(home)
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    spool.append(home, CLIENT, "그런_봉투는_없다", {},
                 "2026-07-22T09:00:01.000Z", "evt_B")
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1
    assert client.app.state.ctx.repo.get_checkpoint(CKP) is not None


def test_KINDS_와_HANDLERS_가_어긋나지_않는다():
    """spool.py 는 absorb 를 임포트하지 않으므로 여기서만 두 상수를 맞춰 본다.

    봉투 종류를 늘릴 때 한쪽만 고치면 그 봉투는 갈 곳이 없다.
    """
    assert spool.KINDS == set(absorb._HANDLERS)
