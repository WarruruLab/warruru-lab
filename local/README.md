# Warruru Local

여러 AI 에이전트가 MCP 로 남긴 개발 기록을 개인 머신에 유실 없이 저장하고, 날짜별로 되돌아보게 한다.

WarruruLab 의 네 번째 축이며, 유일하게 서버가 아닌 사용자의 머신에서 돈다.
명세서는 통합 docs 의 `docs/local/specs/` 에 있다.

## 구성

```text
Codex / Claude Code / Antigravity
        │  stdio (에이전트마다 1 프로세스)
        ▼
   warruru-mcp  ──HTTP──▶  warruru-daemon  ──▶  ~/.warruru/warruru.db
                                  │
   브라우저  ─────────────────────┘  (날짜별 화면)
```

데몬이 SQLite 의 유일한 writer 다. 데몬에 닿지 못하면 어댑터가 기록을
`~/.warruru/spool/` 에 남기고, 데몬이 나중에 흡수한다. **성공 응답을 받은
기록은 어떤 경우에도 사라지지 않는다.**

## 설치

```bash
cd local
python -m pip install -e .
```

에이전트의 MCP 설정에 다음 한 줄을 넣는다. 데몬은 필요할 때 어댑터가 알아서 띄운다.

```json
{
  "mcpServers": {
    "warruru": {
      "command": "warruru-mcp",
      "env": { "WARRURU_TOOL": "codex" }
    }
  }
}
```

`WARRURU_TOOL` 은 화면에서 기록을 도구별로 나눌 때 쓰는 이름이다.
에이전트마다 다르게 준다: `codex`, `claude-code`, `antigravity`.

화면은 <http://127.0.0.1:8787/> 에서 연다.

## 에이전트 기록 규칙

각 에이전트의 `AGENTS.md` 또는 규칙 파일에 넣는다.

```md
작업을 시작할 때 start_work 를 호출한다.

다음 상황에서 record_checkpoint 를 호출한다.

- 기존 접근 방법을 포기하거나 변경했을 때
- 중요한 오류가 발생했을 때
- 오류의 원인을 확인했을 때
- 중요한 구현 방식이나 아키텍처를 결정했을 때
- 테스트 결과가 작업 방향을 바꿨을 때
- 의미 있는 기능이 완료됐을 때
- 남은 한계가 확인됐을 때

작업이 끝나면 finish_work 를 호출한다.

단순 오타 수정, 포맷팅, 파일 탐색, 반복 테스트, 임시 디버깅 코드는 기록하지 않는다.
```

`start_work` 를 빼먹어도 기록은 남는다. 자동으로 세션이 만들어지고
`INFERRED` 로 표시된다.

## 저장 위치

```text
~/.warruru/
├── warruru.db          기록
├── config/             machine.json, daemon.json(토큰)
├── spool/              데몬에 못 넘긴 기록. absorbed/ 로 옮겨진다
├── logs/                daemon.log, mcp.log
└── run/                 daemon.lock
```

`WARRURU_HOME` 으로 위치를 바꿀 수 있다. 설정 목록은 명세서 IF-7 에 있다.

## 개발

```bash
python -m pytest -q          # 전체
python -m pytest tests/test_session_attach.py -v
```

시각과 식별자 생성은 주입할 수 있다. 귀속 규칙과 자동 마감을 검증할 때
실제 대기를 쓰지 않는다.

## 두 머신 점검 (AC-10, 수동)

자동화할 수 없어 손으로 확인한다. Windows 와 macOS 각각에서:

- [ ] `python -m pip install -e .` 가 끝난다
- [ ] 에이전트에서 `start_work` → `record_checkpoint` → `finish_work` 가 동작한다
- [ ] <http://127.0.0.1:8787/> 에 그 기록이 보인다
- [ ] `~/.warruru/config/machine.json` 의 `machine_id` 가 두 머신에서 서로 다르다
- [ ] 데몬을 강제 종료한 뒤 기록해도 툴이 성공을 반환하고, 데몬을 다시 띄우면 반영된다
- [ ] 에이전트를 종료하면 진행 중 세션이 `AUTO_CLOSED` / `CLIENT_EXIT` 이 된다

## 하지 않는 일

Git Diff·Patch·핵심 Symbol 추출, 오류/테스트 로그 수집, 서버 전송,
LLM 요약, 블로그 초안 생성은 전부 후속 단계다. 이 축은 기록만 한다.
