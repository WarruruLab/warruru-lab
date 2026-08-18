# 학습 기록 (Learning Record) 설계

> ## ⚠️ 이 문서는 대체됐다 (2026-08-18)
>
> **정본은 `local/docs/specs/2026-08-18-mvp-daily-loop.md` 다.**
> 이 문서는 그 명세가 흡수했고, 아래 결정 넷은 **명시적으로 뒤집혔다.**
>
> | 이 문서의 결정 | 지금 확정된 것 |
> |---|---|
> | `kind` 별 MCP 툴 4개 | `record_learning` 툴 하나 |
> | 필수 필드 미비 시 거절 | 거절하지 않고 결손 필드 힌트를 돌려준다 |
> | `topic` 은 검증 없는 자유 문자열 | 원문 보존 + `topic_slug` 정규화 |
> | `measurement` · `tech_option` 정규화 테이블 | 만들지 않는다. 본문 텍스트로 |
>
> 뒤집은 이유는 새 명세 §5 의 정산표에 있다.
> **이 문서를 근거로 설계하지 마라.** 남겨 둔 이유는 왜 그렇게 정했었는지를
> 되짚을 때 쓰기 위해서다.

**작성일:** 2026-08-12
**개정:** 2026-08-17 — 코드 대조 리뷰 반영 (시간대 변환, SPOOL 반환값, 검증 위치)
**개정:** 2026-08-17 — 기록 종류를 4종으로 확장 (기술 선택 · CS 개념), 면접 문장 필드 추가
**대상:** `local/` (warruru-local) — 마이그레이션 v2
**상태:** **대체됨(2026-08-18).** 위 경고를 먼저 읽어라.

---

## 1. 왜 만드는가

2027년 3월 공채를 목표로 한 31주 백엔드·인프라 로드맵(2026-08-12 시작)을 수행한다.
그 과정에서 **면접에서 말해야 할 것**이 네 갈래로 생기는데, 넷 다 지금 남길 곳이 없다.

**1. 측정값이 붙은 개선.**
산책온·StackUp 에서 N+1 개선 전후의 쿼리 수, Redis 적용 전후의 p95 가 계속 나온다.
숫자는 기억에 남지 않는다.

**2. 장애와 해결.**
증상 → 원인 → 해결의 사슬은 며칠만 지나도 "그때 뭐가 원인이었더라"가 된다.

**3. 기술 선택의 근거.**
이게 실제로는 가장 자주 물어보는 것이다. RabbitMQ 냐 Kafka 냐, Redis 를 캐시로 쓸까 세션 저장소로 쓸까 —
**후보를 늘어놓고, 각각의 장단점을 적고, 우리 프로젝트의 어떤 특성 때문에 이걸 골랐고,
고른 것의 단점을 어떻게 보완했는지**까지가 한 덩어리다.
지금은 이 덩어리가 통째로 머릿속에만 있다. 몇 주 지나면 "Kafka 를 썼습니다"만 남는다.
그건 기술 이름을 나열하는 설명이고, 로드맵이 명시적으로 버리기로 한 방식이다.

**4. CS 기초.**
Java · 네트워크 · OS · DB · 알고리즘 · 자료구조, 그리고 백엔드 포트폴리오에 쓰는 기술들.
2027년 상반기에 이것들을 공부하면서, 읽은 것을 **내 말로 다시 쓴 문장**이 남아야 한다.
남의 문장은 면접장에서 안 나온다.

넷 다 같은 성질을 갖는다 — 그 순간에 적지 않으면 복원할 수 없고,
31주차에 다시 읽을 것이며, 최종 목표인 **"문제 → 선택 → 구현 → 측정 → 결과 → 한계"**
서사의 재료다. 그래서 한 테이블·한 화면에 담는다.

### 이 조각이 끝나면 할 수 있는 일

- 개선을 마친 자리에서 에이전트에게 "이거 기록해 줘" 하면 측정값과 함께 남는다.
- 기술을 고른 자리에서 **후보와 장단점, 선택 근거, 보완책**이 한 기록으로 남는다.
- CS 를 공부한 자리에서 분야(Java · 네트워크 · OS · DB · 알고리즘 · 자료구조)를 붙여 남긴다.
- `http://127.0.0.1:8787/records` 에서 프로젝트별·주차별·분야별로 훑어본다.
- **면접 문장이 비어 있는 기록**만 골라내 복습 대상으로 삼는다.
- 에이전트가 `list_records` 로 과거 기록을 꺼내 주간 정리나 면접 서사를 조립한다.

---

## 2. 배경: `local/` 의 현재 구조

`local/` 은 와르르랩에서 **유일하게 동작하는 축**이다.
(`packages/*`, `services/*` 는 명세만 있고 코드가 0줄이다.)

```
Codex / Claude Code / Antigravity
        │  stdio (에이전트마다 1 프로세스)
        ▼
   warruru-mcp  ──HTTP──▶  warruru-daemon(:8787)  ──▶  ~/.warruru/warruru.db (SQLite)
                                  │
   브라우저  ─────────────────────┘  (날짜별 화면)
```

재사용할 자산:

- **데몬이 SQLite 의 유일한 writer.** 잠금·동시성 문제가 이미 해결돼 있다.
- **spool.** 데몬에 못 닿으면 `~/.warruru/spool/` 에 남겼다가 흡수한다.
  성공 응답을 받은 기록은 유실되지 않는다.
- **세션 자동 부착.** `record_checkpoint` 는 `work_id` 없이 불러도
  `sessions.attach` 가 활성 세션을 찾거나 만들어 붙인다.
- **git 스냅샷.** `gitinfo.collect()` 가 repo/branch/commit/dirty 를 수집한다.
- **한도.** `limits.py` — 상한을 넘는 값은 거절하지 않고 자른다.

기존 MCP 툴 4개: `start_work` / `record_checkpoint` / `finish_work` / `get_today_context`.
기존 테이블 4개: `machine` / `client_instance` / `work_session` / `checkpoint`.
기존 테스트 25개 파일 (pytest).

### 왜 `checkpoint` 를 확장하지 않는가

`checkpoint` 는 `type` 이 9종으로 고정돼 있고 `work_id` 가 `NOT NULL` 이며
수치를 담을 자리가 없다. 여기에 지표 컬럼을 끼워 넣으면 두 개념이 섞인다.
체크포인트는 *작업 중의 순간*이고, 학습 기록은 *면접에서 말할 수 있게 정리된 것*이다 —
검증된 개선, 근거가 붙은 선택, 내 말로 쓴 이해.
수명도 다르다 — 체크포인트는 그날 지나면 잘 안 보지만
학습 기록은 31주차에 다시 읽는다.

---

## 3. 확정된 설계 결정

| 결정 | 내용 | 근거 |
|---|---|---|
| 필수 필드 | 핵심만 강제, 나머지는 선택 | 기록 마찰이 크면 실제로 안 남긴다. 결론·한계는 기록 시점에 모를 수 있다 |
| 기록 종류 | **MCP 툴 4개 / 테이블 1개** (`kind` 4종) | MCP JSON Schema 는 "조건부 필수"를 표현하지 못한다. 툴을 나눠야 에이전트에게 명확하다 |
| 기술 선택 | 후보를 **자식 테이블**(`option`)로, 2개 이상 필수 | "여러 개 중에 골랐다"가 증명되지 않으면 그 기록은 면접에서 못 쓴다. 후보 없이 결론만 있는 기록을 막는다 |
| 단점 보완 | `mitigation` 컬럼. 선택이지만 **비면 화면에 배지** | 기록 시점엔 아직 보완 안 했을 수 있다. 거절 대신 눈에 띄게 남겨 나중에 채우게 한다 |
| CS 분야 | `topic` 한 컬럼 (자유 문자열 + 권장값) | 분야를 테이블로 만들면 새 분야마다 마이그레이션이 필요하다. 오타는 목록 화면에서 바로 보인다 |
| 면접 문장 | `interview` 컬럼, **4종 공통** | 최종 목표는 "말할 수 있는 상태"다. 기록마다 말할 문장을 붙여 두면 31주차에 조립이 아니라 낭독이 된다 |
| 저장 위치 | 공용 `~/.warruru/warruru.db` + `project` 필드 | 데몬 1개·DB 1개·포트 1개 구조 유지. 31주차에 두 프로젝트를 한 번에 조회 |
| 측정값 | 지표 여러 개(`measurements`) + 근거 텍스트(`evidence`) | 하나의 개선이 쿼리수와 p95 를 동시에 움직인다. 그게 한 기록에 남아야 한다 |
| 조회 | MCP 툴 + 전용 웹 화면 `/records` | 에이전트가 조립하고, 사람이 눈으로 확인한다 |
| 주차 | 설정된 시작일로 조회 시 자동 계산 | 에이전트가 몇 주차인지 알 필요가 없다. 저장하지 않으므로 계산식을 고쳐도 과거가 안 흔들린다 |
| 결합 방식 | `local/` 안에서 확장 (같은 데몬·MCP·DB) | 신뢰성(spool·중복·잠금)은 이미 값을 치르고 확보한 자산이다 |

---

## 4. 데이터 모델 (마이그레이션 v2)

`store/migrations.py` 의 `CURRENT_VERSION` 을 `2` 로 올리고 `_V2` 스크립트를 더한다.
기존 v1 테이블은 수정하지 않는다. 마이그레이션은 앞으로만 간다 — 되돌리기는 없다.

```sql
CREATE TABLE IF NOT EXISTS learning_record (
    record_id      TEXT PRIMARY KEY,
    work_id        TEXT NOT NULL REFERENCES work_session(work_id),
    machine_id     TEXT NOT NULL REFERENCES machine(machine_id),
    tool           TEXT NOT NULL,

    kind           TEXT NOT NULL,   -- EXPERIMENT | TROUBLESHOOTING
                                    -- | TECH_CHOICE | CONCEPT
    title          TEXT NOT NULL,   -- 한 줄 요약. 목록 화면이 읽는 값
    topic          TEXT,            -- JAVA NETWORK OS DB ALGORITHM
                                    -- DATA_STRUCTURE SPRING INFRA … (자유 문자열)
    problem        TEXT NOT NULL,   -- 무엇 때문에 이 기록이 생겼나 (§4 매핑표)
    hypothesis     TEXT,            -- 실험: 왜 그렇게 판단했나
    cause          TEXT,            -- 트러블슈팅: 원인
    action         TEXT,            -- 무엇을 했나 (§4 매핑표)
    rationale      TEXT,            -- 기술 선택: 왜 이걸 골랐나 (프로젝트 특성 근거)
    mitigation     TEXT,            -- 기술 선택: 고른 것의 단점을 어떻게 보완했나
    outcome        TEXT,            -- 결론 / CS: 핵심 정리
    limitation     TEXT,            -- 한계 / CS: 아직 모르는 것
    interview      TEXT,            -- 면접에서 이렇게 말한다 (4종 공통)
    evidence       TEXT,            -- EXPLAIN·SQL·로그·코드 원문
    evidence_truncated INTEGER NOT NULL DEFAULT 0,
    tags_json      TEXT,
    project        TEXT,            -- repo_name 기반. 기록 시점에 고정

    occurred_at    TEXT NOT NULL,
    recorded_at    TEXT NOT NULL,
    source         TEXT NOT NULL,   -- MCP | SPOOL

    repo_path      TEXT,
    repo_name      TEXT,
    branch         TEXT,
    commit_sha     TEXT,
    dirty          INTEGER,
    dirty_file_count   INTEGER,
    dirty_count_capped INTEGER NOT NULL DEFAULT 0,

    deleted_at     TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_record_occurred
    ON learning_record (occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_project_kind
    ON learning_record (project, kind, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_work
    ON learning_record (work_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_record_topic
    ON learning_record (topic, occurred_at DESC);

CREATE TABLE IF NOT EXISTS measurement (
    measurement_id TEXT PRIMARY KEY,
    record_id      TEXT NOT NULL REFERENCES learning_record(record_id),
    seq            INTEGER NOT NULL,   -- 입력 순서 보존
    metric         TEXT NOT NULL,      -- "p95_latency"
    unit           TEXT,               -- "ms"
    before_value   REAL NOT NULL,
    after_value    REAL NOT NULL,
    direction      TEXT NOT NULL DEFAULT 'LOWER_IS_BETTER'
);

CREATE INDEX IF NOT EXISTS ix_measurement_record
    ON measurement (record_id, seq);

CREATE TABLE IF NOT EXISTS tech_option (
    option_id      TEXT PRIMARY KEY,
    record_id      TEXT NOT NULL REFERENCES learning_record(record_id),
    seq            INTEGER NOT NULL,   -- 입력 순서 보존
    name           TEXT NOT NULL,      -- "RabbitMQ"
    pros           TEXT,               -- 장점
    cons           TEXT,               -- 단점
    chosen         INTEGER NOT NULL DEFAULT 0   -- 고른 것 1, 나머지 0
);

CREATE INDEX IF NOT EXISTS ix_option_record
    ON tech_option (record_id, seq);
```

### 필수 필드

DB 레벨에서는 `title` / `problem` 만 `NOT NULL` 이다.
`cause` 와 `action` 은 트러블슈팅에만 필수이므로 컬럼은 NULL 을 허용하고
**검증은 입구(MCP·API)에서** 한다. 규칙은 `record_rules.py` 한 곳에 적고
"비어 있음"의 정의(공백 문자열·빈 리스트)도 거기서 정한다 (§7).

| kind | 필수 |
|---|---|
| `EXPERIMENT` | `title`, `problem`, `measurements` 1개 이상 |
| `TROUBLESHOOTING` | `title`, `problem`(증상), `cause`, `action`(해결) |
| `TECH_CHOICE` | `title`, `problem`(무엇을 정해야 했나), **`options` 2개 이상**, 그중 정확히 하나가 `chosen`, `rationale` |
| `CONCEPT` | `title`, `topic`, `problem`(왜 봤나 / 뭐가 헷갈렸나), `outcome`(핵심 정리) |

`title` 은 애초 정한 핵심 필드보다 하나 많다.
목록 화면과 서사 조립이 실제로 읽는 값이고,
없으면 `problem` 을 잘라 써야 하는데 그건 눈에 띄게 나쁘다.

**`options` 2개 이상이 `TECH_CHOICE` 의 핵심 강제다.**
후보가 하나면 그건 선택이 아니라 통보다. 면접에서 "왜 그걸 골랐냐"에
답할 수 없는 기록은 남길 이유가 없다. `chosen` 이 정확히 하나여야 하는 것도 같은 이유다.

**`mitigation`(단점 보완)은 일부러 필수가 아니다.**
기술을 고르는 시점에는 아직 보완하지 않았을 수 있다.
대신 비어 있으면 목록·상세 화면에 **"보완책 없음" 배지**가 붙어 눈에 띈다 (§8).
`interview`(면접 문장)도 같다 — 없으면 배지가 붙고, `list_records` 로 그것만 골라낼 수 있다.
거절하면 기록 자체를 안 하게 되고, 조용히 넘어가면 영영 안 채운다. 배지가 그 사이다.

### `kind` 별 필드 매핑

같은 컬럼이 종류마다 다른 의미를 갖는다. 화면과 툴은 이 표를 따른다.

| 화면 라벨 | EXPERIMENT | TROUBLESHOOTING | TECH_CHOICE | CONCEPT |
|---|---|---|---|---|
| 문제 | 무엇이 느렸나 | 증상 | 무엇을 정해야 했나 | 왜 봤나 / 뭐가 헷갈렸나 |
| 선택 | `hypothesis` 가설 | `cause` 원인 | `options` 후보 비교 + `rationale` | — |
| 구현 | `action` 무엇을 바꿨나 | `action` 해결 방법 | `mitigation` 단점 보완 | `action` 어떻게 확인했나 |
| 측정 | `measurements` | `measurements`(있으면) | `measurements`(있으면) | — |
| 결과 | `outcome` | `outcome` | `outcome` 도입 후 | `outcome` 핵심 정리 |
| 한계 | `limitation` | `limitation` | `limitation` 남은 한계 | `limitation` 아직 모르는 것 |
| **면접** | `interview` | `interview` | `interview` | `interview` |

`CONCEPT` 의 "구현"이 `action`(어떻게 확인했나)인 것은 의도적이다.
읽기만 한 개념과 **직접 돌려 본 개념**은 면접에서 티가 난다.
코드로 확인했다면 그 자리에 남고, 안 했다면 빈칸으로 남아 그 사실이 보인다.

### 저장하지 않는 값

`week` 와 개선률(`-88%`)은 컬럼이 아니라 **조회 시 계산**한다 (§6).
로드맵 시작일이 바뀌거나 계산식을 고쳐도 과거 기록을 손댈 필요가 없다.

### `direction` 이 필요한 이유

p95·쿼리 수는 낮을수록 좋지만 처리량(TPS)은 높을수록 좋다.
이 값이 없으면 화면이 `1200 → 3400` 을 악화로 표시한다.
기본값은 `LOWER_IS_BETTER` — 대부분의 성능 지표가 그렇다.

### `work_id` 가 `NOT NULL` 인 이유

체크포인트와 똑같이 `sessions.attach` 가 자동으로 붙인다.
호출자는 `work_id` 를 몰라도 되고,
"이 실험이 어떤 작업 중에 나왔나"가 보존되며 날짜별 화면과도 연결된다.

**알고 받는 한계:** `attach` 는 귀속을 "지금" 기준으로 판단한다 (§12 I4, 미해결).
그래서 데몬이 꺼진 채 월요일에 남긴 기록이 화요일에 흡수되면
화요일의 살아 있는 작업에 붙는다. 기록 자체(내용·`occurred_at`)는 온전하고
`/records` 화면은 `occurred_at` 으로 정렬·필터하므로 이 기능의 결과는 흔들리지 않는다.
소속 작업 링크만 어긋난다. 이번 범위에서 고치지 않는다.

---

## 5. MCP 툴 표면

기존 서버(`mcp/server.py`)에 툴 6개를 더한다. 기존 4개는 그대로 둔다.
기록 툴 4개(종류마다 하나)와 조회 툴 2개다.

```python
from warruru_local.measurement import MeasurementInput  # 최상위 (§6)
# metric / before / after / unit / direction("LOWER_IS_BETTER" | "HIGHER_IS_BETTER")

from warruru_local.measurement import OptionInput       # 최상위 (§6)
# name / pros / cons / chosen(bool)


@server.tool()
def record_experiment(
    title: str,
    problem: str,
    measurements: list[MeasurementInput],
    hypothesis: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limitation: str | None = None,
    evidence: str | None = None,
    tags: list[str] | None = None,
    occurred_at: str | None = None,
    repo_path: str | None = None,
) -> dict:
    """무언가를 바꿔서 수치가 달라진 것을 기록한다. 측정값이 없으면 이 툴이 아니다."""


@server.tool()
def record_troubleshooting(
    title: str,
    symptom: str,          # → problem
    cause: str,
    fix: str,              # → action
    measurements: list[MeasurementInput] | None = None,
    outcome: str | None = None,
    limitation: str | None = None,
    evidence: str | None = None,
    tags: list[str] | None = None,
    occurred_at: str | None = None,
    repo_path: str | None = None,
) -> dict:
    """무언가 고장났다가 고쳐진 것을 기록한다. 증상·원인·해결이 모두 필요하다."""


@server.tool()
def record_tech_choice(
    title: str,
    problem: str,                    # 무엇을 정해야 했나
    options: list[OptionInput],      # 후보 2개 이상. 정확히 하나가 chosen
    rationale: str,                  # 우리 프로젝트의 어떤 특성 때문에 골랐나
    mitigation: str | None = None,   # 고른 것의 단점을 어떻게 보완했나
    outcome: str | None = None,
    limitation: str | None = None,
    interview: str | None = None,
    measurements: list[MeasurementInput] | None = None,
    topic: str | None = None,
    evidence: str | None = None,
    tags: list[str] | None = None,
    occurred_at: str | None = None,
    repo_path: str | None = None,
) -> dict:
    """여러 기술 중 하나를 고른 것을 기록한다.

    후보가 하나뿐이면 이 툴이 아니다 — 후보마다 장점과 단점을 적고,
    그중 하나에만 chosen 을 준다. rationale 에는 일반론이 아니라
    이 프로젝트의 구체적인 특성을 적는다.
    """


@server.tool()
def record_concept(
    title: str,
    topic: str,                      # JAVA NETWORK OS DB ALGORITHM DATA_STRUCTURE …
    problem: str,                    # 왜 봤나 / 뭐가 헷갈렸나
    outcome: str,                    # 핵심 정리 — 내 말로
    action: str | None = None,       # 어떻게 확인했나 (코드·실험)
    limitation: str | None = None,   # 아직 모르는 것
    interview: str | None = None,
    evidence: str | None = None,
    tags: list[str] | None = None,
    occurred_at: str | None = None,
    repo_path: str | None = None,
) -> dict:
    """CS 개념을 공부하고 남긴다. outcome 은 읽은 문장이 아니라 내 말로 쓴다.

    남의 문장을 그대로 옮기면 면접장에서 안 나온다.
    """


@server.tool()
def list_records(
    project: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    tag: str | None = None,
    week: int | None = None,
    since: str | None = None,
    until: str | None = None,
    missing: str | None = None,   # "interview" | "mitigation"
    limit: int = 20,
) -> dict:
    """남긴 기록을 조건으로 찾는다. 본문은 요약만 돌려준다.

    missing="interview" 를 주면 면접 문장이 비어 있는 기록만 나온다.
    복습할 것을 고를 때 쓴다.
    """


@server.tool()
def get_record(record_id: str) -> dict:
    """기록 하나의 전체 내용을 읽는다. evidence 원문까지 포함한다."""
```

`measurements` 와 `options` 를 `list[dict]` 가 아니라 pydantic 모델로 받는 이유는,
FastMCP 가 이걸 JSON Schema 로 내보내서 **에이전트가 필드 이름을 추측하지 않게** 되기 때문이다.
`pros` / `cons` 라는 이름이 스키마에 박혀 있으면 에이전트는 장단점을 빠뜨리기 어려워진다.
툴 설명(docstring)이 곧 프롬프트이므로 "언제 이 툴이 아닌지"를 한 줄에 못 박는다.

### 반환값

기존 툴과 같은 모양(`ok` / `storage` / `message`)에 아래를 더한다.

```python
{
    "ok": True,
    "storage": "DAEMON",          # 또는 "SPOOL" / "NONE"
    "message": "...",
    "record_id": "rec_01H...",
    "work_id": "wrk_01H...",
    "work_origin": "IMPLICIT",
    "attached_by": "CLIENT",
    "project": "산책온",
    "week": 13,                    # 계산된 값. 시작일 미설정이면 None
    "measurements": [
        {"metric": "query_count", "unit": "개",
         "before": 102.0, "after": 3.0,
         "change": -99.0, "percent": -97.06, "improved": True},
        {"metric": "p95_latency", "unit": "ms",
         "before": 1800.0, "after": 220.0,
         "change": -1580.0, "percent": -87.78, "improved": True},
    ],
    "git": {...},
}
```

에이전트가 기록 직후 "쿼리 102→3 (-97%)" 를 그대로 사용자에게 보고할 수 있다.

### 데몬에 닿지 못했을 때 (`storage="SPOOL"`)

`client.send()` 는 spool 로 떨어지면 `body` 가 `None` 인 `Outcome` 을 돌려준다.
데몬만 아는 값(`work_id` · `work_origin` · `attached_by` · `project` · `week` · `git`)은
그때 채울 수 없으므로 **`None` 으로 나간다.**

다만 **개선률은 SPOOL 에서도 채운다.** `delta_of` 를 데몬이 아니라
최상위 `measurement.py` 에 두고 MCP 가 직접 계산하기 때문이다 (§6).
`record_id` 도 MCP 가 만든 값이라 그대로 돌려준다.

```python
{
    "ok": True,
    "storage": "SPOOL",
    "message": "데몬에 닿지 못해 보관했습니다. 다음 기동 때 반영됩니다.",
    "record_id": "rec_01H...",
    "work_id": None, "work_origin": None, "attached_by": None,
    "project": None, "week": None, "git": None,
    "measurements": [  # 개선률은 그대로 있다
        {"metric": "query_count", "unit": "개", "before": 102.0, "after": 3.0,
         "change": -99.0, "percent": -97.06, "improved": True},
    ],
}
```

데몬이 꺼져 있어도 에이전트의 보고 문장이 달라지지 않는다.
이것이 `delta_of` 를 순수 함수로 최상위에 두는 실질적인 이유다.

`list_records` 는 `evidence` 를 뺀 요약 목록을 돌려주고,
`get_record` 는 전체를 돌려준다. 컨텍스트를 아끼기 위한 구분이다.
둘 다 조회이므로 데몬이 꺼져 있으면 `storage="NONE"` 이다 (기존 `query()` 관례).

`limit` 은 상한 100, 기본 20 이다. **페이징(offset·커서)은 이번 범위 밖이다** (§10).

### 한도 (`limits.py`)

기존 상수를 그대로 쓰고 필요한 것만 더한다.

| 대상 | 상한 | 상수 |
|---|---|---|
| `title` | 200자 | `TITLE_MAX` (기존) |
| `topic` | 200자 | `TITLE_MAX` (기존) |
| `problem` `hypothesis` `cause` `action` `outcome` `limitation` | 4096자 | `TEXT_MAX` (기존) |
| `rationale` `mitigation` `interview` | 4096자 | `TEXT_MAX` (기존) |
| 후보의 `name` | 200자 | `TITLE_MAX` (기존) |
| 후보의 `pros` `cons` | 4096자 | `TEXT_MAX` (기존) |
| `evidence` | 65536자 | `BODY_MAX` (기존) |
| `tags` | 20개 | `TAGS_MAX` (기존) |
| `measurements` | 10개 | `MEASUREMENTS_MAX` (신규) |
| `options` | 8개 | `OPTIONS_MAX` (신규) |

후보 8개를 넘겨 비교하는 기술 선택은 없다. 넘으면 자르고 몇 개를 버렸는지 알린다.
다만 **`chosen` 인 후보가 잘려 나가면 거절한다** — 그 경우 남는 기록이 거짓이 된다.

---

## 6. 데몬 구조

### 파일 배치

| 파일 | 역할 | 상태 |
|---|---|---|
| `measurement.py` (최상위) | `MeasurementInput` · `OptionInput` 모델 + `delta_of()` 순수 함수 | 신규 |
| `record_rules.py` (최상위) | `kind` 4종의 필수 필드 검증. MCP·데몬이 함께 쓴다 | 신규 |
| `store/records.py` | `RecordRepository` — 기록·조회 SQL (`tech_option` 포함) | 신규 |
| `daemon/learning.py` | 기록 로직 (`recording.py` 의 자매) | 신규 |
| `daemon/derive.py` | `week_of()` / `week_bounds()` — 로드맵 시작일이 필요한 계산 | 신규 |
| `daemon/templates/records.html` | 목록 화면 | 신규 |
| `daemon/templates/record.html` | 상세 화면 | 신규 |
| `store/migrations.py` | `_V2` 추가, `CURRENT_VERSION = 2` | 수정 |
| `daemon/models.py` | `RecordRequest` (`MeasurementInput` 을 임포트) | 수정 |
| `daemon/routes_api.py` | `/v1/records` 3개 | 수정 |
| `daemon/routes_web.py` | `/records` 2개 + 삭제/복구 폼 2개 | 수정 |
| `daemon/templates/base.html` | `nav` 추가, CSS 클래스 몇 개 | 수정 |
| `daemon/absorb.py` | `_HANDLERS` 2종 추가 + 모르는 `kind` 처리 수정 | 수정 |
| `daemon/app.py` | `Context` 에 `records` 필드 추가, `_build_context` 에서 생성 | 수정 |
| `spool.py` | `KINDS` 에 봉투 4종 추가 | 수정 |
| `config.py` | `roadmap_start_date` + `load_or_create_daemon_config` 반환 형태 | 수정 |
| `mcp/client.py` | `_NO_SPOOL_STATUSES` 에서 `404` 제거 (§12 K2) | 수정 |
| `mcp/server.py` | 툴 6개 추가 (기존 4개는 그대로) | 수정 |

`Repository` 는 이미 483줄에 메서드 28개다.
여기에 기록 메서드를 더 넣는 대신 `RecordRepository` 를 따로 두고 `ctx.records` 로 노출한다.
`ctx.sessions` 가 이미 그렇게 분리돼 있어 기존 구조와 어긋나지 않는다.
`ctx` 는 `daemon/app.py` 의 `_build_context()` 가 만드는 dataclass다.
(`daemon/context.py` 는 이름이 비슷하지만 `get_today_context` 의 요약 빌더로, 무관하다.)

### 무엇을 최상위에 두고 무엇을 `daemon/` 에 두는가

`mcp/` 는 현재 `spool` · `clock` · `config` · `ids` 같은 **최상위 공용 모듈만** 임포트하고
`daemon/` 은 한 번도 임포트하지 않는다. 두 프로세스가 독립적이라는 사실이 임포트 방향에 드러나 있다.
그래서 **두 프로세스가 함께 쓰는 것만 최상위**에 둔다.

| 모듈 | 위치 | 누가 쓰나 | 왜 |
|---|---|---|---|
| `MeasurementInput` `OptionInput` | 최상위 `measurement.py` | MCP 툴 시그니처, `daemon/models.py` | 양쪽이 같은 모양을 알아야 한다 |
| `delta_of()` | 최상위 `measurement.py` | MCP(§5 SPOOL 경로), 데몬(반환값·화면) | 입력만으로 계산되는 순수 함수. 데몬 없이도 답이 같다 |
| `missing_fields()` | 최상위 `record_rules.py` | MCP(거절), 데몬(422) | 같은 규칙을 두 번 쓰면 문구가 갈라진다 (§7) |
| `week_of()` `week_bounds()` | `daemon/derive.py` | 데몬만 | `roadmap_start_date` 설정과 DB 질의가 필요하다. MCP 는 알 필요가 없다 |

`week` 계산만 데몬에 남는 이유는 그것만이 **설정에 의존**하기 때문이다.
개선률은 before/after 두 숫자면 끝나므로 어디서 계산해도 같은 값이 나온다.

### `spool.KINDS`

`spool.py` 의 `KINDS` 는 지금 어떤 코드도 참조하지 않는 상수지만,
봉투 종류를 열거한 유일한 자리다. 여기를 갱신하지 않으면
`_HANDLERS`(4종 → 8종)와 어긋난 채 남아 다음 사람을 속인다.
`record_experiment` · `record_troubleshooting` · `record_tech_choice` · `record_concept`
네 종을 더한다.

### HTTP 엔드포인트

```
POST /v1/records              기록 (kind 는 본문에)
GET  /v1/records              목록 (project, kind, topic, tag, week,
                                     since, until, missing, limit)
GET  /v1/records/{record_id}  상세
```

`/v1/*` 이므로 기존 토큰 인증(`require_token`)이 그대로 걸린다.

`week` 는 저장된 컬럼이 아니므로 **필터링 시 날짜 구간으로 변환해서** 질의한다.
`week=13` → `시작일 + 84일` 부터 7일간.
`roadmap_start_date` 가 없는데 `week` 필터가 오면 빈 목록을 돌려준다 (오류가 아니다).
`tag` 는 `tags_json` 에 대한 부분 일치로 거른다 — 태그 수가 20개 이하라 인덱스는 두지 않는다.
`topic` 은 정확히 일치로 거른다. 자유 문자열이므로 오타는 목록 화면에서 눈으로 잡는다.
`missing=interview` 는 `interview IS NULL OR interview = ''` 로 거른다 (`mitigation` 도 같다).

### 날짜 구간은 반드시 로컬 시간대로 만든다

`occurred_at` 은 UTC ISO 문자열(`2026-11-03T00:12:00.000Z`)로 저장된다.
그런데 `week` · `since` · `until` 은 **사람이 보는 로컬 날짜** 개념이다.
`"2026-11-03"` 을 그대로 `"2026-11-03T00:00:00.000Z"` 로 써서 비교하면
KST 기준 오전 9시 이전에 남긴 기록이 통째로 앞 구간으로 샌다.

경계는 예외 없이 기존 `clock.local_day_bounds(date_str)` 로 만든다.
이 함수는 "지금"이 아니라 **대상 날짜 자체의 오프셋**을 쓴다 (`dayview` 가 이미 이렇게 한다).

다만 이 함수의 **끝 경계는 서머타임에서 정확하지 않다** — 시작에 고정 24시간을 더한다
(§12 I5, 미해결). 한국 시간대에는 서머타임이 없어 이 로드맵에서는 드러나지 않지만,
새 코드가 이 결함을 더 넓게 퍼뜨리는 것이므로 알고 쓴다.
고치게 되면 `local_day_bounds` 한 곳만 고치면 `dayview` 와 `/records` 가 함께 낫는다.
그래서 여기서 별도 계산을 만들지 않고 굳이 이 함수를 부른다.

```python
def week_bounds(week: int, start_date: str | None) -> tuple[str, str] | None:
    """주차 → [시작 ISO, 끝 ISO). 시작일 미설정이면 None.

    시작일 + (week-1)*7 일의 로컬 자정부터 7일 뒤 로컬 자정까지.
    두 경계 모두 local_day_bounds 로 얻는다 — 직접 문자열을 잇지 않는다.
    """
```

`since` / `until` 도 같다. `until` 은 **그날을 포함**하도록
`local_day_bounds(until)[1]` (다음날 자정)을 배타적 상한으로 쓴다.
"11월 3일까지"라고 적은 사람은 3일에 남긴 기록을 보고 싶어 한다.

### 기록 흐름

`learning.record()` 는 `recording.record_checkpoint()` 와 같은 순서로 흐른다.

```
_register_client → _snapshot → ctx.sessions.attach → 한도 적용
    → insert (learning_record + measurement, 한 트랜잭션)
    → ctx.repo.touch_work
```

그래서 세션 자동 부착, git 스냅샷, 중복 방지(같은 `record_id` 재전송 시 `duplicate`)가
전부 따라온다. spool 흡수도 같은 함수를 부르므로 온라인·오프라인 경로가 갈라지지 않는다.

`measurement` 삽입은 `learning_record` 와 **같은 트랜잭션**이다.
지표 없는 실험 기록이 남는 중간 상태가 생기면 안 된다.

### `project` 유도

`snapshot.repo_name` 을 기록 시점에 그대로 넣어 고정한다.
저장소 밖에서 기록하면 `NULL` 이고 화면엔 "(저장소 없음)"으로 나온다.
나중에 저장소 이름이 바뀌어도 과거 기록의 소속은 흔들리지 않는다.

### `daemon/derive.py`

```python
def week_of(occurred_at: str, start_date: str | None) -> int | None:
    """로드맵 시작일 기준 주차. 시작일이 없거나 그보다 이른 기록이면 None.

    week = (로컬 날짜 - 시작일).days // 7 + 1
    상한 없음 — 31주를 넘어도 그대로 센다.
    """


def week_bounds(week: int, start_date: str | None) -> tuple[str, str] | None:
    """주차 → 질의용 [시작, 끝) UTC ISO. 위 §"날짜 구간" 참조."""
```

날짜 변환은 기존 `clock.local_date_of` / `clock.local_day_bounds` 를 쓴다.
`week_of` 와 `week_bounds` 는 서로의 역함수여야 한다 — 테스트로 못 박는다 (§9).

### `measurement.py` (최상위)

```python
class MeasurementInput(BaseModel):
    metric: str
    before: float
    after: float
    unit: str | None = None
    direction: str = "LOWER_IS_BETTER"


class OptionInput(BaseModel):
    name: str                  # "RabbitMQ"
    pros: str | None = None    # 장점
    cons: str | None = None    # 단점
    chosen: bool = False       # 정확히 하나만 True (§7)


def delta_of(before: float, after: float, direction: str) -> dict:
    """{change, percent, improved}

    percent  : before == 0 이면 None (0으로 나누지 않는다)
    improved : before == after 이면 None (변화 없음은 개선도 악화도 아니다)
               direction == "LOWER_IS_BETTER"  → after < before
               direction == "HIGHER_IS_BETTER" → after > before

    모르는 direction 문자열은 LOWER_IS_BETTER 로 본다 (기본값과 같게).
    """
```

`delta_of` 가 데몬이 아니라 여기 있는 덕분에 MCP 가 SPOOL 경로에서도
개선률을 채울 수 있다 (§5).

### 설정

`Settings` 에 `roadmap_start_date: str | None` 한 줄을 더한다.
우선순위는 기존과 같이 `WARRURU_ROADMAP_START_DATE` 환경변수 >
`config/daemon.json` 의 `roadmap_start_date` > `None`.

`Settings` 는 한 줄이지만 `config.py` 수정은 두 자리다.
지금 `load_or_create_daemon_config()` 는 `(token, port)` **튜플만** 돌려주므로
파일에서 세 번째 값을 꺼내려면 이 함수의 반환 형태를 바꿔야 한다.
설정 파일이 앞으로 더 늘어날 자리이므로 `dict` 를 돌려주도록 고치고
`load_settings()` 에서 `.get()` 으로 꺼낸다. 없는 키는 `None` 이다.
파일을 새로 만들 때 `roadmap_start_date` 를 쓰지는 않는다 —
설정하지 않은 상태가 정상이기 때문이다.

기본값이 `None` 이라 **설정하지 않으면 주차 기능이 조용히 꺼진다.**
이 도구를 로드맵과 무관하게 써도 된다.

이 로드맵의 시작일은 `2026-08-12` 다.

---

## 7. 오류 처리

기존 두 원칙을 따른다: *상한을 넘는 값은 자른다*, *툴은 예외를 밖으로 던지지 않는다*.
여기에 하나를 더한다: **필수 필드는 거절한다.**

| 상황 | 처리 |
|---|---|
| 필수 필드 누락 | MCP 단계에서 거절. `{ok: false, storage: "NONE"}` + 무엇이 빠졌는지 메시지에 명시. spool 에 넣지 않음 |
| `kind` 별 필수 위반 (예: `cause` 빈 트러블슈팅) | 위와 동일 |
| 같은 요청이 API 로 직접 들어옴 | 데몬도 같은 규칙으로 `422`. `_NO_SPOOL_STATUSES` 에 422가 있어 클라이언트는 spool 하지 않는다 |
| 빈 리스트 `measurements=[]` / 공백뿐인 문자열 | **누락으로 본다.** 아래 참조 |
| `options` 가 2개 미만 | 거절. "후보를 2개 이상 적어야 선택 기록이 된다" |
| `chosen` 이 0개이거나 2개 이상 | 거절. 무엇을 골랐는지 모르는 기록은 쓸 수 없다 |
| `options` 8개 초과 | 자름. 단, 잘린 쪽에 `chosen` 이 있으면 **거절** |
| `mitigation` · `interview` 비어 있음 | **거절하지 않는다.** 저장하고 화면에 배지를 붙인다 (§8) |
| `topic` 오타 (`NETWROK`) | 그대로 저장. 자유 문자열이라 검증하지 않는다. 목록 화면에서 눈에 띈다 |
| `evidence` 상한 초과 | 자르고 `evidence_truncated=1`, 메시지로 알림 (거절 아님) |
| 그 외 문자열 상한 초과 | 자름 (기존 `limits` 관례) |
| `measurements` 10개 초과 | 앞 10개만 남기고 자름 + **메시지로 몇 개를 버렸는지 알림** (`tags` 관례와 같음) |
| 모르는 `direction` 문자열 | `LOWER_IS_BETTER` 로 보고 진행. 거절하지 않음 |
| 데몬 못 닿음 | 기존 spool. `storage="SPOOL"`. 검증은 이미 통과했으므로 흡수 시점에 다시 실패하지 않음 |
| `before == 0` | `percent = None`. 값 자체는 그대로 표시 |
| `before == after` | `improved = None`. 화살표 없이 값만 |
| `roadmap_start_date` 미설정 | `week = None`. 정상 동작 |
| `roadmap_start_date` 형식 오류 | `week = None`, 기동은 계속. 로그 경고 1회 |
| `occurred_at` 형식 오류 | 기록 경계에서 정규화하고, 실패하면 **현재 시각으로 대체**. 거절하지 않음 (§12 I2) |
| 모르는 spool `kind` | dead-letter 로 이동 (아래 참조) |
| 구버전 데몬이 v2 DB 를 염 | `migrate()` 가 아무것도 안 하고 넘어감. v1 테이블만 쓰므로 무해. 그대로 둔다 |
| **구버전 데몬에 `/v1/records` 요청** | 데몬이 404. 지금은 spool 없이 버려진다 → 이번에 고친다 (§12 K2) |

### 왜 MCP 단계에서 거절하는가

`record_checkpoint` 는 모르는 `type` 을 거절하지 않고 `NOTE` 로 낮춰 담는다(관대함).
새 툴은 반대로 간다. 이유는 두 가지다.

첫째, 체크포인트는 부수적 기록이라 반쯤 빈 것도 없는 것보단 낫지만,
실험 기록은 이 도구의 존재 이유라 `cause` 가 빈 트러블슈팅은 없느니만 못하다.

둘째, 데몬이 꺼져 있을 때 검증 없이 spool 에 넣으면
흡수 시점에야 실패해서 dead-letter 로 간다.
그때는 에이전트가 이미 사라진 뒤라 아무도 고칠 수 없다.
거절은 에이전트가 살아 있을 때 해야 고칠 수 있다.

### 그래도 데몬에서 한 번 더 검증한다

MCP 가 유일한 입구는 아니다. `POST /v1/records` 는 토큰만 있으면
누구나(다음 세션의 스크립트, curl, 나중에 붙일 다른 어댑터) 부를 수 있다.
데몬이 검증하지 않으면 `cause` 없는 트러블슈팅이 DB 에 들어가고,
그건 §7 첫 문단에서 막으려던 바로 그 상태다.

두 곳에서 검증해도 **spool 이 이중으로 실패하지 않는다.**
`mcp/client.py` 의 `_NO_SPOOL_STATUSES` 가 422 응답을 이미 spool 대상에서 빼고 있기 때문이다.
(이번에 이 집합에서 `404` 만 뺀다 — §12 K2. `400` · `401` · `422` 는 그대로 둔다.)

대신 규칙은 최상위 `record_rules.py` 한 군데에만 적는다.

```python
def missing_fields(kind: str, values: dict) -> list[str]:
    """비어 있는 필수 필드 이름 목록. 빈 리스트면 통과."""
```

MCP 는 이 결과로 거절 메시지를 만들고, 데몬은 같은 결과로 422 본문을 만든다.
규칙을 두 번 적으면 두 문구가 갈라지고, 갈라진 뒤에는 어느 쪽이 옳은지 알 수 없다.

**검증은 두 입구(`mcp/server.py` · `routes_api.py`)에만 두고
`learning.record()` 안에서는 하지 않는다.** 흡수 경로가 같은 함수를 부르기 때문이다.
안쪽에 검증을 두면, 이미 입구를 통과해 spool 에 들어간 기록이
흡수 시점에 다시 걸려 dead-letter 로 갈 여지가 생긴다.
그건 §7이 애초에 막으려던 상황이다 (아무도 고칠 수 없는 실패).

### 무엇을 "누락"으로 보는가

타입 검사만으로는 부족하다. `measurements=[]` 는 `list[MeasurementInput]` 을
만족하고, `cause="   "` 는 `str` 을 만족한다. 둘 다 통과시키면
"실험인데 측정값이 없다"는 기록이 그대로 남는다.

- 문자열: `strip()` 한 결과가 빈 문자열이면 누락
- 리스트: 길이 0이면 누락 (`EXPERIMENT` 의 `measurements`)
- 저장할 때도 `strip()` 한 값을 넣는다 — 화면에서 앞뒤 공백이 보이지 않게

### 같이 고치는 기존 결함

`absorb.py` 의 `_apply_file()` 은 모르는 봉투 `kind` 를 만나면
경고만 남기고 `continue` 한다. 그 봉투는 `remaining` 에도 `dead` 에도 안 들어가서
파일이 그대로 `absorbed/` 로 옮겨지며 **조용히 사라진다.**

지금 봉투 종류를 2개 늘리는 참이라
구버전 데몬 + 신버전 MCP 조합에서 바로 터질 수 있다.
모르는 `kind` 는 dead-letter 로 보내도록 이번에 함께 고친다.

---

## 8. 웹 화면 `/records`

기존 화면과 같은 방식이다. Jinja2 서버 렌더링, JavaScript 없음,
`base.html` 의 인라인 CSS 에 클래스 몇 개만 더한다.

```
GET  /records                      목록 + 필터
GET  /records/{record_id}          상세
POST /web/records/{id}/delete      soft delete (기존 _check_token 폼 토큰)
POST /web/records/{id}/restore
```

`base.html` 에 `nav` 를 넣어 날짜 화면(`/d/{date}`)과 기록 화면을 오갈 수 있게 한다.
지금 `nav a` CSS 는 이미 있는데 정작 `nav` 가 없다.

### 목록

필터는 GET 폼(`project` / `kind` / `topic` / `week` / `tag` / 기간 / `missing`)이고
querystring 에 그대로 남아 URL 을 북마크할 수 있다.
`?missing=interview` 는 **복습 큐**가 된다 — 면접 문장이 아직 없는 기록만 나온다.

종류마다 목록 한 줄의 요약이 다르다. 그 종류에서 가장 먼저 보고 싶은 것을 보여준다.

```
산책온 · 실험 · 13주차                 2026-11-03 (main @ a3f9c21)
추천 목록 N+1 제거
  query_count    102 → 3        ↓ 97%
  p95_latency  1800 → 220 ms    ↓ 88%
#jpa #n+1                                    [상세] [삭제]

StackUp · 기술 선택 · 17주차           2026-12-08 (main @ 7c1e02b)
비동기 메시징: RabbitMQ vs Kafka
  후보 2개 → RabbitMQ 선택
  근거: 재처리보다 개별 ACK 와 DLQ 가 먼저 필요했다
  ⚠ 보완책 없음                              [상세] [삭제]

CS · 개념 · DB · 4주차                 2026-09-02
격리 수준과 팬텀 리드
  확인: MySQL 에서 두 세션으로 재현
  ⚠ 면접 문장 없음                           [상세] [삭제]
```

지표가 3개를 넘으면 목록에서는 2개만 보이고 "+2개"로 접는다.
`direction` 을 반영해 처리량 증가는 `↑` 개선으로 표시하고,
`improved` 가 `None`(변화 없음)이면 화살표 없이 값만 쓴다.

**배지 두 개가 이 화면의 일이다.**
`⚠ 보완책 없음`(기술 선택)과 `⚠ 면접 문장 없음`(4종 공통)은
거절 대신 고른 방식이다 (§4). 목록을 훑을 때 채울 곳이 바로 보여야 한다.

### 상세

필드 순서를 **면접 서사 6단계와 같은 순서**로 놓고, 마지막에 면접 문장을 둔다.
어떤 컬럼이 어느 라벨에 붙는지는 §4 매핑표를 따른다.

| 화면 라벨 | 실험 | 트러블슈팅 | 기술 선택 | CS 개념 |
|---|---|---|---|---|
| 문제 | 문제 | 증상 | 무엇을 정해야 했나 | 왜 봤나 |
| 선택 | 가설 | 원인 | **후보 표** + 선택 근거 | — |
| 구현 | 무엇을 바꿨나 | 해결 방법 | 단점 보완 | 어떻게 확인했나 |
| 측정 | 지표 표 | 있으면 | 있으면 | — |
| 결과 | 결론 | 결론 | 도입 후 | 핵심 정리 |
| 한계 | 한계 | 한계 | 남은 한계 | 아직 모르는 것 |
| **면접에서 이렇게 말한다** | 공통 | 공통 | 공통 | 공통 |

기술 선택의 **후보 표**는 이 화면의 핵심이다.

```
후보          장점                        단점                      선택
RabbitMQ     개별 ACK, DLQ 가 기본       처리량 한계, 재처리 불편    ●
Kafka        높은 처리량, 재처리 가능     오프셋 운영 부담, 무겁다    ○
```

고른 것에 표시가 붙고, 바로 아래에 "왜 이걸 골랐나"와 "단점을 어떻게 보완했나"가 온다.
이 세 덩어리가 붙어 있어야 면접 답변 한 문단이 된다.

그 아래에 근거(`evidence` 를 `<pre>` 원문으로)와
맥락(저장소·브랜치·커밋, 소속 작업 → `/d/{date}` 링크)을 둔다.

이렇게 두면 31주차에 이 화면을 위에서 아래로 읽는 것만으로 서사가 나온다.

### 빈 상태

"아직 기록이 없습니다" 아래에 툴 4개의 호출 예시를 한 줄씩 넣는다.
이 화면을 처음 여는 시점은 툴 사용법을 모를 때이기도 하다.

### 삭제

soft delete 로, 체크포인트와 같다. `deleted_at` 이 찍히고 `?deleted=1` 로 볼 수 있다.

돌아갈 곳은 **누르기 직전에 보고 있던 목록**이다.
기존 체크포인트 폼은 hidden `date` 를 받아 `/d/{date}` 로 돌아가는데,
기록 목록은 날짜가 아니라 필터 조합(`project` · `kind` · `topic` · `week` · `tag`)이 화면을 정한다.
그래서 폼에 현재 쿼리스트링을 hidden `back` 으로 실어 보내고 거기로 302 한다.
없으면 `/records` 로 간다.

`back` 은 사용자가 보낸 값이므로 **`/records` 로 시작하는 상대 경로만 허용**한다.
그렇지 않으면 다른 사이트로 튕겨 보내는 리다이렉트가 된다.
`_check_token` 이 같은 이유(다른 출처의 조작 차단)로 이미 붙어 있으니 그 옆에 둔다.

---

## 9. 테스트

기존 `local/tests/` 배치를 따라 파일을 나눈다.

| 파일 | 확인할 것 |
|---|---|
| `test_migrations.py` (확장) | v1 데이터가 든 DB 를 v2 로 올려도 기존 work/checkpoint 가 보존됨 |
| `test_measurement.py` (신규) | `delta_of` 경계 (아래), 모르는 `direction` 처리 |
| `test_record_rules.py` (신규) | `kind` **4종**의 누락 판정, 빈 리스트·공백 문자열, 후보 2개 미만, `chosen` 0개·2개, 메시지에 필드 이름이 들어감 |
| `test_derive.py` (신규) | `week_of` 경계 (아래) / `week_bounds` 시간대 / 둘이 서로의 역함수인지 |
| `test_records_repository.py` (신규) | 삽입, 중복(`record_id` 재전송), 필터 조합(`topic` · `missing` 포함), 후보 순서·`chosen` 보존, soft delete·restore |
| `test_learning_record.py` (신규) | 세션 자동 부착, git 스냅샷 채워짐, 한도 적용, `touch_work` 호출, 트랜잭션 원자성 |
| `test_mcp_learning_tools.py` (신규) | 툴 4종 각각의 정상 기록, 필수 필드 누락이 **spool 을 만들지 않고** 거절되는지, **데몬 꺼짐 시 SPOOL 반환에 개선률이 들어감**, `missing=interview` 조회 |
| `test_api_records.py` (신규) | 토큰 없으면 401, 필수 필드 없으면 422, 목록 필터, 없는 id 는 404 |
| `test_web_records.py` (신규) | 4종 목록·상세 렌더, 후보 표와 선택 표시, **배지 2종**, 빈 상태, 개선률 표시(↑/↓/없음), 삭제 폼 토큰, `back` 복귀와 외부 URL 거부 |
| `test_spool.py` (확장) | 새 봉투 4종이 `KINDS` 와 `_HANDLERS` 양쪽에 있는지 |
| `test_mcp_client.py` (확장) | **404 응답이 spool 로 떨어지는지** (§12 K2). 400·401·422 는 그대로 spool 없음 |
| `test_config.py` (확장) | `roadmap_start_date` 우선순위(환경변수 > 파일 > None), 기존 token·port 가 그대로 읽히는지 |
| `test_absorb.py` (확장) | 새 `kind` 4종 흡수, 모르는 `kind` → dead-letter |
| `test_acceptance.py` (확장) | MCP 로 실험 기록 → `/records` 화면에 `-88%` 가 뜰 때까지 한 줄로. 기술 선택 기록 → 후보 표가 화면에 뜨는지 |

### 못 박아 두는 경계값

`week_of` 는 off-by-one 이 나기 딱 좋은 자리다. 시작일 `2026-08-12` 기준:

| 기록 날짜 | 기대 `week` |
|---|---|
| `2026-08-11` (하루 전) | `None` |
| `2026-08-12` (당일) | `1` |
| `2026-08-18` (+6일) | `1` |
| `2026-08-19` (+7일) | `2` |
| `2027-03-17` (+217일) | `32` (상한 없음) |
| 시작일 미설정 | `None` |

`delta_of`:

| before | after | direction | change | percent | improved |
|---|---|---|---|---|---|
| 1800 | 220 | LOWER | -1580 | -87.78 | `True` |
| 1200 | 3400 | HIGHER | +2200 | +183.33 | `True` |
| 1200 | 3400 | LOWER | +2200 | +183.33 | `False` |
| 0 | 5 | LOWER | +5 | `None` | `False` |
| 100 | 100 | LOWER | 0 | 0.0 | `None` |

`week_bounds` 의 시간대. UTC 가 아닌 시간대를 고정하고 확인한다
(`TZ=Asia/Seoul`. 시스템 시간대에 따라 통과 여부가 갈리는 테스트는 테스트가 아니다):

| 기록 `occurred_at` (UTC) | 로컬(KST) | `week=1` 구간에 |
|---|---|---|
| `2026-08-11T15:30:00Z` | 08-12 00:30 | **든다** (1주차 첫날) |
| `2026-08-11T14:30:00Z` | 08-11 23:30 | 안 든다 (시작 전) |
| `2026-08-18T14:59:00Z` | 08-18 23:59 | **든다** (1주차 마지막) |
| `2026-08-18T15:00:00Z` | 08-19 00:00 | 안 든다 (2주차) |

경계를 UTC 자정으로 잡으면 첫 줄과 셋째 줄이 반대로 나온다.
`until=2026-08-18` 로 조회했을 때 셋째 줄이 나오는지도 같이 본다.

---

## 10. 이번에 하지 않는 것

명시적으로 범위 밖이다. 지금 넣으면 "명세만 쌓임"으로 되돌아간다.

- 사람이 웹 폼으로 직접 기록 입력
- LLM 요약, 블로그 초안 생성
- 커리큘럼 31주 테이블과 진도 추적
- **분야별 커버리지 대시보드** ("이번 주 OS 가 비었다" 같은 집계).
  `topic` 필터로 눈으로 확인하는 것까지가 이번 범위다
- **면접 예상 질문·답 목록** — `interview` 한 문단으로 시작한다.
  Q/A 를 여러 개 다는 것은 다음 조각
- 노션 로드맵 동기화
- 대상 저장소에 마크다운 미러
- `get_today_context` 에 학습 기록 섞기
- RAG 인덱싱 (Qdrant)
- **목록 페이징** — `limit`(기본 20 · 상한 100)만 둔다. 필터로 좁히는 것이 먼저다.
  31주가 지나 한 화면에 안 들어오면 그때 넣는다
- **기록 수정** — 잘못 남겼으면 지우고 다시 남긴다. soft delete 로 충분하다

이 중 여럿은 다음 조각 후보다.

---

## 11. 완료 기준

1. `pytest` 가 기존 25개 파일 포함 전부 통과한다.
2. v1 데이터가 있는 실제 `~/.warruru/warruru.db` 가 v2 로 올라가고 기존 기록이 보존된다.
3. 산책온 또는 StackUp 저장소에서 Claude Code 로 `record_experiment` 를 불러
   기록이 남고, 반환값에 개선률이 포함된다.
4. `http://127.0.0.1:8787/records` 에서 그 기록이 프로젝트·주차와 함께 보인다.
5. 데몬을 끈 상태로 기록해도 spool 에 남고, 데몬을 켜면 흡수돼 화면에 나타난다.
   이때도 **반환값에 개선률이 들어 있다** (`week` · `project` 는 `None`).
6. 필수 필드를 빠뜨린 호출이 거절되고, spool 파일이 만들어지지 않는다.
   같은 요청을 `POST /v1/records` 로 직접 보내면 `422` 가 온다.
7. `TZ=Asia/Seoul` 로 §9의 시간대 경계 4줄이 통과한다.
8. 기술 선택을 기록하면 `/records` 상세에 **후보 표**가 뜨고 고른 것에 표시가 붙는다.
   후보를 하나만 넣은 호출은 거절된다.
9. CS 개념을 분야와 함께 기록하면 `?topic=DB` 로 그것만 골라 볼 수 있다.
10. `?missing=interview` 가 면접 문장이 비어 있는 기록만 돌려준다.

---

## 12. 기존 미해결 결함과의 관계

`local/docs/OUTSTANDING.md`(2026-07-23)에 남아 있는 결함 중
이 기능이 **지나가는 자리에 있는 것들**이다. 새 코드가 같은 함정을 다시 밟거나,
결함의 영향 범위를 넓히는 쪽이면 여기서 정한다.

| # | 결함 | 이번 조치 |
|---|---|---|
| C1 계열 | `absorb.py` 가 모르는 봉투 `kind` 를 조용히 버린다 | **고친다.** 봉투를 2종 늘리는 참이라 바로 터진다 (§7) |
| K2 | `404` 가 spool 없이 버려진다 (`_NO_SPOOL_STATUSES`) | **고친다.** `/v1/records` 는 구버전 데몬에 없다 → 404 → 유실. 404를 제외 목록에서 뺀다 |
| I2 | `occurred_at` 이 검증 없이 저장돼 화면을 500 으로 만든다 | **새 경로에서만 막는다.** `learning.record()` 가 정규화하고 실패 시 현재 시각 (§7). 기존 `record_checkpoint` 는 건드리지 않는다 |
| I4 | `attach` 가 귀속을 "지금" 기준으로 본다 | **받아들인다.** 소속 작업 링크만 어긋나고 기록·조회는 온전하다 (§4) |
| I5 | `local_day_bounds` 의 끝 경계가 서머타임에서 틀리다 | **받아들이고 같은 함수를 쓴다.** 한 곳을 고치면 두 화면이 함께 낫는다 (§6) |
| K7 | 데몬이 거절한 요청을 `storage="DAEMON"` 으로 보고한다 | **범위 밖.** MCP 검증이 먼저 거르므로 실사용 경로에서는 드러나지 않는다. 열거값에 "거절"을 넣는 일은 별도 조각 |

C1 · K2 두 건만 고치는 기준은 하나다 — **이 기능이 그 결함을 실제로 밟는가.**
봉투 종류가 늘어나고 엔드포인트가 늘어나므로 두 건은 밟는다.
나머지는 이 기능 없이도 있던 문제라 여기서 같이 처리하지 않는다.

K2 를 고치면 경로 오타 같은 영구적 404 도 spool 에 쌓인다.
그 경우는 `MAX_ATTEMPTS`(5) 뒤에 dead-letter 로 격리되므로
"조용한 유실" 대신 "시끄러운 격리"가 된다. 그쪽이 낫다.
