from datetime import datetime, timezone

import httpx
import pytest

from warruru_local import spool
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.mcp.client import DaemonClient

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


class FakeTransport:
    """응답 또는 예외를 순서대로 돌려준다."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append((method, url, json, params, headers, timeout))
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcomes_default()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def outcomes_default(self):
        return httpx.Response(200, json={"ok": True})


def _client(home, transport, spawned=None, logger=None):
    import logging

    settings = load_settings(home)
    return DaemonClient(
        settings,
        CLIENT,
        logger or logging.getLogger("test"),
        FixedClock(START),
        transport=transport,
        spawner=(spawned if spawned is not None else (lambda: False)),
    )


def test_정상이면_데몬_저장이다(home):
    transport = FakeTransport(httpx.Response(200, json={"work_id": "wrk_A"}))
    outcome = _client(home, transport).send("start_work", "/v1/works", {"a": 1})
    assert outcome.storage == "DAEMON"
    assert outcome.body["work_id"] == "wrk_A"


def test_토큰_헤더와_주소와_시간초과를_제대로_보낸다(home):
    transport = FakeTransport(httpx.Response(200, json={}))
    settings = load_settings(home)
    _client(home, transport).send("start_work", "/v1/works", {"a": 1})

    method, url, body, _, headers, timeout = transport.calls[0]
    assert method == "POST"
    assert url == f"http://{settings.host}:{settings.port}/v1/works"
    assert body == {"a": 1}
    assert headers["X-Warruru-Token"] == settings.token
    assert timeout == settings.http_timeout_seconds


def test_연결_실패면_기동을_시도하고_재시도한다(home):
    transport = FakeTransport(
        httpx.ConnectError("연결 불가"), httpx.Response(200, json={"ok": True})
    )
    spawned = []
    outcome = _client(
        home, transport, spawned=lambda: (spawned.append(1), True)[1]
    ).send("start_work", "/v1/works", {})
    assert spawned == [1]
    assert outcome.storage == "DAEMON"


def test_재시도도_실패하면_spool_에_남긴다(home):
    transport = FakeTransport(
        httpx.ConnectError("연결 불가"), httpx.ConnectError("연결 불가")
    )
    outcome = _client(home, transport).send("start_work", "/v1/works", {"a": 1})
    assert outcome.storage == "SPOOL"
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert envelopes[0]["kind"] == "start_work"
    assert envelopes[0]["payload"] == {"a": 1}


def test_시간_초과도_spool_로_간다(home):
    transport = FakeTransport(
        httpx.ReadTimeout("느림"), httpx.ReadTimeout("느림")
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "SPOOL"


def test_500_이면_spool_로_간다(home):
    transport = FakeTransport(
        httpx.Response(500, json={"error": {"code": "STORAGE_ERROR"}})
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "SPOOL"


def test_400_이면_spool_하지_않는다(home):
    transport = FakeTransport(
        httpx.Response(400, json={"error": {"code": "INVALID_REQUEST",
                                            "message": "type 은 필수입니다"}})
    )
    outcome = _client(home, transport).send("s", "/v1/works", {})
    assert outcome.storage == "DAEMON"
    assert outcome.body is None
    assert "type 은 필수입니다" in outcome.message
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []


def test_401_이면_spool_하지_않는다(home):
    transport = FakeTransport(
        httpx.Response(401, json={"error": {"code": "INVALID_TOKEN",
                                            "message": "토큰 오류"}})
    )
    outcome = _client(home, transport).send("s", "/v1/works", {})
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []
    assert outcome.storage == "DAEMON"


def test_503_이면_한_번_재시도한다(home):
    transport = FakeTransport(
        httpx.Response(503, json={"error": {"code": "NOT_READY"}}),
        httpx.Response(200, json={"ok": True}),
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "DAEMON"


def test_조회는_실패해도_spool_하지_않는다(home):
    transport = FakeTransport(httpx.ConnectError("연결 불가"),
                              httpx.ConnectError("연결 불가"))
    outcome = _client(home, transport).query("/v1/context", {"date": "2026-07-22"})
    assert outcome.storage == "NONE"
    assert outcome.body is None
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []


def test_기동은_한_번만_시도한다(home):
    transport = FakeTransport(
        httpx.ConnectError("x"), httpx.ConnectError("x"),
        httpx.ConnectError("x"), httpx.ConnectError("x"),
    )
    spawned = []
    made = _client(home, transport, spawned=lambda: (spawned.append(1), True)[1])
    made.send("s", "/v1/works", {})
    made.send("s", "/v1/works", {})
    assert len(spawned) == 1


def test_닫기는_client_closed_봉투를_남긴다(home):
    transport = FakeTransport(httpx.ConnectError("x"), httpx.ConnectError("x"))
    _client(home, transport).close()
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert envelopes[0]["kind"] == "client_closed"


def test_404_는_spool_로_떨어진다(home):
    """구버전 데몬이 새 라우트를 모르면 404 다. 이건 요청 내용 문제가 아니다.

    SingleInstanceLock 때문에 구버전 데몬이 떠 있으면 새 데몬을 띄우지도 못하므로,
    여기서 버리면 새 기록만 조용히 사라진다(OUTSTANDING K2).
    """
    transport = FakeTransport(httpx.Response(404))
    outcome = _client(home, transport).send(
        spool.KIND_LEARNING_RECORD, "/v1/records", {"a": 1}
    )
    assert outcome.storage == "SPOOL"
    assert len(spool.read_envelopes(spool.spool_path(home, CLIENT))) == 1


def test_422_는_spool_하지_않는다(home):
    """검증 실패는 다시 보내도 같은 답이 온다. 쌓아둘 이유가 없다."""
    transport = FakeTransport(
        httpx.Response(422, json={"error": {"code": "INVALID_REQUEST",
                                            "message": "topic 은 필수입니다"}})
    )
    outcome = _client(home, transport).send("s", "/v1/records", {})
    assert outcome.storage == "DAEMON"
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []


def test_spool_제외_목록은_400_401_422_뿐이다():
    from warruru_local.mcp.client import _NO_SPOOL_STATUSES

    assert _NO_SPOOL_STATUSES == {400, 401, 422}

