"""`learning.record` — 기록 한 건이 세션에 붙고 git 을 달고 저장된다.

`recording.record_checkpoint()` 와 같은 순서로 흐른다. 온라인 경로와 spool 흡수가
같은 함수를 부르므로, **검증은 이 함수 안에 두지 않는다.**
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import limits, topics
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import learning
from warruru_local.daemon.app import create_app

START = datetime(2026, 8, 18, 9, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def ctx(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        yield made.app.state.ctx


def _payload(**extra):
    values = {
        "record_id": "rec_A",
        "kind": "EXPERIMENT",
        "topic": "connection pool",
        "title": "풀 크기 10→30",
        "body": "p95 320ms→90ms",
        **COMMON,
    }
    values.update(extra)
    return values


def test_work_id_없이_와도_세션이_자동으로_붙는다(ctx):
    """호출자는 세션 id 를 몰라도 된다. 체크포인트와 같은 규칙이다."""
    result = learning.record(ctx, _payload())
    assert result["work_id"].startswith("wrk_")
    assert result["attached_by"]


def test_기록이_저장되고_원문_topic_이_남는다(ctx):
    learning.record(ctx, _payload(topic="  Connection Pool  "))
    row = ctx.records.get_record("rec_A")
    assert row["topic"] == "Connection Pool"     # strip 은 한다
    assert row["topic_slug"] == "connection-pool"


def test_git_스냅샷이_채워진다(ctx, tmp_path):
    result = learning.record(ctx, _payload(repo_path=str(tmp_path)))
    assert "git" in result


def test_project_는_repo_name_으로_고정된다(ctx, monkeypatch):
    """저장소 이름이 나중에 바뀌어도 과거 기록의 소속은 흔들리지 않는다."""
    class _Snap:
        repo_path = "/tmp/산책온"
        repo_name = "산책온"
        branch = "main"
        commit_sha = "abc1234"
        dirty = False
        dirty_file_count = 0
        dirty_count_capped = False

        def as_dict(self):
            return {"repo_name": self.repo_name}

    monkeypatch.setattr(ctx.git, "collect", lambda path: _Snap())
    learning.record(ctx, _payload())
    assert ctx.records.get_record("rec_A")["project"] == "산책온"


def test_저장소_밖이면_project_는_None_이다(ctx):
    learning.record(ctx, _payload())
    assert ctx.records.get_record("rec_A")["project"] is None


def test_body_가_상한을_넘으면_자르고_표시한다(ctx):
    learning.record(ctx, _payload(body="가" * (limits.BODY_MAX + 10)))
    row = ctx.records.get_record("rec_A")
    assert len(row["body"]) == limits.BODY_MAX
    assert row["body_truncated"] == 1


def test_topic_slug_는_topic_을_자른_뒤에_만든다(ctx):
    """순서를 바꾸면 같은 원문이 상한 근처에서 두 슬러그로 갈린다."""
    long_topic = "가" * (limits.TITLE_MAX + 50)
    learning.record(ctx, _payload(topic=long_topic))
    row = ctx.records.get_record("rec_A")
    assert row["topic_slug"] == topics.slugify(row["topic"])


def test_occurred_at_이_이상하면_현재_시각으로_대체한다(ctx):
    """잘못된 시각 하나가 날짜 화면을 영구히 500 으로 만드는 결함이 있었다(I2)."""
    learning.record(ctx, _payload(occurred_at="어제쯤"))
    assert ctx.records.get_record("rec_A")["occurred_at"] == "2026-08-18T09:00:00.000Z"


def test_occurred_at_을_주면_그대로_쓴다(ctx):
    learning.record(ctx, _payload(occurred_at="2026-08-17T01:02:03.000Z"))
    assert ctx.records.get_record("rec_A")["occurred_at"] == "2026-08-17T01:02:03.000Z"


def test_touch_work_가_불린다(ctx, monkeypatch):
    called = []
    monkeypatch.setattr(ctx.repo, "touch_work",
                        lambda *args, **kwargs: called.append(args))
    learning.record(ctx, _payload())
    assert called


def test_같은_기록을_두_번_보내도_한_건이다(ctx):
    learning.record(ctx, _payload())
    result = learning.record(ctx, _payload(title="나중"))
    assert result["duplicate"] is True
    assert len(ctx.records.list_records()) == 1


def test_중복이면_touch_work_를_다시_부르지_않는다(ctx, monkeypatch):
    learning.record(ctx, _payload())
    called = []
    monkeypatch.setattr(ctx.repo, "touch_work",
                        lambda *args, **kwargs: called.append(args))
    learning.record(ctx, _payload())
    assert called == []


def test_learning_record_는_필수_필드를_검증하지_않는다(ctx):
    """검증은 입구(MCP·API)에만 있다. 흡수 경로가 이 함수를 부르기 때문이다.

    안쪽에 두면 이미 입구를 통과해 spool 에 들어간 기록이 흡수 때 다시 걸린다.
    """
    result = learning.record(ctx, _payload(title="   ", body="   "))
    assert ctx.records.get_record("rec_A") is not None
    assert result["record_id"] == "rec_A"


def test_결손_필드와_예시가_응답에_실린다(ctx):
    result = learning.record(ctx, _payload())
    assert "outcome" in result["missing_fields"]
    assert "record_learning(" in result["example_call"]


def test_유사_슬러그가_응답에_실린다(ctx):
    result = learning.record(ctx, _payload(topic="jpa n plus"))
    assert "jpa-n-plus-one" in result["similar_slugs"]


def test_흡수_경로는_source_가_SPOOL_이다(ctx):
    learning.record(ctx, _payload(), source="SPOOL")
    assert ctx.records.get_record("rec_A")["source"] == "SPOOL"


def test_예시는_저장된_값을_되돌려_준다(ctx):
    """원본을 되돌려 주면 방금 정리한 것을 다시 되돌리는 호출이 나간다."""
    result = learning.record(ctx, _payload(topic="  Connection Pool  "))
    assert '"Connection Pool"' in result["example_call"]
    assert '"  Connection Pool  "' not in result["example_call"]


def test_같은_기록을_다시_보내면_빈칸만_채운다(ctx):
    learning.record(ctx, _payload())
    result = learning.record(ctx, _payload(outcome="p95 가 90ms 로"))
    assert result["duplicate"] is True
    assert result["filled_fields"] == ["outcome"]
    assert ctx.records.get_record("rec_A")["outcome"] == "p95 가 90ms 로"


def test_보강해도_이미_있는_값은_그대로다(ctx):
    learning.record(ctx, _payload(outcome="처음"))
    learning.record(ctx, _payload(outcome="나중", title="바뀐 제목"))
    row = ctx.records.get_record("rec_A")
    assert row["outcome"] == "처음"
    assert row["title"] == "풀 크기 10→30"


def test_보강하면_결손_목록이_줄어든다(ctx):
    first = learning.record(ctx, _payload())
    second = learning.record(ctx, _payload(outcome="결과", limitation="한계"))
    assert set(first["missing_fields"]) - set(second["missing_fields"]) == {
        "outcome", "limitation"
    }


def test_kind_는_대문자로_저장된다(ctx):
    """slug_summary 가 kind 로 집계한다. 갈리면 화면의 건수가 쪼개진다."""
    learning.record(ctx, _payload(kind="Experiment"))
    assert ctx.records.get_record("rec_A")["kind"] == "EXPERIMENT"


def test_소수점_자릿수가_달라도_사전순이_시간순과_같다(ctx):
    """`%f` 는 1~6자리를 다 받는다. 그대로 저장하면 정렬이 뒤집힌다."""
    learning.record(ctx, _payload(record_id="rec_A",
                                  occurred_at="2026-08-18T09:00:00.1Z"))
    learning.record(ctx, _payload(record_id="rec_B",
                                  occurred_at="2026-08-18T09:00:00.150Z"))
    ids = [r["record_id"] for r in ctx.records.list_records()]
    assert ids == ["rec_B", "rec_A"]


# ── 리뷰 반영 (2026-08-24) ─────────────────────────────────────────

def test_중복이면_세션을_새로_붙이지_않는다(ctx, monkeypatch):
    """봉투 재생(daemon 크래시 후 재시도, 보강 호출)은 설계된 일상이다.
    attach 를 멱등 확인보다 먼저 부르면 재생마다 빈 INFERRED 작업이 생겨
    날짜 화면에 유령 작업이 쌓인다.
    """
    learning.record(ctx, _payload())
    boom = lambda **kwargs: (_ for _ in ()).throw(AssertionError("attach 불림"))
    monkeypatch.setattr(ctx.sessions, "attach", boom)
    result = learning.record(ctx, _payload(outcome="보강"))
    assert result["duplicate"] is True
    assert result["filled_fields"] == ["outcome"]


def test_비어_있던_topic_은_보강으로_채울_수_있다(ctx):
    """topic 이 빈 기록은 misc 로 좌초한다. 힌트가 topic 을 채우라고
    말하는데 채울 수 없으면 그 힌트는 영원히 도는 헛바퀴다.
    """
    learning.record(ctx, _payload(topic=""))
    assert ctx.records.get_record("rec_A")["topic_slug"] == "misc"

    result = learning.record(ctx, _payload(topic="connection pool"))
    assert "topic" in result["filled_fields"]
    row = ctx.records.get_record("rec_A")
    assert row["topic"] == "connection pool"
    assert row["topic_slug"] == "connection-pool"


def test_이미_있는_topic_은_보강으로_바뀌지_않는다(ctx):
    """topic 을 바꾸면 슬러그가 갈라져 기록이 다른 주제로 이사한다."""
    learning.record(ctx, _payload(topic="connection pool"))
    learning.record(ctx, _payload(topic="jvm gc"))
    assert ctx.records.get_record("rec_A")["topic_slug"] == "connection-pool"


def test_예시_재호출에_record_id_가_들어_있다(ctx):
    result = learning.record(ctx, _payload())
    assert 'record_id="rec_A"' in result["example_call"]
