"""주제 화면에서 물으면 구독 CLI 를 자식 프로세스로 띄운다 (명세 §2.6 · §3.7).

**데몬은 모델을 모른다.** 모델 이름 · 프롬프트 조립 · 재시도 · 인증 · 토큰
갱신은 전부 CLI 안에 있고 이 파일에 들어오지 않는다. 여기가 하는 일은 셋이다 —
자식을 규약대로 띄우고, 표준출력의 JSONL 을 화면이 아는 이벤트로 옮기고,
`thread_id` 를 붙잡아 다음 질문이 이어지게 한다.

**초안 조립기는 이 파일을 모른다.** 6단 조립은 여전히 결정적이고 LLM 호출이
0 이다 — 그것이 원래 지키려던 경계다(명세 §2.4).

실행 규약 넷은 관례가 아니라 코드다. 각각에 테스트 이름이 하나씩 붙는다.

1. `stdin` 을 닫는다. 열어 두면 CLI 가 `Reading additional input from stdin...`
   에서 **영원히 멈춘다**(2026-09-05 실측, 4분을 기다리다 끊었다).
2. `stdout` 만 파싱한다. `stderr` 에는 JSONL 이 아닌 로그가 섞여 나온다.
3. `-s read-only`. 재료는 MCP 로 읽고 답은 데몬이 쓴다. 자식에게 쓰기 권한을
   줄 이유가 없다.
4. 타임아웃. 넘으면 죽이고 `error` 를 낸다.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# 한 번의 물음에 이만큼까지 기다린다. 실측으로 초안 다듬기가 54초였고,
# 그보다 훨씬 무거운 질문도 있으므로 넉넉히 잡되 무한은 아니다.
TIMEOUT_SEC = 300

# 화면에 흘릴 답의 상한. 넘으면 자른다 — 브라우저를 멈추게 하는 답보다
# 잘린 답이 낫고, 잘렸다는 사실은 화면이 말한다.
TEXT_MAX = 40_000


@dataclass(frozen=True)
class Ask:
    """한 번의 물음. **CLI 이름과 실행 파일을 인자로 받는다.**

    테스트가 진짜 `codex` 를 부르지 않기 위해서다. 네트워크와 구독 한도에
    기대는 테스트는 아침마다 다르게 실패한다.
    """

    topic_slug: str
    prompt: str
    home: Path
    cli: str = "codex"
    program: str | None = None      # 없으면 PATH 에서 `cli` 를 찾는다
    thread_id: str | None = None    # 있으면 이어 묻는다

    def argv(self) -> list[str]:
        exe = self.program or self.cli
        if self.cli == "claude":
            # `--verbose` 가 있어야 `-p` 에서 stream-json 이 줄 단위로 나온다.
            # **도구 권한을 주지 않는다** — 답만 받고 파일은 데몬이 쓴다.
            head = [exe, "-p", "--output-format", "stream-json", "--verbose"]
            if self.thread_id:
                head += ["--resume", self.thread_id]
            return head + [self.prompt]
        # **`-C` 와 `-s` 는 `resume` 앞에 와야 한다.** 그 둘은 `exec` 의
        # 것이고 `resume` 하위 명령은 받지 않는다 — 뒤에 놓으면 이어 묻기가
        # 통째로 `exit 2` 로 죽는다(2026-09-06 실측). 첫 질문은 멀쩡하고
        # 두 번째부터만 죽어서, 순서 하나가 조용히 기능 절반을 앗아간다.
        head = [exe, "exec", "-C", str(self.home), "-s", "read-only"]
        if self.thread_id:
            head += ["resume", self.thread_id]
        return head + ["--json", "--skip-git-repo-check", self.prompt]


def translate(line: str) -> tuple[str, dict] | None:
    """CLI 의 JSONL 한 줄을 화면이 아는 이벤트로 옮긴다.

    **CLI 의 이름을 그대로 흘리지 않는다.** 저쪽이 `thread.started` 를
    `session.started` 로 바꾸면 화면이 아니라 이 함수 하나가 깨져야 한다.

    JSON 이 아닌 줄은 `None` 이다 — `stderr` 가 섞여 들어와도 여기서 조용히
    걸러진다. 파싱 실패로 답 전체를 잃는 것이 이 경로의 가장 나쁜 결말이다.
    """
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None

    kind = event.get("type")

    # ── Claude Code (`--output-format stream-json`) ──────────────
    # **Codex 와 이벤트 이름도 모양도 겹치지 않는다**(2026-09-08 실측).
    # 저쪽은 `thread.started` / `item.completed`, 이쪽은
    # `system.init` / `assistant` / `result` 다. 한 함수가 둘 다 받되
    # 분기는 여기 한 곳에만 둔다 — 화면은 어느 CLI 인지 몰라야 한다.
    if kind == "system" and event.get("subtype") == "init":
        thread = event.get("session_id")
        return ("started", {"thread_id": thread}) if thread else None

    if kind == "assistant":
        blocks = (event.get("message") or {}).get("content") or []
        text = "".join(
            str(b.get("text") or "") for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        return ("message", {"text": text}) if text.strip() else None

    if kind == "result":
        if event.get("is_error"):
            return "error", {"message": str(event.get("result") or "실패")[:400]}
        usage = event.get("usage") or {}
        total = 0
        for key in ("input_tokens", "output_tokens"):
            try:
                total += int(usage.get(key) or 0)
            except (TypeError, ValueError):
                pass
        return "usage", {"tokens": total}

    # ── Codex (`--json`) ─────────────────────────────────────────
    if kind in ("thread.started", "session.started"):
        thread = event.get("thread_id") or event.get("session_id")
        return ("started", {"thread_id": thread}) if thread else None

    if kind == "item.completed":
        item = event.get("item") or {}
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = str(item.get("text") or "")
            if text:
                return "message", {"text": text}
        return None

    if kind == "turn.completed":
        usage = event.get("usage") or {}
        total = 0
        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens"):
                try:
                    total += int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    pass
        return "usage", {"tokens": total}

    if kind in ("turn.failed", "error"):
        message = event.get("message") or event.get("error") or "알 수 없는 실패"
        return "error", {"message": str(message)[:400]}

    return None


def missing_cli(ask: Ask) -> dict | None:
    """CLI 가 없으면 **고치는 법과 함께** 알린다.

    "잠시 후 다시 시도" 로 덮지 않는다. 이 실패는 시간이 고쳐 주지 않는다.
    """
    if ask.program:
        return None
    if shutil.which(ask.cli):
        return None
    return {
        "message": f"`{ask.cli}` 를 찾을 수 없습니다.",
        "fix": f"터미널에서 `{ask.cli}` 가 도는지 먼저 확인하세요.",
    }


async def run(ask: Ask):
    """자식을 띄우고 이벤트를 하나씩 내보낸다.

    예외를 밖으로 던지지 않는다 — 실패도 `error` 이벤트로 나간다.
    이 경로가 죽어도 기록·초안·발행은 안 흔들려야 하고, 그러려면 화면
    쪽에서 붙잡을 것이 예외가 아니라 이벤트여야 한다.
    """
    gone = missing_cli(ask)
    if gone:
        yield "error", gone
        return

    try:
        proc = await asyncio.create_subprocess_exec(
            *ask.argv(),
            stdin=asyncio.subprocess.DEVNULL,   # 규약 1
            stdout=asyncio.subprocess.PIPE,     # 규약 2 — stderr 는 섞지 않는다
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, ValueError) as exc:
        yield "error", {"message": f"실행하지 못했습니다: {exc}",
                        "fix": f"`{ask.cli}` 설치와 실행 권한을 확인하세요."}
        return

    sent = 0
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=TIMEOUT_SEC
                )
            except asyncio.TimeoutError:
                proc.kill()
                yield "error", {
                    "message": f"{TIMEOUT_SEC}초 안에 답이 오지 않아 멈췄습니다.",
                    "fix": "질문을 줄여 다시 물어보세요.",
                }
                return
            if not raw:
                break
            made = translate(raw.decode("utf-8", errors="replace"))
            if made is None:
                continue
            name, data = made
            if name == "message":
                room = TEXT_MAX - sent
                if room <= 0:
                    continue
                data = {"text": data["text"][:room]}
                sent += len(data["text"])
            yield name, data
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()

    if proc.returncode not in (0, None):
        tail = (await proc.stderr.read()).decode("utf-8", errors="replace")
        yield "error", {
            "message": f"`{ask.cli}` 가 {proc.returncode} 로 끝났습니다.",
            "fix": tail.strip().splitlines()[-1][:200] if tail.strip() else "",
        }
