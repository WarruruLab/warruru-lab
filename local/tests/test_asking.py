"""주제 화면에서 묻는 경로 (명세 §2.6 · §3.7, 계획 Task 14).

**진짜 `codex` 를 부르지 않는다.** 네트워크와 구독 한도에 기대는 테스트는
아침마다 다르게 실패하고, 그런 테스트는 초록이어도 아무것도 증명하지 못한다.
대신 JSONL 을 뱉는 가짜 프로그램을 `program` 으로 주입해 **규약과 변환**만 본다.

실행 규약 넷은 관례가 아니라 여기서 못 박는다. 넷 중 하나만 어겨도
데몬이 통째로 매달리거나 답을 조용히 잃는다.
"""

from __future__ import annotations

import asyncio
import json
import stat
from pathlib import Path

from warruru_local.daemon import asking


def _fake(tmp_path: Path, body: str, *, name: str = "fake-cli") -> str:
    """인자를 무시하고 정해진 것을 뱉는 셸 스크립트."""
    path = tmp_path / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _run(ask: asking.Ask) -> list[tuple[str, dict]]:
    async def go():
        return [event async for event in asking.run(ask)]
    return asyncio.run(go())


STREAM = r"""
cat <<'EOF'
{"type":"thread.started","thread_id":"01a07175-d272-70b0-9ebc-80c5bc83af64"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"체이닝과 개방주소법."}}
{"type":"turn.completed","usage":{"input_tokens":19273,"output_tokens":41}}
EOF
"""


# ── 규약 1: stdin ────────────────────────────────────────────────

def test_stdin_을_닫지_않으면_매달린다_는_것을_규약으로_막는다(tmp_path):
    """CLI 는 stdin 이 열려 있으면 거기서도 입력을 읽으려고 기다린다.
    2026-09-05 에 이것으로 4분을 기다리다 끊었다.

    가짜는 stdin 을 통째로 읽고 나서야 답한다 — 데몬이 stdin 을 닫지
    않으면 이 테스트가 타임아웃으로 죽는다.
    """
    program = _fake(tmp_path, "cat > /dev/null\n" + STREAM.strip())
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert ("message", {"text": "체이닝과 개방주소법."}) in events


# ── 규약 2: stdout 만 ────────────────────────────────────────────

def test_stderr_가_섞여도_이벤트_파싱이_안_깨진다(tmp_path):
    """실제로 MCP OAuth 갱신 실패 로그가 JSONL 사이에 끼어들었다.
    한 줄 때문에 답 전체를 잃는 것이 이 경로의 가장 나쁜 결말이다.
    """
    program = _fake(tmp_path, (
        'echo "Reading additional input from stdin..." >&2\n'
        + STREAM.strip()
        + '\necho "2026-09-05T12:05:43Z ERROR codex_rmcp_client: refresh failed" >&2'
    ))
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    names = [name for name, _ in events]
    assert names == ["started", "message", "usage"]


def test_JSON_이_아닌_줄은_조용히_버린다(tmp_path):
    program = _fake(tmp_path, 'echo "그냥 로그"\n' + STREAM.strip())
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert [n for n, _ in events] == ["started", "message", "usage"]


# ── 규약 3: 권한 ─────────────────────────────────────────────────

def test_자식에게_쓰기_권한을_주지_않는다(tmp_path):
    """재료는 MCP 로 읽고 답은 데몬이 쓴다. 자식이 디스크에 손댈 이유가 없다."""
    argv = asking.Ask("db-index", "질문", tmp_path).argv()
    assert "-s" in argv and argv[argv.index("-s") + 1] == "read-only"
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


# ── 규약 4: 타임아웃 ─────────────────────────────────────────────

def test_답이_안_오면_죽이고_고치는_법을_말한다(tmp_path, monkeypatch):
    monkeypatch.setattr(asking, "TIMEOUT_SEC", 0.4)
    # `exec` 로 셸을 대체한다. 안 그러면 죽인 셸의 자식이 파이프를 붙들고
    # 있어서 `wait()` 가 그 자식이 끝날 때까지 안 돌아온다 — 테스트가 30초
    # 걸리던 이유가 그것이었고, 실전에서도 같은 모양으로 매달릴 수 있다.
    program = _fake(tmp_path, "exec sleep 5")
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert events[-1][0] == "error"
    assert "멈췄습니다" in events[-1][1]["message"]
    assert events[-1][1]["fix"]


# ── 스레드 ───────────────────────────────────────────────────────

def test_첫_이벤트에서_thread_id_를_잡는다(tmp_path):
    """이 값이 없으면 다음 질문이 앞의 대화를 못 잇는다."""
    program = _fake(tmp_path, STREAM.strip())
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert events[0] == ("started",
                         {"thread_id": "01a07175-d272-70b0-9ebc-80c5bc83af64"})


def test_두_번째_질문은_resume_으로_간다():
    first = asking.Ask("db-index", "질문", Path("/tmp")).argv()
    again = asking.Ask("db-index", "또", Path("/tmp"), thread_id="abc").argv()
    assert "resume" not in first
    assert again[again.index("resume") + 1] == "abc"


def test_C_와_s_는_resume_앞에_온다():
    """그 둘은 `exec` 의 인자이고 `resume` 하위 명령은 받지 않는다.
    뒤에 놓으면 이어 묻기만 `exit 2` 로 죽는다 — 첫 질문은 멀쩡해서
    순서 하나가 기능 절반을 조용히 앗아간다(2026-09-06 실측).
    """
    argv = asking.Ask("db-index", "또", Path("/tmp"), thread_id="abc").argv()
    resume = argv.index("resume")
    assert argv.index("-C") < resume
    assert argv.index("-s") < resume


def test_claude_로도_이어_물을_수_있다():
    argv = asking.Ask("db-index", "또", Path("/tmp"),
                      cli="claude", thread_id="abc").argv()
    assert "--resume" in argv and argv[argv.index("--resume") + 1] == "abc"


# ── 실패를 덮지 않는다 ───────────────────────────────────────────

def test_CLI_가_없으면_고치는_법을_화면이_말한다(tmp_path):
    """이 실패는 시간이 고쳐 주지 않는다. '잠시 후 다시' 로 덮지 않는다."""
    events = _run(asking.Ask("db-index", "질문", tmp_path, cli="없는명령어xyz"))
    assert len(events) == 1 and events[0][0] == "error"
    assert "없는명령어xyz" in events[0][1]["fix"]


def test_0_이_아닌_종료코드는_error_로_나간다(tmp_path):
    program = _fake(tmp_path, 'echo "무언가 잘못됨" >&2\nexit 3')
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert events[-1][0] == "error"
    assert "3" in events[-1][1]["message"]


def test_예외를_밖으로_던지지_않는다(tmp_path):
    """이 경로가 죽어도 기록·초안·발행은 안 흔들려야 한다."""
    events = _run(asking.Ask("db-index", "질문", tmp_path,
                             program=str(tmp_path / "없는파일")))
    assert events[0][0] == "error"


# ── 변환 ─────────────────────────────────────────────────────────

def test_CLI_의_이벤트_이름을_그대로_흘리지_않는다():
    """저쪽이 이름을 바꾸면 화면이 아니라 이 함수 하나가 깨져야 한다."""
    assert asking.translate('{"type":"thread.started","thread_id":"x"}') == \
        ("started", {"thread_id": "x"})
    assert asking.translate('{"type":"turn.started"}') is None
    assert asking.translate("아무 말") is None
    assert asking.translate("") is None


def test_생각하는_중간_항목은_답이_아니다():
    """`agent_message` 만 사람에게 보여 줄 말이다."""
    line = json.dumps({"type": "item.completed",
                       "item": {"type": "reasoning", "text": "음"}})
    assert asking.translate(line) is None


def test_아주_긴_답은_잘린다(tmp_path, monkeypatch):
    """브라우저를 멈추게 하는 답보다 잘린 답이 낫다."""
    monkeypatch.setattr(asking, "TEXT_MAX", 20)
    line = json.dumps({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "가" * 100}})
    program = _fake(tmp_path, f"cat <<'EOF'\n{line}\nEOF")
    events = _run(asking.Ask("db-index", "질문", tmp_path, program=program))
    assert len(events[0][1]["text"]) == 20


# ── Claude Code 는 이벤트 모양이 다르다 (2026-09-08 실측) ──────────

CLAUDE_STREAM = [
    {"type": "rate_limit_event", "session_id": "s1"},
    {"type": "system", "subtype": "init", "session_id": "d92a02cb-d270-4dd3-b7c9"},
    {"type": "assistant",
     "message": {"content": [{"type": "text", "text": "체이닝과 개방주소법."}]}},
    {"type": "result", "subtype": "success", "is_error": False,
     "usage": {"input_tokens": 2, "output_tokens": 3}},
]


def _claude_fake(tmp_path):
    body = "\n".join(json.dumps(line, ensure_ascii=False) for line in CLAUDE_STREAM)
    return _fake(tmp_path, f"cat <<'EOF'\n{body}\nEOF", name="fake-claude")


def test_claude_이벤트도_같은_이름으로_나온다(tmp_path):
    """화면은 어느 CLI 인지 몰라야 한다. 분기는 `translate` 한 곳에만 둔다."""
    program = _claude_fake(tmp_path)
    events = _run(asking.Ask("db-index", "질문", tmp_path,
                             cli="claude", program=program))
    assert [name for name, _ in events] == ["started", "message", "usage"]
    assert events[0][1]["thread_id"] == "d92a02cb-d270-4dd3-b7c9"
    assert events[1][1]["text"] == "체이닝과 개방주소법."
    assert events[2][1]["tokens"] == 5


def test_claude_의_생각_블록은_답이_아니다():
    """`text` 블록만 사람에게 보여 줄 말이다."""
    line = json.dumps({"type": "assistant",
                       "message": {"content": [{"type": "thinking", "thinking": "음"}]}})
    assert asking.translate(line) is None


def test_claude_실패는_error_로_나온다():
    line = json.dumps({"type": "result", "subtype": "error_during_execution",
                       "is_error": True, "result": "한도를 넘었습니다"})
    assert asking.translate(line) == ("error", {"message": "한도를 넘었습니다"})


def test_두_CLI_의_이벤트가_서로를_가리지_않는다():
    """이름이 겹치면 한쪽이 조용히 다른 쪽으로 읽힌다."""
    codex = json.dumps({"type": "thread.started", "thread_id": "c1"})
    claude = json.dumps({"type": "system", "subtype": "init", "session_id": "l1"})
    assert asking.translate(codex) == ("started", {"thread_id": "c1"})
    assert asking.translate(claude) == ("started", {"thread_id": "l1"})
