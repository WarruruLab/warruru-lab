# Warruru Local

여러 AI 에이전트가 MCP 로 남긴 개발 기록을 개인 머신에 유실 없이 저장하고,
날짜별로 되돌아보게 한다. WarruruLab 에서 실제로 도는 코드는 이것 하나다.

이번 MVP 의 명세 정본은 `docs/specs/2026-08-18-mvp-daily-loop.md` 다.
평가 기준은 `docs/acceptance.md`, 발행 경로 결정은 `docs/adr/2026-08-18-publish-target.md` 에 있다.
그 밖에 `docs/plans/` 의 구현 계획과 `docs/OUTSTANDING.md` 의 미해결 결함 목록을 함께 본다.

## 환경 — Task 0 은 끝났다 (2026-08-18)

이 머신에는 `local/.venv/`(Python 3.12.14)와 `~/.warruru/` 가 이미 있고,
**489개 테스트가 전원 통과한다.** 매번 다시 만들 필요 없다.

```bash
cd local && source .venv/bin/activate
python -m pytest -q           # 489 passed 여야 한다
warruru-daemon                # 필요할 때만. 어댑터가 알아서 띄운다
```

### 새 머신에서 처음 세팅할 때

시스템 python 은 macOS 기본 **3.9.6** 이라 그대로는 안 된다.
`pyproject.toml` 이 **>=3.11** 을 요구한다.

```bash
brew install python@3.12                      # 1. 3.12 를 쓴다 (아래 주의)
cd local
/opt/homebrew/bin/python3.12 -m venv .venv    # 2. venv
source .venv/bin/activate
pip install -e '.[dev]'                       # 3. 개발 의존성까지
python -m pytest -q                           # 4. 489 passed 확인
```

**3.13 이 아니라 3.12 인 이유** — 의존성이 여섯 개라 그중 하나라도
3.13 휠이 없으면 소스 빌드로 넘어간다. Docker 는 쓰지 않는다.
데몬이 `~/.warruru` 에 쓰고, 어댑터가 데몬을 자동 기동하고,
브라우저가 `127.0.0.1` 로 붙기 때문에 컨테이너 경계를 세 번 넘어야 한다.

**`mcp` 는 1.x 로 고정돼 있다.** 2.0.0 에서 `mcp.server.fastmcp` 경로가
사라져 테스트가 수집 단계부터 깨진다(2026-08-18 확인). 상한을 풀지 마라.

마지막으로 브라우저에서 <http://127.0.0.1:8787> 을 연다.
루트는 오늘 날짜 화면(`/d/{오늘}`)으로 302 리다이렉트된다. 이 화면이 뜨면 Task 0 완료다.

평소에는 데몬을 직접 띄울 필요가 없다. 에이전트의 MCP 설정에 아래를 넣으면
어댑터가 데몬이 꺼져 있을 때 알아서 기동한다.

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

## 구성

```text
Codex / Claude Code / Antigravity
        │  stdio (에이전트마다 1 프로세스)
        ▼
   warruru-mcp  ──HTTP──▶  warruru-daemon
                                  │
                                  ▼
                        ~/.warruru/warruru.db
                                  ▲
   브라우저  ─────────────────────┘
```

데몬이 SQLite 의 유일한 writer 다. 데몬에 닿지 못하면 어댑터가 기록을
`~/.warruru/spool/` 에 남기고, 데몬이 나중에 흡수한다. **성공 응답을 받은
기록은 어떤 경우에도 사라지지 않는다.**

`mcp/` 는 `daemon/` 을 한 번도 임포트하지 않는다. 이 경계는 깨면 안 된다.

## MCP 툴

전부 7개다. 넷은 작업의 흐름을, 셋은 글의 재료를 남긴다.

- `start_work` — 작업 세션을 연다
- `record_checkpoint` — 작업 도중의 판단·오류·결정을 한 건 남긴다
- `finish_work` — 작업 세션을 닫는다
- `get_today_context` — 오늘의 세션과 체크포인트를 돌려준다
- `record_learning` — 학습 기록 한 건. 필수는 `kind` · `topic` · `title` · `body` 넷이고
  `rationale` · `outcome` · `limitation` · `interview` 는 비어도 거절하지 않는다.
  응답의 `record_id` 를 다시 넘기면 **비어 있던 필드만** 채워진다
- `get_topic_records` — 한 주제(`topic_slug`)의 기록 묶음을 돌려준다. 초안을 다듬을 때 쓴다
- `save_draft` — 다듬은 마크다운으로 같은 draft 행을 덮어쓴다

일곱 툴 중 어느 것도 예외를 밖으로 던지지 않는다. 실패는 `ok: false` 봉투로 돌아온다 —
기록이 개발을 멈추게 하지 않기 위해서다.

## 화면

- `/` — 오늘 날짜 화면으로 리다이렉트
- `/d/{date}` — 그날의 작업·체크포인트·학습 기록
- `/d/{date}?deleted=1` — 삭제한 기록 (되살릴 것을 고르는 자리라 학습 기록은 안 나온다)
- `/t` — 오늘 기록을 주제로 묶은 목록. 건수 1건 이하는 '미분류' 로 모인다
- `/t/{slug}` — 한 주제의 전체 기록과 부족한 재료. [초안 만들기] 가 여기 있다
- `/drafts/{id}` — 6단 초안, 남은 TODO 수, 붙여넣기용 HTML, [발행함] 표시.
  `WARRURU_PUBLISH_REPO` 를 정하면 [비공개 저장소에 밀어 넣기] 가 함께 생긴다
- `/c/{YYYY-MM}` — 달력. 날짜 화면에 무언가 있는 날만 링크가 된다

전부 Jinja2 서버 렌더링이다. JS 는 초안 화면의 복사 버튼 하나뿐이고(인라인 8줄),
그 스크립트가 죽어도 textarea 전체 선택으로 대체된다.
조회는 토큰이 필요 없고, 상태를 바꾸는 폼만 토큰을 요구한다.

## 에이전트 기록 규칙

각 에이전트의 `AGENTS.md` 또는 규칙 파일에 넣는다. 기록을 남길지 말지는 100% 에이전트
재량이므로, 이 문단이 사실상 "중요한 것을 알아채는 장치"의 전부다.

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

`start_work` 를 빼먹어도 기록은 남는다. 자동으로 세션이 만들어지고 `INFERRED` 로 표시된다.

### record_learning 을 부르는 순간

체크포인트가 "작업이 어떻게 흘러갔는가"라면, 학습 기록은 "나중에 글로 설명할 수 있는가"다.
아래 넷 중 하나에 해당하면 그 자리에서 부른다. 나중에 몰아서 쓰지 않는다 — 그때는 이미
숫자와 이유를 잊는다.

- `EXPERIMENT` — 무언가를 바꿔보고 **측정값이 달라졌을 때**.
  바꾼 값과 전후 수치를 `title` 에 그대로 적는다(예: 풀 크기 10→30, p95 320ms→90ms).
- `TROUBLESHOOTING` — 원인을 몰랐다가 **알아냈을 때**. 증상이 아니라 원인을 적는다.
- `TECH_CHOICE` — 후보 둘 이상을 놓고 **하나를 골랐을 때**. 버린 쪽과 버린 이유를 함께 적는다.
- `CONCEPT` — 그때까지 잘못 알고 있던 것을 **바로잡았을 때**.

지킬 것:

- **지어내지 않는다.** `rationale` · `outcome` · `limitation` 이 비면 비운 채로 저장한다.
  빈 필드는 주제 화면에 '재료 부족' 으로 뜨고, 툴 응답이 그 필드를 채워 다시 부르는
  `example_call` 을 돌려준다. 모르는 것은 사용자에게 되묻고, 답을 받으면
  **같은 `record_id` 로** 다시 부른다. 새 id 로 부르면 거의 같은 기록이 하나 더 생긴다.
- **`topic` 은 여러 기록에 걸쳐 같은 말을 쓴다.** 집계와 글 한 편의 단위가 topic 이다.
  응답에 오는 유사 슬러그 힌트('connection-pool 과 유사합니다')를 보면 그쪽을 따른다.
- **기록 실패로 작업을 멈추지 않는다.** 데몬이 꺼져 있어도 봉투는 spool 에 떨어진다.

## 저장 위치

```text
~/.warruru/
├── warruru.db          기록
├── config/             machine.json, daemon.json(토큰)
├── spool/              데몬에 못 넘긴 기록. absorbed/ 로 옮겨진다
├── drafts/             YYYY/MM/ 아래 초안 마크다운. **저장소 바깥이다**
├── logs/               daemon.log, mcp.log
└── run/                daemon.lock
```

`WARRURU_HOME` 으로 위치를 통째로 바꿀 수 있다. 전체 목록은
`src/warruru_local/config.py` 의 `load_settings()` 가 정본이고, 지금은 18개다.

```text
WARRURU_HOME  TOKEN  TOOL  DAEMON_HOST  DAEMON_PORT  LOG_LEVEL
WARRURU_ATTACH_WINDOW_MINUTES   IDLE_TIMEOUT_HOURS
WARRURU_SWEEP_INTERVAL_SECONDS  SPOOL_QUIET_SECONDS
WARRURU_HTTP_TIMEOUT_SECONDS    AUTOSTART_DAEMON
WARRURU_GIT_TIMEOUT_SECONDS     GIT_CACHE_TTL_SECONDS
WARRURU_GIT_DIRTY_FILE_CAP      DRAFTS_ROOT  REPO_ROOT
WARRURU_PUBLISH_REPO
```

(전부 `WARRURU_` 접두사를 공유한다. 우선순위는
환경변수 > `config/daemon.json` > 기본값.)

초안이 저장소가 아니라 여기 앉는 이유는 취향이 아니다. warruru-lab 저장소는 public 이고,
미완성 사고 과정이 `git add -A` 한 번에 인터넷에 올라가는 것을 막아야 한다.
저장소 안 경로가 인자로 들어오면 쓰기 어댑터가 예외를 던진다.

## 개발

```bash
python -m pytest -q          # 전체
python -m pytest tests/test_session_attach.py -v
```

시각과 식별자 생성은 주입할 수 있다. 귀속 규칙과 자동 마감을 검증할 때 실제 대기를 쓰지 않는다.
날짜 경계는 반드시 `clock.local_day_bounds` 만 쓴다.

**모든 커밋의 머지 조건은 기존 테스트 24파일 전원 통과다.**

## 두 머신 점검 (수동) — **MVP 이후로 미룸**

크로스 플랫폼은 `AGENTS.md` §2 에서 'MVP 이후' 로 내려갔다.
지금 Windows 머신이 범위에 없으므로 이 절은 **실행하지 않는다.**
서버·동기화 축을 되살릴 때 다시 꺼낸다. 그때 확인할 것:

- [ ] `pip install -e '.[dev]'` 가 끝난다
- [ ] 에이전트에서 `start_work` → `record_checkpoint` → `finish_work` 가 동작한다
- [ ] <http://127.0.0.1:8787/> 에 그 기록이 보인다
- [ ] `~/.warruru/config/machine.json` 의 `machine_id` 가 두 머신에서 서로 다르다
- [ ] 데몬을 강제 종료한 뒤 기록해도 툴이 성공을 반환하고, 데몬을 다시 띄우면 반영된다
- [ ] 에이전트를 종료하면 진행 중 세션이 `AUTO_CLOSED` / `CLIENT_EXIT` 이 된다

## 하지 않는 일

Git Diff·Patch·핵심 Symbol 추출, 오류/테스트 로그 수집, 서버 전송, 데몬 안의 LLM 호출은
하지 않는다. 초안은 LLM 없이 결정적으로 조립하고, 문장을 다듬는 것은 사용자 앞에 이미
떠 있는 에이전트의 몫이다.
