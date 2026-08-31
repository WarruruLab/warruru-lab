# AGENTS.md — WarruruLab 에이전트 가이드

이 파일은 매 세션 에이전트 컨텍스트에 자동으로 들어간다.
여기 적힌 것이 틀리면 매번 틀린 전제로 작업이 시작된다.
그래서 **실재하는 것만** 적고, 짧게 유지한다.

`CLAUDE.md` 는 이 파일을 `@import` 하는 포인터다. 그쪽은 고치지 않는다.

---

## 1. 지금 이 저장소에 있는 것

**실제로 도는 코드는 `local/` 하나다.** 소스 2,918줄(`.py` 기준, 템플릿 포함 3,093),
테스트 파일 24개(`conftest.py` 별도), 테스트 248개가 이 머신에서 전원 통과한다
(2026-08-18 실측, Python 3.12.14). `local/.venv/` 와 `~/.warruru/` 가 이미 있다.

- MCP stdio 어댑터 `warruru-mcp` — 툴 7개
  (`start_work` / `record_checkpoint` / `finish_work` / `get_today_context`
  / `record_learning` / `get_topic_records` / `save_draft`)
- 데몬 `warruru-daemon` — `127.0.0.1:8787`, FastAPI + Jinja2 서버 렌더링
- SQLite `~/.warruru/warruru.db` — 스키마 v2, 테이블 6개
  (`machine` / `client_instance` / `work_session` / `checkpoint`
  / `learning_record` / `draft`)
- 초안 파일 `~/.warruru/drafts/YYYY/MM/` — **저장소 바깥이다**
- 회사별 준비 노트 `~/.warruru/career/*.md` · 자격증 노트
  `~/.warruru/career/certs/*.md` · 주제 참고 노트
  `~/.warruru/career/topics/*.md` · 묶음 머리말
  `~/.warruru/career/groups/*.md` — 저장소 바깥이다.
  `/career` 는 이 파일들을 읽어 보여줄 뿐 **데몬은 노션에 닿지 않는다**
- 에이전트 플러그인 `agent-plugin/` — 스킬 2개(`warruru-recording`
  · `career-prep`) + MCP 연결.
  **Codex 와 Claude Code 가 매니페스트 한 벌을 같이 읽는다.** 한 번 설치하면
  다른 저장소를 열어도 기록 규칙과 툴이 따라온다.
  설치법은 `local/README.md`, 규칙 원문은 §5 와 같은 것이다
- 화면 — `/d/{date}` · `/c/{YYYY-MM}` · `/t` · `/t/{slug}` · `/drafts/{id}`
  · `/career`(허브 — 내가 채울 것 / 채용공고) · `/career/stack`
  · `/career/stack/{묶음}`
  · `/career/cert/{자격증}` · `/career/companies` · `/career/c/{회사}`
  조회는 토큰 불필요, 상태 변경 폼만 토큰.
  JavaScript 는 초안 복사와 일반/다크 모드 전환에만 쓴다.
  둘 다 실패해도 기록 조회·수정·발행 표시 경로는 살아 있다

### 코드 0줄이었던 명세 7묶음은 폐기한다

`packages/{agent,web-ui,local-record}` 와
`services/{ollama,qdrant,sync,tistory-mcp}` 는 AGENTS.md + docs 3종,
합쳐 28편의 명세만 있고 코드가 0줄이다. 그 명세들은 데몬과 같은
8787 포트를 요구하거나(web-ui), 없는 인프라를 전제하거나(agent 의
MySQL·Qdrant), 이미 죽은 API 를 기술한다(tistory-mcp 의 OAuth).
남겨두면 다음 세션의 에이전트가 그것을 읽고 틀린 전제를 세우므로
`.archive/specs-2026-08/` 로 내렸다(2026-08-18). `.archive/` 는 git 추적 대상이
아니라 작업 머신에만 남는다. 되살릴 일이 생기면 git 히스토리에서 꺼낸다.
**이 두 디렉터리를 확장하거나 근거로 삼지 않는다.**

---

## 2. 원칙

- **로컬 우선** — 모든 처리는 이 머신에서 끝난다. 사용자는 1명이다.
- **명세는 소비할 구현과 같은 주에만 쓴다** — 읽는 코드가 없는
  명세는 부채다. 위 7묶음이 그 증거다.
- **완료 조건은 산문이 아니라 통과하는 테스트 이름으로 적는다.**
  대응하는 커밋이 없는 체크박스는 존재하지 않는 것으로 본다.

크로스 플랫폼 동기화(Windows ↔ Mac)와 서버 운영은 **MVP 이후**다.
사용자가 그렇게 정했다. 핵심 원칙에서 내렸으니 설계 근거로 쓰지 않는다.

---

## 3. 하나만 둔다

MVP 전체가 `local/src/warruru_local/` 안에서 산다.

- 데몬 1 · DB 1 · 포트 1(8787) · MCP 서버 1
- 주기 작업도 그 데몬 안에 있다. 유휴 마감 · spool 흡수 · 밀린 날 초안 —
  셋 다 스위퍼 안의 함수이고, 데몬이 뜰 때 한 번씩 더 돈다. cron 도
  launchd 도 쓰지 않는다. `local/scripts/warruru.command` 는 예외가 아니라
  그 데몬의 시동 버튼일 뿐이다 — 스스로 아무 판단도 하지 않는다

**새 프로세스·새 포트·새 저장소·새 런타임 의존성을 만들지 않는다.**
필요해 보이면 그건 기존 것 안에 함수로 들어갈 자리를 못 찾은 것이다.
파일 하나 쓰려고 프로세스를 만들면, 중간에 멈췄을 때 골격만 남고
결과물은 없다.

## 4. 깨면 안 되는 경계

넷 다 이유가 있고, 어긴 자리가 조용히 썩는 종류다.

- **데몬이 SQLite 의 유일한 writer다.** 다른 어디서도 커서를 열지 않는다.
- **`mcp/` 는 `daemon/` 을 임포트하지 않는다.** 지금까지 한 번도 없다.
  어댑터는 판단도 요약도 하지 않고 봉투를 만들어 보낼 뿐이다.
- **`publish/` 는 `sqlite3` 와 `warruru_local.store.*` 를 임포트하지 않는다.**
  관례로 두지 않고 소스를 AST 로 훑는 테스트 1개로 강제할 것이다 —
  `local/tests/test_publish_boundary.py`, 계획 문서 Task 8 에서 들어온다.
- **날짜 경계는 `clock.local_day_bounds` 만 쓴다.** 날짜 문자열에
  `T00:00:00.000Z` 를 직접 잇지 않는다. 그렇게 하면 KST 오전 9시
  이전 기록이 통째로 앞 구간으로 샌다.

---

## 5. 에이전트 기록 규칙

이 절이 이 프로젝트의 산출물이 생기느냐 마느냐를 결정한다.
코드가 아니라 이 문단이 결정한다. MCP 가 대화를 감시해 '중요한 것'을
자동으로 잡아내는 장치는 만들지 않기로 했고, 그 자리를 이 규칙이 대신한다.

### 언제 부르는가

아래 넷 중 하나가 일어나면 `record_learning` 을 부른다.

- **수치가 달라졌을 때** — `kind='EXPERIMENT'`.
  전후 값을 둘 다 적는다. "빨라졌다"가 아니라 "p95 320ms→90ms".
- **고장났다 고쳤을 때** — `kind='TROUBLESHOOTING'`.
  증상 · 진짜 원인 · 고친 방법 셋이 한 벌이다.
- **여러 후보 중 하나를 골랐을 때** — `kind='TECH_CHOICE'`.
  고른 것보다 **버린 것과 버린 이유**가 면접에서 쓰인다.
- **CS 개념을 이해했을 때** — `kind='CONCEPT'`.
  코드에서 부딪혀 알게 된 것이면 "무엇인지"가 아니라 "그래서 지금 이 코드의
  무엇이 설명되는지"를 적는다.
  **읽어서 안 것도 남긴다**(2026-09-01 정함). 자료구조·알고리즘처럼 만들다
  부딪히지 않는 주제가 있어서, 코드에서 만날 때까지 기다리면 영영 안 남는다.
  대신 **내 말로** 적는다 — 옮겨 적은 문장은 기록이 아니라 사본이고,
  면접에서 그대로 드러난다.

### 어떻게 부르는가

- **사용자가 시키지 않아도 그 자리에서 남긴다.** "기록할까요?"라고
  물어보고 남기는 것이 아니다. 물어보면 흐름이 끊기고, 끊기면 안 남는다.
- 필수는 `kind` · `topic` · `title` · `body` 넷뿐이다.
  `rationale` · `outcome` · `limitation` · `interview` 는 비어도 거절당하지 않는다.
- **재료가 없으면 지어내지 마라.** 특히 `limitation` 과 `rationale` 은
  사용자 머릿속에만 있다. 비운 채로 저장한 다음 **그 자리에서 되물어라** —
  "풀 크기를 30 이상으로 못 올린 이유가 무엇이었나요?"
  답을 받으면 **응답에 실려 온 `record_id` 를 그대로 넘겨** 같은 툴을 다시 부른다.
  그래야 빈칸이 채워진다. `record_id` 없이 다시 부르면 거의 같은 기록이 하나 더 생긴다.
  지어낸 문장은 면접장에서 안 나온다. 그게 이 도구의 유일한 실패 방식이다.
- 응답의 `missing_fields` · `example_call` · `similar_slugs` · `recommended` 를 읽어라.
  거절 대신 오는 것이다. `example_call` 은 복사해서 바로 다시 부를 수 있는 형태다.
  `recommended` 가 `true` 면 로드맵 위의 주제를 정확히 짚은 것이다.
  `similar_slugs` 는 **비슷한 다른 것**만 준다 — 자기 자신은 빼므로,
  권장 슬러그를 그대로 적었을 때 비는 것이 정상이다.
- `missing_fields_scope` 가 `call_args` 면 그 목록은 **이번 호출 인자만** 본 값이다
  (데몬이 꺼진 채 보강한 경우). 이미 채워 둔 필드를 다시 묻지 마라.
- `topic` 은 원문 그대로 적는다. 정규화는 시스템이 한다.
  권장 슬러그는 `docs/guides/backend-infra-roadmap-31w.md` 부록 A 에 있다 —
  **그 목록을 쓰면 힌트가 첫 호출부터 맞는다.** 한글로 적으면 한글 슬러그가 되어
  그 목록과 절대 만나지 않으므로, 한쪽으로 정해 쓴다.

### 글로 만들 때

- 하루 끝에 `http://127.0.0.1:8787/t` 를 열면 그날 기록이 주제로 묶여 있다.
- 주제를 눌러 [초안 만들기] 를 누르면 6단 마크다운이
  `~/.warruru/drafts/YYYY/MM/` 에 생긴다. **LLM 호출은 0이다.**
- 빈 절은 `TODO:` 로 남는다. 그 자리가 곧 "면접에서 대답 못 할 부분" 이다.
  **지어내서 채우지 마라** — 기록을 보강하고 다시 만든다.
- 초안 화면이 주는 `polish topic=... draft=...` 한 줄을 받으면
  `get_topic_records` 로 재료를 읽고, 다듬은 글을 `save_draft` 로 덮어쓴다.
  그 툴의 `missing_summary` 가 비어 있는 필드를 알려준다 — **되물어라.**

### 데몬이 꺼져 있어도 부른다

```
record_learning → 어댑터 → 데몬(8787) → SQLite
                     │              ↑
                     └ 못 닿음 → spool → 다음 기동 때 흡수
```

기록 실패로 개발이 멈추는 일은 없다. 툴은 예외를 밖으로 던지지 않는다.

다만 **`spool_backlog` 이 응답에 있으면 그 기록은 아직 DB 에 없다.**
그 수가 계속 늘면 데몬이 영영 안 뜨고 있는 것이니, 사용자에게 말한다 —
"나중에 반영됩니다" 를 곧이곧대로 옮기지 마라.

세 툴 모두 도착했다(2026-08-25). 툴 목록에 없으면 데몬이 구버전이니,
없는 툴을 부른 척하지 말고 그 사실을 사용자에게 말한다.

---

## 6. 계획 문서는 하나뿐이다

유지되는 계획 문서는 이것 하나다. **새 계획 문서를 만들지 않는다.**

- `local/docs/plans/2026-08-17-학습기록-구현계획.md`

같은 주제의 계획이 두 문서로 갈라지는 순간이 지난 실패
('명세만 쌓이고 코드 0줄')의 시작점과 정확히 같은 모양이었다.
축소됨 표시를 달고 새 문서를 쓰는 것도 안 된다 — 다음 세션의
에이전트가 어느 쪽을 믿을지 모르게 된다. 기존 문서를 개정한다.

---

## 7. 실재하는 문서

여기 없는 문서는 없는 것이다. 링크를 지어내지 않는다.

**루트**

- `README.md` — 프로젝트 소개와 현재 상태
- `docs/git-convention.md` — 커밋·브랜치·PR 규칙 (Google 관례 기반).
  **§0 을 먼저 읽어라 — `git add -A` 를 쓰지 않는다.** 작업 트리에 있던
  남의 파일이 public 저장소에 올라간 사고가 하루에 두 번 났다(2026-08-25)
- `docs/guides/backend-infra-roadmap-31w.md` — 31주 학습 로드맵,
  주차별 권장 `topic_slug` 의 원본
- `docs/superpowers/specs/2026-08-12-learning-record-design.md` —
  **대체됨.** 지금 명세가 흡수했고 일부 결정은 뒤집혔다. 파일 첫머리 경고를 읽어라
- `docs/architecture/` — **없다.** 시스템 맵 HTML 2개는 폐기한 아키텍처를
  그린 것이라 `.archive/architecture-2026-07/` 로 내렸다(2026-08-18)

**local/**

- `local/README.md` — Task 0(환경 구축)과 MCP 설정
- `local/docs/specs/2026-08-18-mvp-daily-loop.md` — 이번 MVP 명세(확정)
- `local/docs/acceptance.md` — 평가 기준. 리뷰 루프의 종료 조건
- `local/docs/plans/2026-08-17-학습기록-구현계획.md` — 유일한 계획 문서
- `local/docs/plans/2026-07-22-warruru-local-1단계-구현계획.md` — 완료된 1단계
- `local/docs/OUTSTANDING.md` — 미해결 결함
- `local/docs/adr/2026-08-18-publish-target.md` — 발행 경로 결정

**agent-plugin/**

- `agent-plugin/warruru/skills/warruru-recording/SKILL.md` — §5 를 저장소 밖으로
  들고 나간 사본. 권장 슬러그 100개가 본문에 실려 있다.
  `local/tests/test_agent_plugin.py` 가 `topics.py` 와 대조해 어긋남을 막는다
- `agent-plugin/warruru/skills/career-prep/SKILL.md` — 노션의 공고 아카이브와
  기록을 대조해 **빈 곳**을 뽑는다. 산출물은 `~/.warruru/career/` 다.
  데몬은 노션을 모른다 — 읽는 쪽은 에이전트뿐이라 새 의존성이 없다.
  `local/tests/test_career_skill.py` 가 매핑 표와 로드맵 100개를 대조한다

`docs/architecture/*.md` · `docs/api/*` 12편은 **만들지 않는다.**
약속만 있고 실물이 없었다. 시스템이 데몬 하나면 아키텍처 문서 4개가
필요 없으므로, 문서를 만드는 대신 약속을 지웠다.

---

## 8. 지금 하는 일

`local/` 축을 한 뼘 늘려, 개발 중 남긴 기록이
"문제 → 선택 → 구현 → 측정 → 결과 → 한계" 6단 마크다운 한 편이 되어
저장소 **바깥**에 앉는 것까지 한 바퀴를 돌린다.

**계획서의 구현 태스크는 전부 닫혔다**(2026-08-25). 다음은 새 코드가 아니라
한 주 써 보고 재는 일이다 — 기록 건수(기준선 주 5건)와 초안의 TODO 수.

- 마이그레이션 v2 — `learning_record` · `draft` ✅
- MCP 툴 3개 추가(총 7개) ✅
- 웹 라우트 `/t` · `/t/{slug}` · `/drafts/{id}` · 달력 `/c/{YYYY-MM}` ✅
- 결정적 6단 조립기 — **LLM 호출 0** ✅
- `PublishTarget` 인터페이스 + 어댑터 3개 ✅
  (`MarkdownFileTarget` · `TistoryClipboardTarget` · `GitPrivateRepoTarget`)

착지점은 `~/.warruru/drafts/YYYY/MM/` 이고, 저장소 안 경로가 인자로
들어오면 쓰기 어댑터가 **예외를 던진다.** origin 이 public 저장소이므로
이건 취향이 아니라 사고 방지 장치다. `.gitignore` 한 줄은 `git add -f`
한 번에 뚫리니 방어로 치지 않는다. `blog/` 는 사람이 읽고
"공개해도 된다"고 결정한 글만 들어가는 자리로 역할을 축소했다.

**Task 0(환경)은 2026-08-18 에 끝났다.** 248 passed, 데몬 기동 확인.
다시 할 필요 없다 — `local/.venv/` 를 켜고 바로 작업한다.
그 과정에서 `mcp` 2.0.0 이 `mcp.server.fastmcp` 경로를 없앤 것을 발견해
`pyproject.toml` 을 `mcp>=1.16.0,<2` 로 고정했다. 이 상한을 풀지 마라.

**티스토리 자동 발행은 접었다(2026-08-28).** 약관 때문이 아니라 캡차 때문이다 —
약관에는 자동화 금지 조항이 없고 대법원 2021도1533 이 그 질문을 무력화하는데,
`DKAPTCHA` 가 발행마다 떠서 사람이 풀면 붙여넣기보다 느리다. 우회는 하지 않는다.
대신 `GitPrivateRepoTarget` 으로 간다. 근거는 발행 경로 ADR 에 있다.

**이번에 하지 않는 것** — 티스토리 자동 발행(위 참조) · 데몬 안의 LLM 호출 ·
RAG/Qdrant/임베딩 · 크로스 플랫폼 동기화 · `measurement`/`tech_option`
정규화 테이블 · 기록 거절 규칙. 각각의 이유는 이번 MVP 명세에 있다.

---

**Last Updated:** 2026-08-31
