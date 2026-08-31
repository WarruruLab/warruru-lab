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

`WARRURU_TOOL` 은 **적지 않아도 된다.** 어댑터가 MCP 핸드셰이크의
`clientInfo` 로 어느 에이전트가 붙었는지 알아낸다(`codex` · `claude-code` ·
처음 보는 이름이면 그 이름 그대로). 적으면 그 값이 이긴다 — 추론을 덮고
싶을 때만 쓴다.

## 어느 저장소에서든 쓰기 — 에이전트 플러그인

위 설정을 저장소마다 넣는 대신 `agent-plugin/` 을 한 번 설치하면 끝난다.
MCP 연결과 기록 규칙(스킬)이 함께 들어가므로 **다른 프로젝트를 열어도
`AGENTS.md` 를 손대지 않고** 그대로 쓴다.
**매니페스트 한 벌을 Codex 와 Claude Code 가 같이 읽는다.**

먼저 어댑터를 PATH 에 올린다. venv 안에만 있으면 다른 경로에서 안 잡힌다.

```bash
ln -sf "$PWD/local/.venv/bin/warruru-mcp" ~/.local/bin/warruru-mcp
```

그다음 이 저장소를 로컬 마켓플레이스로 걸고 설치한다.

```bash
codex plugin marketplace add ./agent-plugin
codex plugin add warruru@warruru-local

claude plugin marketplace add ./agent-plugin
claude plugin install warruru@warruru-local
```

확인:

- Codex — `codex mcp list` 에 `warruru`(command 가 `warruru-mcp`),
  `codex debug prompt-input` 에 `warruru:warruru-recording`.
- Claude Code — `claude plugin details warruru@warruru-local` 의 부품 목록에
  Skills 1 · MCP servers 1.

둘 다 모델을 부르지 않는다.

**직접 넣어 둔 MCP 등록이 있으면 지운다.** 플러그인이 같은 이름으로 서버를
등록하므로 두 벌이 된다 — `~/.codex/config.toml` 의 `[mcp_servers.warruru]`,
Claude Code 는 `claude mcp remove warruru -s user`.

플러그인 파일을 고친 뒤에는 캐시로 복사된 사본이 낡는다.
설치 명령을 다시 실행하고 **에이전트를 재시작한다.**

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
- `/t` — 선택 날짜의 기록을 주제로 묶은 목록. 날짜 양옆 화살표로
  전날·다음날을 넘기며, 건수 1건 이하는 '미분류' 로 모인다
- `/t/{slug}` — 한 주제의 전체 기록과 부족한 재료. [초안 만들기] 가 여기 있다
- `/drafts/{id}` — 6단 초안. 미리보기 · 본문 고치기 · 붙여넣기용 **마크다운** ·
  [발행함] 표시. `WARRURU_PUBLISH_REPO` 를 정하면 [비공개 저장소에 밀어 넣기] 가,
  `WARRURU_TISTORY_BLOG` 을 정하면 [글쓰기 화면 열기] 가 함께 생긴다
- `/c/{YYYY-MM}` — 달력. 날짜 화면에 무언가 있는 날만 링크가 된다

전부 Jinja2 서버 렌더링이다. JS 는 초안 복사와 일반/다크 모드 전환에만 쓴다.
복사 스크립트가 죽어도 textarea 전체 선택으로 대체되고, 테마 스크립트가
죽으면 기본인 일반 모드로 읽을 수 있다.

초안 화면의 [다듬기] 칸에 요청을 적으면 **붙여넣을 한 줄에 얹힌다.**
데몬이 모델을 부르지는 않는다 — MCP 는 에이전트가 데몬을 부르는 단방향이라
반대로 갈 길이 없고, 그 길을 내면 기록이 이 머신을 떠난다. 여기서 줄이는 것은
옮겨 적는 수고까지다.
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

## 하루가 끝나면 자동으로

날짜가 바뀐 뒤 첫 스위프에서 **아직 마감하지 못한 날들의 주제로 초안을
만들어 둔다.** `WARRURU_PUBLISH_REPO` 가 설정돼 있으면 비공개 저장소로 밀어
넣기까지 한다.

새 프로세스도 새 포트도 만들지 않는다 — 이미 도는 스위퍼 안의 함수다.
cron 을 쓰지 않는 것도 같은 이유다. 데몬은 화면 때문에 어차피 떠 있다.

**어제까지를 마감한다. 오늘은 아니다.** 오늘은 아직 기록이 더 들어올 수 있고
어제는 확정된 하루다. 그래서 '몇 시에 돌 것인가' 를 설정으로 받지 않는다.
머신이 자고 있었어도 깨어난 뒤 첫 스위프에서 처리된다.

**데몬이 꺼져 있던 날도 함께 마감한다.** 표식(`~/.warruru/run/nightly.json`)에
적힌 날부터 어제까지를 한 구간으로 훑는다. 어제 하루만 보면 재부팅 뒤 며칠
만에 데몬이 뜬 경우 그 사이 날짜가 영영 잡히지 않는데, 데몬을 자동으로 띄우는
장치를 두지 않았으므로(launchd 도 cron 도 없다) 그 구멍이 실제로 열린다.

되돌아보기는 **14일**에서 멈춘다(`nightly.LOOKBACK_DAYS`). 표식이 없는 첫
기동에 몇 달치가 한꺼번에 쏟아지면 그것은 마감이 아니라 사고다. 표식이 아예
없으면 어제만 본다. 바닥 너머의 날은 `/t` 에서 직접 만들면 되고, 초안은 어차피
그 주제의 기록 전부를 재료로 쓰므로 잃는 것은 편의지 기록이 아니다.

**이미 초안이 있는 주제는 건드리지 않는다.** `upsert_draft` 가 미발행 초안을
덮어쓰므로, `save_draft` 로 다듬어 둔 글이 다음 날 밤 조립기 출력으로 덮이면
그 문장은 복원되지 않는다. 자동화가 사람의 작업을 지우는 것은 사고다.

끄려면 `WARRURU_NIGHTLY_DRAFT=0`.

## 바탕화면에서 켜기

재부팅하면 데몬은 죽어 있다. 자동 시작 장치를 두지 않았기 때문이다
(launchd 도 cron 도 쓰지 않는다 — `AGENTS.md` §3). 보통은 다음 대화에서
어댑터가 알아서 띄우지만, **대화를 열기 전에 화면부터 보고 싶을 때**가 있다.

```sh
ln -s "$(pwd)/scripts/warruru.command" "$HOME/Desktop/워루루 켜기.command"
```

두 번 누르면 데몬을 띄우고, 밀린 날 마감 결과를 알려 주고, `/t` 를 연다.

```text
  워루루
  ─────────────────────────────────────────
  데몬을 띄운다...
  떴다. (PID 29775)
  마감: 2026-08-28~2026-08-28 — 초안 1편
        · tistory-publishing
  초안 3편 · 남은 TODO 3개
  ─────────────────────────────────────────
```

**이 파일은 "동기화 버튼" 이 아니라 "켜기 버튼" 이다.** 밀린 날 마감은 이
스크립트가 아니라 **데몬이 뜨면서 스스로** 한다. 그래서 누르는 것을 잊어도
잃는 것이 없다 — 다음 대화에서 어댑터가 데몬을 띄우면 같은 일이 일어난다.

확장자가 `.command` 인 것은 macOS 가 그것만 두 번 눌러 실행하기 때문이다.
`.sh` 는 편집기로 열린다. 이 파일은 로그인 셸이 아니라서 `~/.zshrc` 의
환경변수가 보이지 않으므로, `WARRURU_PUBLISH_REPO` 가 필요하면 스크립트
안의 '선택 설정' 에 적는다.

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
`src/warruru_local/config.py` 의 `load_settings()` 가 정본이고, 지금은 19개다.

```text
WARRURU_HOME  TOKEN  TOOL  DAEMON_HOST  DAEMON_PORT  LOG_LEVEL
WARRURU_ATTACH_WINDOW_MINUTES   IDLE_TIMEOUT_HOURS
WARRURU_SWEEP_INTERVAL_SECONDS  SPOOL_QUIET_SECONDS
WARRURU_HTTP_TIMEOUT_SECONDS    AUTOSTART_DAEMON
WARRURU_GIT_TIMEOUT_SECONDS     GIT_CACHE_TTL_SECONDS
WARRURU_GIT_DIRTY_FILE_CAP      DRAFTS_ROOT  REPO_ROOT
WARRURU_PUBLISH_REPO            NIGHTLY_DRAFT
WARRURU_TISTORY_BLOG
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
