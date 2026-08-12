# 학습 기록 (Learning Record) 설계

**작성일:** 2026-08-12
**대상:** `local/` (warruru-local) — 마이그레이션 v2
**상태:** 설계 승인됨. 구현 계획 작성 전.

---

## 1. 왜 만드는가

2027년 3월 공채를 목표로 한 31주 백엔드·인프라 로드맵(2026-08-12 시작)을 수행하면서,
산책온·StackUp 두 프로젝트에서 성능 개선과 장애 해결이 계속 발생한다.
N+1 개선 전후의 쿼리 수, Redis 적용 전후의 p95 같은 **측정값이 붙은 기록**을
지금 남길 곳이 없다.

31주차 면접 서사는 "문제 → 선택 → 구현 → 측정 → 결과 → 한계" 순서로 설명해야 하는데,
그 재료가 바로 이 기록들이다. 지금 남기지 않으면 나중에 복원할 수 없다.
숫자는 기억에 남지 않는다.

### 이 조각이 끝나면 할 수 있는 일

- 산책온/StackUp 에서 Claude Code·Codex 로 작업하다가, 개선을 마친 자리에서
  에이전트에게 "이거 기록해 줘" 하면 측정값과 함께 남는다.
- `http://127.0.0.1:8787/records` 에서 프로젝트별·주차별로 훑어본다.
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
체크포인트는 *작업 중의 순간*이고 학습 기록은 *검증된 개선*이다.
수명도 다르다 — 체크포인트는 그날 지나면 잘 안 보지만
학습 기록은 31주차에 다시 읽는다.

---

## 3. 확정된 설계 결정

| 결정 | 내용 | 근거 |
|---|---|---|
| 필수 필드 | 핵심만 강제, 나머지는 선택 | 기록 마찰이 크면 실제로 안 남긴다. 결론·한계는 기록 시점에 모를 수 있다 |
| 기록 종류 | MCP 툴 2개 / 테이블 1개 | MCP JSON Schema 는 "조건부 필수"를 표현하지 못한다. 툴을 나눠야 에이전트에게 명확하다 |
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
    title          TEXT NOT NULL,   -- 한 줄 요약. 목록 화면이 읽는 값
    problem        TEXT NOT NULL,   -- 실험: 문제 / 트러블슈팅: 증상
    hypothesis     TEXT,            -- 실험: 왜 그렇게 판단했나
    cause          TEXT,            -- 트러블슈팅: 원인
    action         TEXT,            -- 실험: 무엇을 바꿨나 / 트러블슈팅: 해결 방법
    outcome        TEXT,            -- 결론
    limitation     TEXT,            -- 한계
    evidence       TEXT,            -- EXPLAIN·SQL·로그 원문
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
```

### 필수 필드

DB 레벨에서는 `title` / `problem` 만 `NOT NULL` 이다.
`cause` 와 `action` 은 트러블슈팅에만 필수이므로 컬럼은 NULL 을 허용하고
**검증은 MCP 단계에서** 한다 (§7).

| kind | 필수 |
|---|---|
| `EXPERIMENT` | `title`, `problem`, `measurements` 1개 이상 |
| `TROUBLESHOOTING` | `title`, `problem`(증상), `cause`, `action`(해결) |

`title` 은 애초 정한 핵심 필드보다 하나 많다.
목록 화면과 서사 조립이 실제로 읽는 값이고,
없으면 `problem` 을 잘라 써야 하는데 그건 눈에 띄게 나쁘다.

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

---

## 5. MCP 툴 표면

기존 서버(`mcp/server.py`)에 툴 4개를 더한다. 기존 4개는 그대로 둔다.

```python
class MeasurementInput(BaseModel):
    metric: str                       # "p95_latency"
    before: float
    after: float
    unit: str | None = None           # "ms"
    direction: str = "LOWER_IS_BETTER"  # 또는 "HIGHER_IS_BETTER"


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
def list_records(
    project: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    week: int | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 20,
) -> dict:
    """남긴 실험·트러블슈팅 기록을 조건으로 찾는다. 본문은 요약만 돌려준다."""


@server.tool()
def get_record(record_id: str) -> dict:
    """기록 하나의 전체 내용을 읽는다. evidence 원문까지 포함한다."""
```

`measurements` 를 `list[dict]` 가 아니라 pydantic 모델로 받는 이유는,
FastMCP 가 이걸 JSON Schema 로 내보내서 **에이전트가 필드 이름을 추측하지 않게** 되기 때문이다.
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

`list_records` 는 `evidence` 를 뺀 요약 목록을 돌려주고,
`get_record` 는 전체를 돌려준다. 컨텍스트를 아끼기 위한 구분이다.

### 한도 (`limits.py`)

기존 상수를 그대로 쓰고 필요한 것만 더한다.

| 대상 | 상한 | 상수 |
|---|---|---|
| `title` | 200자 | `TITLE_MAX` (기존) |
| `problem` `hypothesis` `cause` `action` `outcome` `limitation` | 4096자 | `TEXT_MAX` (기존) |
| `evidence` | 65536자 | `BODY_MAX` (기존) |
| `tags` | 20개 | `TAGS_MAX` (기존) |
| `measurements` | 10개 | `MEASUREMENTS_MAX` (신규) |

---

## 6. 데몬 구조

### 파일 배치

| 파일 | 역할 | 상태 |
|---|---|---|
| `measurement.py` (최상위) | `MeasurementInput` pydantic 모델 | 신규 |
| `store/records.py` | `RecordRepository` — 기록·조회 SQL | 신규 |
| `daemon/learning.py` | 기록 로직 (`recording.py` 의 자매) | 신규 |
| `daemon/derive.py` | `week` / 개선률 계산 (순수 함수) | 신규 |
| `daemon/templates/records.html` | 목록 화면 | 신규 |
| `daemon/templates/record.html` | 상세 화면 | 신규 |
| `store/migrations.py` | `_V2` 추가, `CURRENT_VERSION = 2` | 수정 |
| `daemon/models.py` | `RecordRequest` (`MeasurementInput` 을 임포트) | 수정 |
| `daemon/routes_api.py` | `/v1/records` 3개 | 수정 |
| `daemon/routes_web.py` | `/records` 2개 + 삭제/복구 폼 2개 | 수정 |
| `daemon/templates/base.html` | `nav` 추가, CSS 클래스 몇 개 | 수정 |
| `daemon/absorb.py` | `_HANDLERS` 2종 추가 + 모르는 `kind` 처리 수정 | 수정 |
| `daemon/app.py` | `Context` 에 `records` 필드 추가, `_build_context` 에서 생성 | 수정 |
| `config.py` | `roadmap_start_date` | 수정 |
| `mcp/server.py` | 툴 4개 | 수정 |

`Repository` 는 이미 483줄에 메서드 28개다.
여기에 기록 메서드를 더 넣는 대신 `RecordRepository` 를 따로 두고 `ctx.records` 로 노출한다.
`ctx.sessions` 가 이미 그렇게 분리돼 있어 기존 구조와 어긋나지 않는다.
`ctx` 는 `daemon/app.py` 의 `_build_context()` 가 만드는 dataclass다.
(`daemon/context.py` 는 이름이 비슷하지만 `get_today_context` 의 요약 빌더로, 무관하다.)

### `MeasurementInput` 을 최상위에 두는 이유

`mcp/` 는 현재 `spool` · `clock` · `config` · `ids` 같은 **최상위 공용 모듈만** 임포트하고
`daemon/` 은 한 번도 임포트하지 않는다. 두 프로세스가 독립적이라는 사실이 임포트 방향에 드러나 있다.
`MeasurementInput` 을 `daemon/models.py` 에 두면 이 경계가 깨지므로
최상위 `measurement.py` 에 두고 MCP 서버와 `daemon/models.py` 가 각자 임포트한다.

### HTTP 엔드포인트

```
POST /v1/records              기록 (kind 는 본문에)
GET  /v1/records              목록 (project, kind, tag, week, since, until, limit)
GET  /v1/records/{record_id}  상세
```

`/v1/*` 이므로 기존 토큰 인증(`require_token`)이 그대로 걸린다.

`week` 는 저장된 컬럼이 아니므로 **필터링 시 날짜 구간으로 변환해서** 질의한다.
`week=13` → `시작일 + 84일 <= occurred_at < 시작일 + 91일`.
`roadmap_start_date` 가 없는데 `week` 필터가 오면 빈 목록을 돌려준다 (오류가 아니다).
`tag` 는 `tags_json` 에 대한 부분 일치로 거른다 — 태그 수가 20개 이하라 인덱스는 두지 않는다.

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

### `derive.py`

```python
def week_of(occurred_at: str, start_date: str | None) -> int | None:
    """로드맵 시작일 기준 주차. 시작일이 없거나 그보다 이른 기록이면 None.

    week = (로컬 날짜 - 시작일).days // 7 + 1
    상한 없음 — 31주를 넘어도 그대로 센다.
    """


def delta_of(before: float, after: float, direction: str) -> dict:
    """{change, percent, improved}

    percent  : before == 0 이면 None (0으로 나누지 않는다)
    improved : before == after 이면 None (변화 없음은 개선도 악화도 아니다)
               direction == "LOWER_IS_BETTER"  → after < before
               direction == "HIGHER_IS_BETTER" → after > before
    """
```

날짜 변환은 기존 `clock.local_date_of` 를 쓴다.

### 설정

`Settings` 에 `roadmap_start_date: str | None` 한 줄을 더한다.
우선순위는 기존과 같이 `WARRURU_ROADMAP_START_DATE` 환경변수 >
`config/daemon.json` 의 `roadmap_start_date` > `None`.

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
| `evidence` 상한 초과 | 자르고 `evidence_truncated=1`, 메시지로 알림 (거절 아님) |
| 그 외 문자열 상한 초과 | 자름 (기존 `limits` 관례) |
| 데몬 못 닿음 | 기존 spool. `storage="SPOOL"`. 검증은 이미 통과했으므로 흡수 시점에 다시 실패하지 않음 |
| `before == 0` | `percent = None`. 값 자체는 그대로 표시 |
| `before == after` | `improved = None`. 화살표 없이 값만 |
| `roadmap_start_date` 미설정 | `week = None`. 정상 동작 |
| `roadmap_start_date` 형식 오류 | `week = None`, 기동은 계속. 로그 경고 1회 |
| 모르는 spool `kind` | dead-letter 로 이동 (아래 참조) |
| 구버전 데몬이 v2 DB 를 염 | `migrate()` 가 아무것도 안 하고 넘어감. v1 테이블만 쓰므로 무해. 그대로 둔다 |

### 왜 MCP 단계에서 거절하는가

`record_checkpoint` 는 모르는 `type` 을 거절하지 않고 `NOTE` 로 낮춰 담는다(관대함).
새 툴은 반대로 간다. 이유는 두 가지다.

첫째, 체크포인트는 부수적 기록이라 반쯤 빈 것도 없는 것보단 낫지만,
실험 기록은 이 도구의 존재 이유라 `cause` 가 빈 트러블슈팅은 없느니만 못하다.

둘째, 데몬이 꺼져 있을 때 검증 없이 spool 에 넣으면
흡수 시점에야 실패해서 dead-letter 로 간다.
그때는 에이전트가 이미 사라진 뒤라 아무도 고칠 수 없다.
거절은 에이전트가 살아 있을 때 해야 고칠 수 있다.

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

필터는 GET 폼(`project` / `kind` / `week` / `tag` / 기간)이고
querystring 에 그대로 남아 URL 을 북마크할 수 있다.

```
산책온 · 실험 · 13주차              2026-11-03 (main @ a3f9c21)
추천 목록 N+1 제거
  query_count    102 → 3        ↓ 97%
  p95_latency  1800 → 220 ms    ↓ 88%
#jpa #n+1                              [상세] [삭제]
```

지표가 3개를 넘으면 목록에서는 2개만 보이고 "+2개"로 접는다.
`direction` 을 반영해 처리량 증가는 `↑` 개선으로 표시하고,
`improved` 가 `None`(변화 없음)이면 화살표 없이 값만 쓴다.

### 상세

필드 순서를 **면접 서사 6단계와 같은 순서**로 놓는다.

| 화면 라벨 | 실험 | 트러블슈팅 |
|---|---|---|
| 문제 | `problem` | `problem` (증상) |
| 선택 | `hypothesis` | `cause` (원인) |
| 구현 | `action` | `action` (해결) |
| 측정 | `measurements` 표 (before / after / 변화 / 개선) | 같음 (있으면) |
| 결과 | `outcome` | `outcome` |
| 한계 | `limitation` | `limitation` |

그 아래에 근거(`evidence` 를 `<pre>` 원문으로)와
맥락(저장소·브랜치·커밋, 소속 작업 → `/d/{date}` 링크)을 둔다.

이렇게 두면 31주차에 이 화면을 위에서 아래로 읽는 것만으로 서사가 나온다.

### 빈 상태

"아직 기록이 없습니다" 아래에 `record_experiment` 호출 예시를 한 줄 넣는다.
이 화면을 처음 여는 시점은 툴 사용법을 모를 때이기도 하다.

### 삭제

soft delete 로, 체크포인트와 같다. `deleted_at` 이 찍히고 `?deleted=1` 로 볼 수 있다.

---

## 9. 테스트

기존 `local/tests/` 배치를 따라 파일을 나눈다.

| 파일 | 확인할 것 |
|---|---|
| `test_migrations.py` (확장) | v1 데이터가 든 DB 를 v2 로 올려도 기존 work/checkpoint 가 보존됨 |
| `test_derive.py` (신규) | `week_of` 경계 / `delta_of` 경계 (아래) / `week` → 날짜 구간 역변환 |
| `test_records_repository.py` (신규) | 삽입, 중복(`record_id` 재전송), 필터 조합, soft delete·restore |
| `test_learning_record.py` (신규) | 세션 자동 부착, git 스냅샷 채워짐, 한도 적용, `touch_work` 호출, 트랜잭션 원자성 |
| `test_mcp_learning_tools.py` (신규) | 필수 필드 누락이 **spool 을 만들지 않고** 거절되는지, 정상 기록, `list_records` / `get_record` |
| `test_api_records.py` (신규) | 토큰 없으면 401, 목록 필터, 없는 id 는 404 |
| `test_web_records.py` (신규) | 목록·상세 렌더, 빈 상태, 개선률 표시(↑/↓/없음), 삭제 폼 토큰 |
| `test_absorb.py` (확장) | 새 `kind` 2종 흡수, 모르는 `kind` → dead-letter |
| `test_acceptance.py` (확장) | MCP 로 실험 기록 → `/records` 화면에 `-88%` 가 뜰 때까지 한 줄로 |

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

---

## 10. 이번에 하지 않는 것

명시적으로 범위 밖이다. 지금 넣으면 "명세만 쌓임"으로 되돌아간다.

- 사람이 웹 폼으로 직접 기록 입력
- LLM 요약, 블로그 초안 생성
- 커리큘럼 31주 테이블과 진도 추적
- 노션 로드맵 동기화
- 대상 저장소에 마크다운 미러
- `get_today_context` 에 학습 기록 섞기
- RAG 인덱싱 (Qdrant)
- ADR 기록 툴

이 중 여럿은 다음 조각 후보다.

---

## 11. 완료 기준

1. `pytest` 가 기존 25개 파일 포함 전부 통과한다.
2. v1 데이터가 있는 실제 `~/.warruru/warruru.db` 가 v2 로 올라가고 기존 기록이 보존된다.
3. 산책온 또는 StackUp 저장소에서 Claude Code 로 `record_experiment` 를 불러
   기록이 남고, 반환값에 개선률이 포함된다.
4. `http://127.0.0.1:8787/records` 에서 그 기록이 프로젝트·주차와 함께 보인다.
5. 데몬을 끈 상태로 기록해도 spool 에 남고, 데몬을 켜면 흡수돼 화면에 나타난다.
6. 필수 필드를 빠뜨린 호출이 거절되고, spool 파일이 만들어지지 않는다.
