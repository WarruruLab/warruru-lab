# Daily Loop MVP — 기록에서 비공개 글까지 한 바퀴

**작성일:** 2026-08-18
**대상:** `local/` (warruru-local) — 마이그레이션 v2
**상태:** 설계 확정. 구현 착수 전(Task 0 선행).
**근거 문서:** 2026-08-18 확정 브리프. 이 문서의 모든 결정은 거기서 온다.

---

## 0. 이 문서의 위치

이 문서는 `docs/superpowers/specs/2026-08-12-학습기록-설계` 를 **대체하지 않고 흡수한다** —
데이터 축(테이블 1개 · kind 4종 · 자동 세션 부착 · spool)은 그대로 물려받고,
테이블 4개·MCP 툴 6개·필터 화면은 이번 범위에서 덜어낸다.
대신 이전 스펙에 없던 뒷 절반(주제 화면 → 결정적 초안 조립 → 저장소 밖 비공개 발행)을 더해
"기록이 글이 되는" 한 바퀴를 닫는다. 무엇을 물려받고 무엇을 미뤘는지는 §5 에 정산해 두었다.

계획 문서는 `local/docs/plans/2026-08-17-학습기록-구현계획.md` 하나뿐이며 그것을 개정한다.
이 문서는 **명세**이고, 태스크와 완료 조건은 그 계획 문서에 있다.

---

## 1. 요구사항

사용자가 직접 정의한 MVP 항목은 다섯이다. 각 항목마다 **"이게 됐다"를 판정하는 단일 사건**을
하나씩 못 박는다. 기능 목록이 아니라 사건이다 — 사건이 일어나지 않으면 그 항목은 없는 것이다.

### (a) 날짜별 달력 조회

무슨 날에 무엇을 했는지 달 단위로 훑을 수 있어야 한다. 지금은 `/d/{date}` 로
날짜를 직접 쳐야만 볼 수 있고, 기록이 있는 날이 어디인지 알 방법이 없다.

> **판정 사건:** `/c/2026-08` 을 열었을 때 기록이 있는 날만 진하게 칠해져 있고,
> 그중 한 칸을 눌러 `/d/2026-08-24` 로 이동해 그날의 학습 기록을 읽는다.

### (b) 오늘 기준 주제별 정리

하루가 끝나는 시점에 "오늘 무엇을 배웠나"가 주제 단위로 묶여 보여야 한다.
날짜별 나열은 이미 있지만, 글 한 편의 단위는 날짜가 아니라 주제다.

> **판정 사건:** 하루치 기록 3건을 남긴 뒤 `/t` 를 새로고침하면
> `커넥션 풀 3건 · 실험2 트러블슈팅1 · 마지막 16:40` 한 줄이 뜬다.

### (c) 주제를 골라 사고과정·결정·해결과정을 블로그 글로

최종 목표는 "기술 이름 나열"이 아니라 **"문제 → 선택 → 구현 → 측정 → 결과 → 한계"** 로
말하는 것이다. 그 순서가 글의 골격이 되어야 하고, 재료가 없는 자리는 채워진 척하면 안 된다.

> **판정 사건:** `/t/connection-pool` 의 [초안 만들기] 를 한 번 눌러
> `~/.warruru/drafts/2026/08/2026-08-24-connection-pool.md` 파일이 생기고,
> 그 안에 6단 제목이 순서대로 있으며 빈 절에는 `TODO:` 가 남아 있다.

### (d) 비공개 발행

글은 다듬어지기 전에는 어디에도 공개되면 안 된다. 이 저장소의 origin 은 public 이므로
"실수로 공개될 수 있는 경로"는 요구사항 위반이다.

> **판정 사건:** 초안 화면의 HTML 을 티스토리에 붙여넣어 비공개로 저장하고
> 돌아와 URL 을 폼에 적으면 `draft.status='PUBLISHED'` 가 되며,
> 그 사이 어느 순간에도 저장소 안에는 초안 파일이 생기지 않았다.

### (e) 학습 가이드 문서

31주 로드맵이 지금 임시 문서에만 있다. 이것이 정식 문서가 되어야
주차별 주제가 `topics.py` 권장 슬러그의 원본이 된다 — 문서가 곧 데이터다.

> **판정 사건:** `docs/guides/backend-infra-roadmap-31w.md` 가 존재하고,
> 거기 적힌 권장 슬러그 하나를 그대로 `record_learning(topic=...)` 에 넣었을 때
> 유사 슬러그 힌트가 그 값을 되돌려 준다.

### 다섯 항목의 관계

(b)(c)(d) 가 먼저다. 이 셋이 첫 주의 수직 슬라이스이고, 여기서 검증할 위험
("기록이 실제로 쌓이는가", "재료로 글이 되는가", "글이 안전한 곳에 앉는가")이 전부 뒤쪽에 몰려 있다.
(a) 달력은 기록이 며칠 쌓인 뒤에야 볼 것이 있으므로 2주차로 미루되
**기한을 '두 번째 글이 나온 직후'로 못 박는다** — '나중에'로 두면 사라진다.
(e) 는 코드가 0줄이라 언제 써도 되지만 (b) 의 슬러그 품질이 여기에 달려 있다.

---

## 2. 기능 명세

우선순위는 세 단계다. **1주차** = 첫 한 바퀴에 필요한 것, **2주차** = 기한이 못 박힌 것,
**이후** = 인터페이스만 두고 미루는 것.

### 2.1 기록 (record_learning)

- **입력:** `kind`(4종) · `topic`(원문) · `title` · `body` 넷이 필수.
  `rationale` · `outcome` · `limitation` · `interview` 는 선택.
- **출력:** 저장 결과 + **결손 필드 목록** + 그 필드를 채운 **예시 재호출 문자열** +
  **유사 topic_slug 힌트**.
- **우선순위:** 1주차.

필수를 넷으로 묶은 이유는 하나다 — 기록을 남길지 말지가 100% 에이전트 재량인 구조에서
툴 표면적과 필수 필드가 늘수록 '기록 안 하기'가 가장 안전한 선택이 된다.
DB 가 비면 (b)(c)(d) 가 전부 빈 화면이고 나머지 설계의 장점이 전부 무의미해진다.

**버린 대안:** kind 별 툴 4개 + 필수 필드 미비 시 MCP 단계 거절(2026-08-12 스펙 §7).
개발 흐름 한가운데서 거절당한 에이전트는 다시 채우는 대신 그냥 넘어간다.

### 2.2 주제 화면 (`/t`, `/t/{slug}`)

- **입력:** 없음(조회). `/t` 는 오늘 자정~자정 구간, `/t/{slug}` 는 그 슬러그의 전체 기록.
- **출력(`/t`):** 상단에 `오늘 기록 N건`, slug 별로 건수 · kind 배지 · 마지막 기록 시각.
  기록 1건짜리 슬러그는 하단 **'미분류' 구획**에 따로 모은다.
- **출력(`/t/{slug}`):** 그 주제의 기록을 시간순으로 펼치고, 맨 아래 [초안 만들기] 버튼과
  그 옆에 **'이 주제로 글을 쓰기에 부족한 필드'** 목록.
- **우선순위:** 1주차.

'미분류' 구획은 오타 교정 장치다. `connection pool` / `Connection Pool` 같은 변형이
슬러그 정규화를 통과해도 남는 소수는 여기서 눈에 띈다. **병합 UI 는 만들지 않는다** —
남는 소수는 SQL 한 줄이 화면보다 싸다.

'부족한 필드' 목록이 버튼 **옆에** 있는 것은 의도적이다. 초안 품질이 낮은 이유가
조립기가 아니라 재료라는 사실을 누르기 전에 보여줘야 다음 기록이 나아진다.

### 2.3 달력 화면 (`/c/{YYYY-MM}`)

- **입력:** `YYYY-MM` 경로 파라미터.
- **출력:** 그 달의 날짜 격자. 기록이 있는 날만 진하게. 클릭하면 기존 `/d/{date}`.
- **우선순위:** **2주차 확정**. 기한은 '두 번째 글이 나온 직후'.

비용은 반나절이다 — 라우트 1 + 템플릿 1 + '이 달에 기록 있는 날짜 집합' 질의 1.
첫 주에서 빼되 확정 항목으로 못 박는 이유가 이 비대칭이다.

### 2.4 초안 생성

경로가 둘이고, 둘은 **같은 draft 행**을 다룬다.

**(1) 결정적 조립기 — `daemon/draft.py`**

- **입력:** `topic_slug` 하나. 그 슬러그의 기록 묶음.
- **출력:** 문제 → 선택 → 구현 → 측정 → 결과 → 한계 6단 마크다운 파일 +
  `draft` 행 1개. **LLM 을 한 번도 호출하지 않는다.**
- **우선순위:** 1주차.

빈 절은 지우지 않고 `TODO: 여기서 무엇을 판단했는가?` 로 남긴다.
그래서 조립기 자체가 재료 부족 진단기 겸 다음 기록에 대한 압력이 된다.

**(2) 에이전트 다듬기 — 프롬프트 한 줄**

- **입력:** 초안 화면이 보여주는 `polish topic=connection-pool draft=<id>` 를
  옆 창의 에이전트에 붙여넣는다.
- **출력:** `get_topic_records` 로 재료를 읽고 `save_draft` 로 같은 행을 덮어쓴다.
- **우선순위:** 1주차. 단 **관문이 아니라 선택지다** — 붙여넣지 않고 자도 초안 파일은 이미 있다.

다듬기 중에 에이전트가 빈 '한계'를 **지어내지 않고 되묻는 것**이 이 경로의 핵심이다.
그 문답 10분이 사실상 하루를 정리하는 시간이고, 답은 다시 `record_learning` 으로
기록에 보강되어 들어간다.

**버린 대안:** `draft_request` pull 큐 — 사람이 다른 창에서 말해줘야 움직이는 관문이고,
원 제안서가 스스로 '영원히 requested 로 남는다'를 위험으로 적었다.
프롬프트 붙여넣기만 두는 안 — 바쁜 주에는 글이 0편이 된다.

### 2.5 발행

- **입력:** `{title, markdown, tags, visibility:'private'}`.
- **출력:** 어댑터에 따라 다르다.
  - `MarkdownFileTarget` — `~/.warruru/drafts/YYYY/MM/` 에 파일. **1순위, 1주차.**
  - `TistoryClipboardTarget` — 붙여넣기용 HTML + 발행 URL 수기 입력. **1주차.**
  - `GitPrivateRepoTarget` — private 저장소 클론에 write + commit + push. **이후.**
- **우선순위:** 위 표기대로. `GitPrivateRepoTarget` 은 MVP 완료 판정에 포함하지 않는다.

마지막 10초만 사람이 하는 이유는 하나다 — **티스토리 공식 Open API 는 죽었다.**
2023-12-22 종료 공지 후 2024년 2월 순차 종료됐고, 2026-08-18 직접 확인 기준
앱 등록 · `/oauth/authorize` · `/apis/post/write` 가 전부 HTTP 404 다.
신규 등록도 기존 키 재발급도 불가능하다. 존재하지 않는 것에 일정을 묶을 수 없다.

**마크다운 정본은 언제나 로컬이다. 티스토리는 미러다.**
발행하면 원본 마크다운이 소실되므로(HTML 로 변환되어 저장된다) 이 순서를 뒤집을 수 없다.

---

## 3. 인터페이스 명세

### 3.1 데이터 — 마이그레이션 v2

`store/migrations.py` 의 `CURRENT_VERSION` 을 `2` 로 올리고 `_V2` 스크립트를 더한다.
기존 v1 테이블 4개는 건드리지 않는다. 마이그레이션은 앞으로만 간다 — 되돌리기는 없다.

```sql
CREATE TABLE IF NOT EXISTS learning_record (
    record_id          TEXT PRIMARY KEY,
    work_id            TEXT NOT NULL REFERENCES work_session(work_id),
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,

    kind               TEXT NOT NULL,   -- EXPERIMENT | TROUBLESHOOTING
                                        -- | TECH_CHOICE | CONCEPT
    topic              TEXT NOT NULL,   -- 사용자가 적은 원문. 화면에 그대로 쓴다
    topic_slug         TEXT NOT NULL,   -- 집계 · 필터 · 글 생성의 유일한 키
    title              TEXT NOT NULL,   -- 한 줄 요약. 목록이 읽는 값
    body               TEXT NOT NULL,   -- 본문. 측정값과 기술 후보도 여기 텍스트로
    body_truncated     INTEGER NOT NULL DEFAULT 0,

    rationale          TEXT,            -- 왜 그렇게 판단했나
    outcome            TEXT,            -- 결과 / 핵심 정리
    limitation         TEXT,            -- 한계 / 아직 모르는 것
    interview          TEXT,            -- 면접에서 이렇게 말한다

    project            TEXT,            -- repo_name 기반. 기록 시점에 고정
    occurred_at        TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    source             TEXT NOT NULL,   -- MCP | SPOOL

    repo_path          TEXT,
    repo_name          TEXT,
    branch             TEXT,
    commit_sha         TEXT,
    dirty              INTEGER,
    dirty_file_count   INTEGER,
    dirty_count_capped INTEGER NOT NULL DEFAULT 0,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_record_occurred
    ON learning_record (occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_slug
    ON learning_record (topic_slug, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_record_work
    ON learning_record (work_id, occurred_at);

CREATE TABLE IF NOT EXISTS draft (
    draft_id           TEXT PRIMARY KEY,
    topic_slug         TEXT NOT NULL,
    title              TEXT NOT NULL,
    markdown           TEXT NOT NULL,
    markdown_truncated INTEGER NOT NULL DEFAULT 0,
    source_record_ids_json TEXT,        -- 조립에 쓴 record_id 목록

    file_path          TEXT,            -- 저장소 바깥의 마크다운 정본 경로
    status             TEXT NOT NULL,   -- DRAFT | PUBLISHED
    published_url      TEXT,
    published_at       TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_draft_slug
    ON draft (topic_slug, updated_at DESC);
```

**`topic` 과 `topic_slug` 를 함께 저장하는 이유.**
원문은 사람이 적은 말이라 화면에 그대로 보여야 하고, 집계는 변형에 흔들리면 안 된다.
`connection pool` · `Connection Pool` · `커넥션 풀` 이 각각 별개 주제가 되면
같은 이야기를 두 번 쓰게 된다. 그래서 **집계 · 필터 · 글 생성은 예외 없이 slug 기준**이다.

**`draft` 에 git 스냅샷 컬럼군을 두지 않는 이유.**
초안은 특정 커밋의 산물이 아니라 여러 기록의 합성물이고, 각 기록이 이미 스냅샷을 들고 있다.
`source_record_ids_json` 을 따라가면 원 스냅샷에 닿는다.

**초안 파일의 front matter.** `file_path` 가 가리키는 마크다운은 6단 본문 앞에
YAML front matter 를 둔다. 필드는 넷이다 — `topic` · `kind` · `source_record_ids` · `status`.

```yaml
---
topic: 커넥션 풀
kind: [EXPERIMENT, TROUBLESHOOTING]
source_record_ids: [rec_01H..., rec_01H...]
status: DRAFT
---
```

`topic` 은 원문이다(슬러그는 파일명에 이미 들어 있다). `kind` 는 재료가 된 기록들의
kind 집합이고, `source_record_ids` 는 `draft.source_record_ids_json` 과,
`status` 는 `draft.status` 와 같은 값이다.
파일만 열어도 무엇으로 조립됐는지 읽혀야 하기 때문에 넣는다 —
마크다운이 정본이고 DB 는 그 정본을 찾아가는 색인이라는 §2.5 의 순서와 같은 이유다.
`save_draft` 로 덮어쓸 때와 발행으로 `status` 가 바뀔 때 front matter 도 함께 다시 쓴다.

**`work_id` 가 `NOT NULL` 인 것은 체크포인트와 같다.** `sessions.attach` 가 활성 세션을
찾거나 만들어 붙이므로 **호출자는 세션 id 를 몰라도 된다.**
알고 받는 한계는 `attach` 가 귀속을 "지금" 기준으로 본다는 것이다(OUTSTANDING I4).
데몬이 꺼진 채 월요일에 남긴 기록이 화요일에 흡수되면 화요일 작업에 붙는다.
기록 내용과 `occurred_at` 은 온전하고 모든 화면이 `occurred_at` 으로 묶으므로
이 기능의 결과는 흔들리지 않는다. 소속 작업 링크만 어긋난다. 이번 범위에서 고치지 않는다.

**측정값과 기술 후보는 `body` · `outcome` 안의 텍스트다.**
정규화 테이블(`measurement` / `tech_option`)이 값을 하는 건 비교·집계 화면이 있을 때인데
MVP 에 그런 화면이 없다. 글을 쓰는 데는 `body` 안의 문장이면 충분하다.

**버린 대안:** 4테이블을 한 번에 넣기('나눠 넣으면 v3 churn 이 생긴다').
마이그레이션은 앞으로만 가는 틀이라 v3 를 추가하는 비용은 스크립트 하나다.
읽는 코드가 없는 테이블을 먼저 만드는 비용이 더 크다.

### 3.2 MCP 툴 3개 (기존 4개와 합쳐 7개)

`mcp/server.py` 의 `ToolService` 에 메서드로 더한다. 기존 4개는 그대로 둔다.
전부 `DaemonClient.send` / `query` 를 타고, **툴은 예외를 밖으로 던지지 않는다**는
기존 관례를 그대로 따른다. 반환 dict 는 `ok` / `storage` / `message` 를 공통으로 갖는다.

```python
@server.tool()
def record_learning(
    kind: str,
    topic: str,
    title: str,
    body: str,
    rationale: str | None = None,
    outcome: str | None = None,
    limitation: str | None = None,
    interview: str | None = None,
    occurred_at: str | None = None,
    repo_path: str | None = None,
) -> dict:
    """무언가를 배우거나 고치거나 고른 순간을 남긴다.

    kind: EXPERIMENT TROUBLESHOOTING TECH_CHOICE CONCEPT
    필수는 kind · topic · title · body 넷뿐이다. 나머지가 비어도
    거절하지 않는다 — 대신 응답이 무엇이 비었는지 알려준다.
    모르는 것을 지어내지 말고 비워 둔 채 부른 뒤, 사용자에게 되물어
    답을 얻으면 같은 툴을 다시 불러 채운다.
    """
```

`occurred_at` 과 `repo_path` 는 새 파라미터가 아니라 `record_checkpoint` 의 관례를
그대로 상속한 것이다. 브리프가 열거한 필드 목록(필수 4 + 선택 4)에는 영향이 없다.

**정상 응답 (`storage="DAEMON"`)**

```python
{
    "ok": True,
    "storage": "DAEMON",
    "message": "기록했습니다.",
    "record_id": "rec_01H...",
    "work_id": "wrk_01H...",
    "work_origin": "IMPLICIT",
    "attached_by": "CLIENT",
    "topic": "커넥션 풀",
    "topic_slug": "connection-pool",
    "missing_fields": ["outcome", "limitation"],
    "example_call": (
        "record_learning(kind='EXPERIMENT', topic='커넥션 풀', "
        "title='풀 크기 10→30, p95 320ms→90ms', body='...', "
        "outcome='...', limitation='...')"
    ),
    "similar_slugs": ["connection-pool"],
    "git": {...},
}
```

세 필드가 **거절을 대신한다.**
`missing_fields` 는 무엇이 비었는지, `example_call` 은 그것을 채워 같은 툴을
그대로 다시 부르는 방법을, `similar_slugs` 는 쓸 만한 슬러그를 알려준다.
기록하는 주체가 사람이 아니라 에이전트이기 때문에 이 형태가 맞다 —
에이전트는 재시도 비용이 거의 0이라 방법을 알려주면 실제로 보강 호출을 한다.
자동완성을 웹 폼이 아니라 툴 응답으로 주는 것이 이 시스템의 실제 사용자를 정확히 반영한 형태다.

**`similar_slugs` 의 원천은 두 갈래다** —
**기존 DB 슬러그 ∪ `topics.py` 의 권장 슬러그 상수**의 합집합에서 고른다.
권장 상수의 원본은 `docs/guides/backend-infra-roadmap-31w.md` 다(문서가 곧 데이터).

두 갈래인 이유는 §1(e) 의 판정 사건이다. DB 슬러그만 보면 그 슬러그로 남긴 기록이
0건인 **첫 호출에서 힌트가 비고**, 로드맵의 권장 슬러그를 그대로 넣었을 때 그 값이
되돌아온다는 판정이 구조적으로 성립하지 않는다. 권장 상수를 합집합에 넣으면
첫 호출부터 권장 슬러그가 자기 자신을 되돌려 주고, 그 순간이 로드맵 문서가
실제로 데이터로 쓰이고 있다는 증거가 된다.

**버린 대안:** `list_topics` 라는 별도 조회 툴. 힌트를 기록 응답에 실으면
같은 효과를 툴 0개로 얻는다.

**데몬에 닿지 못했을 때 (`storage="SPOOL"`)**

```python
{
    "ok": True,
    "storage": "SPOOL",
    "message": "데몬에 닿지 못해 보관했습니다. 다음 기동 때 반영됩니다.",
    "record_id": "rec_01H...",
    "work_id": None, "work_origin": None, "attached_by": None,
    "topic_slug": "connection-pool",     # 순수 함수라 여기서도 채운다
    "missing_fields": ["outcome", "limitation"],
    "example_call": "record_learning(...)",
    "similar_slugs": ["connection-pool"],  # 권장 상수 갈래만. DB 는 못 본다
    "git": None,
}
```

`topic_slug` 와 `missing_fields` 가 SPOOL 에서도 채워지는 것은
정규화와 결손 판정이 **입력만으로 답이 나오는 순수 함수**이기 때문이다.
그래서 `topics.py` 를 최상위에 둔다 — `mcp/` 는 `daemon/` 을 한 번도 임포트하지 않고,
이 경계는 깨면 안 된다.

`similar_slugs` 도 같은 이유로 SPOOL 에서 비지 않는다. **DB 갈래만 빠지고
`topics.py` 의 권장 슬러그 상수만으로 힌트를 준다** — 상수는 임포트 한 번이면 읽힌다.
겹치는 후보가 하나도 없을 때는 빈 목록이지 `None` 이 아니다.

```python
@server.tool()
def get_topic_records(topic_slug: str, since: str | None = None) -> dict:
    """한 주제의 기록을 시간순으로 읽는다. 초안을 다듬기 전에 재료를 확인한다.

    since 는 로컬 날짜(YYYY-MM-DD). 생략하면 그 주제의 전체 기록.
    """
```

```python
{
    "ok": True,
    "storage": "DAEMON",          # 데몬이 꺼져 있으면 "NONE" (기존 query 관례)
    "message": "...",
    "topic_slug": "connection-pool",
    "topic": "커넥션 풀",           # 가장 최근 기록의 원문
    "records": [
        {"record_id": "rec_...", "kind": "EXPERIMENT",
         "title": "...", "body": "...", "rationale": "...",
         "outcome": None, "limitation": None, "interview": None,
         "occurred_at": "2026-08-24T05:20:00.000Z"},
    ],
    "missing_summary": {"limitation": 3, "outcome": 2},
}
```

`missing_summary` 는 `/t/{slug}` 화면의 '부족한 필드' 목록과 **같은 값**이다.
같은 사실을 두 곳에서 따로 계산하면 두 문구가 갈라지고, 갈라진 뒤에는 어느 쪽이 옳은지 모른다.

```python
@server.tool()
def save_draft(
    topic_slug: str,
    title: str,
    markdown: str,
    source_record_ids: list[str] | None = None,
) -> dict:
    """다듬은 글로 그 주제의 초안을 덮어쓴다. 새 초안을 하나 더 만들지 않는다.

    markdown 이 정본이다. 저장 위치는 데몬이 정하며 저장소 바깥이다.
    """
```

```python
{
    "ok": True,
    "storage": "DAEMON",
    "message": "초안을 덮어썼습니다.",
    "draft_id": "drf_01H...",
    "topic_slug": "connection-pool",
    "path": "~/.warruru/drafts/2026/08/2026-08-24-connection-pool.md",
    "status": "DRAFT",
}
```

**덮어쓸 행을 무엇으로 고르는가.** 시그니처에 `draft_id` 가 없으므로
데몬이 `topic_slug` 로 **그 주제의 가장 최근 미발행(`status='DRAFT'`) 행**을 찾아 덮어쓰고,
없으면 새로 만든다(upsert). 초안 화면이 주는 프롬프트 한 줄에는
`draft=<id>` 가 들어 있는데, 그것은 에이전트가 **어느 글을 다듬는지 읽는 용도**이지
`save_draft` 의 인자가 아니다. 한 주제에 미발행 초안이 둘 이상 생기는 경우의 동작은
**확인 필요** — MVP 경로에서는 조립기가 upsert 하므로 발생하지 않는다.

### 3.3 HTTP 라우트 3개

`daemon/routes_api.py` 에 더한다. `/v1/*` 이므로 기존 토큰 게이트
(`dependencies=[Depends(require_token)]`)가 그대로 걸리고,
오류는 기존 봉투 `{"error": {"code": ..., "message": ..., "detail": {}}}` 로 나간다.
라우트는 얇게 두고 판단은 `daemon/learning.py` 와 `SessionService` 에 맡긴다 —
`recording.py` 를 감싸는 기존 라우트와 같은 모양이다.

- **`POST /v1/records`** — 기록 한 건. 본문은 `RecordRequest`
  (`record_id` · `kind` · `topic` · `title` · `body` · 선택 4종 · `occurred_at` ·
  `client_instance_id` · `tool` · `cwd` · `repo_path`).
  응답은 §3.2 정상 응답에서 `ok`/`storage`/`message` 를 뺀 것.
  MCP 어댑터와 **spool 흡수 경로가 같은 함수(`learning.record()`)를 부른다.**
  온라인·오프라인 경로가 갈라지지 않게 하는 유일한 방법이다.

- **`GET /v1/records`** — 목록. 파라미터는 `topic_slug` · `since` · `until` · `limit`.
  `since`/`until` 은 로컬 날짜(`YYYY-MM-DD`)이고 기존 `validate_date_param` 을 탄다.
  `until` 은 **그날을 포함**한다 — "24일까지"라고 적은 사람은 24일 기록을 보고 싶어 한다.
  `limit` 은 **기본 20 · 상한 100** 이다. 100 을 넘겨 들어오면 거절하지 않고 100 으로 자른다
  (§4.2 의 '상한을 넘으면 자른다'와 같은 관례다).

- **`POST /v1/drafts`** — 초안 저장(upsert). 본문은
  `topic_slug` · `title` · `markdown` · `source_record_ids`.
  응답은 `draft_id` · `topic_slug` · `path` · `status`.
  `save_draft` 툴과 `/t/{slug}` 의 [초안 만들기] 폼이 결국 여기로 모인다.

### 3.4 웹 라우트

`daemon/routes_web.py` 에 더한다. 전부 Jinja2 서버 렌더링이고
**조회는 토큰이 필요 없고 상태를 바꾸는 폼만 토큰**(`_check_token`)이라는 기존 관례를 상속한다.
`base.html` 에 `nav` 를 채운다(오늘 / 주제 / 달력 / 초안) — `nav a` CSS 는 이미 있는데
정작 `nav` 요소가 없다.

- **`GET /t`** — 오늘의 주제 목록. 맨 위 `오늘 기록 N건`(0건이면 붉게).
  slug 별 한 줄: 건수 · kind 배지 · 마지막 기록 시각. 발행된 주제에는 체크 표시.
  기록 1건짜리 슬러그는 하단 '미분류' 구획.
- **`GET /t/{slug}`** — 그 주제의 기록을 시간순으로. 맨 아래 [초안 만들기] 버튼과
  그 옆에 '이 주제로 글을 쓰기에 부족한 필드: limitation(3건 중 3건 비어 있음)'.
- **`GET /drafts/{id}`** — 렌더 미리보기 · 남아 있는 `TODO` 노출 ·
  프롬프트 한 줄(`polish topic=... draft=...`) ·
  붙여넣기용 HTML `textarea` + 복사 버튼 · '발행함 + URL' 폼.
- **`GET /c/{YYYY-MM}`** — 달력. 기록 있는 날만 진하게, 클릭하면 `/d/{date}`. (2주차)
- **`GET /d/{date}`** — 기존 화면 유지. **그날의 학습 기록 섹션만 덧붙인다.**

상태를 바꾸는 폼 둘은 기존 `/web/*` 관례를 따르고 토큰을 요구한다.

- `POST /web/topics/{slug}/draft` — [초안 만들기]. `daemon/draft.py` 조립기를 호출하고
  `/drafts/{id}` 로 302.
- `POST /web/drafts/{id}/published` — '발행함' 폼. `published_url` 을 받아
  `status='PUBLISHED'` 로 바꾸고 되돌아온다.

**JavaScript 는 복사 버튼 인라인 8줄 하나뿐이다.** 이 프로젝트의 유일한 예외로 인정하되,
스크립트가 동작하지 않아도 `textarea` 전체 선택으로 같은 일이 되게 만든다.
매일 쓰는 동작이라 예외를 두지만, 그 예외가 경로를 끊으면 안 된다.

**버린 대안:** React + Vite + Zustand + Socket.IO(`packages/web-ui` 명세).
데몬과 같은 8787 포트를 요구해 정면 충돌하고, 채택하면 이미 돌아가는 화면 4개와
폼 토큰 방식을 통째로 버린다.

### 3.5 `PublishTarget` 과 어댑터

발행 코드는 `daemon/` 아래가 아니라 **`warruru_local/publish/` 독립 패키지**에 둔다.

```python
class PublishTarget(Protocol):
    def publish(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        visibility: str = "private",
    ) -> dict:
        """발행하고 {"path": ..., "url": ..., "status": ...} 를 돌려준다.

        어느 어댑터든 visibility 기본값은 'private' 이다.
        공개는 사람이 명시해야만 일어난다.
        """
```

| 어댑터 | 하는 일 | 상태 |
|---|---|---|
| `MarkdownFileTarget` | 저장소 밖에 마크다운 파일을 쓴다 | MVP · 1순위 |
| `TistoryClipboardTarget` | 붙여넣기용 HTML + URL 수기 입력 | MVP |
| `GitPrivateRepoTarget` | private 저장소에 write · commit · push | 이후 |

`publish/` 는 `sqlite3` 와 `warruru_local.store.*` 를 **임포트하지 못한다.**
이것을 문서 관례가 아니라 **소스를 AST 로 훑는 테스트 1개**
(`local/tests/test_publish_boundary.py`)로 강제한다.
경계는 필요하지만 프로세스는 필요 없다 — MVP 에서 발행이 하는 일은 파일 쓰기라
데몬을 오염시킬 실패 모드가 아직 없다. 그러나 '데몬 API 한 번 더 부르느니 커서 하나 열자'는
유혹은 반드시 오고, 그때 **단일 writer 전제가 조용히 깨진다.** 관례로는 못 막고 테스트 1개면 막힌다.

나중에 진짜로 외부를 때리는 어댑터를 붙일 때 프로세스 분리를 재검토하면 되고,
그때 이미 import 경계가 지켜져 있으므로 분리 비용이 싸다.

**버린 대안:** `warruru-publish` 별도 프로세스 + CLI 진입점.
파일 하나 쓰려고 프로세스를 만들면 중간에 멈췄을 때 '발행 프로세스 골격'만 남고 글은 없다.
반대로 `daemon/publish/` 안에 두고 관례로만 지키기 — 유혹을 막는 장치가 0이다.

### 3.6 spool 봉투

`spool.py` 의 `KINDS` 와 `daemon/absorb.py` 의 `_HANDLERS` 양쪽에
**`kind='learning_record'` 한 종만** 더한다(기존 4종 → 5종).

봉투가 한 종인 이유는 툴이 하나이기 때문이다. `kind` 4종은 **봉투 종류가 아니라 컬럼 값**이라
`payload` 안에 들어간다. `KINDS` 는 봉투 종류를 열거한 유일한 자리이므로
`_HANDLERS` 와 어긋난 채 두면 다음 사람을 속인다 — 둘을 함께 갱신한다.

`draft` 는 spool 대상이 아니다. 초안 저장은 사람이 화면 앞에 있을 때만 일어나고,
데몬이 꺼져 있으면 화면 자체가 안 뜬다.

claim-by-rename · `MAX_ATTEMPTS=5` · dead-letter 는 그대로 물려받는다.

---

## 4. 오류·경계 처리

기존 두 원칙을 그대로 따른다: **상한을 넘는 값은 자른다**,
**툴은 예외를 밖으로 던지지 않는다**. 여기에 하나를 더한다 — **기록은 거절하지 않는다.**

### 4.1 기록은 거절하지 않는다

| 상황 | 처리 |
|---|---|
| 선택 필드가 비어 있음 | 저장. 응답에 `missing_fields` + 예시 재호출 |
| 필수 4개 중 하나가 공백뿐 | **확인 필요** (§ 아래) |
| 모르는 `kind` 값 | 그대로 저장. 집계 키는 `topic_slug` 라 무해 |
| `topic` 이 오타 | 그대로 저장. 슬러그가 대부분 흡수하고 나머지는 '미분류' 구획에서 보인다 |

2026-08-12 스펙 §7 의 `kind` 별 필수 필드 거절 규칙은 **MVP 기간 보류한다.**
거절은 '기록 안 하기'를 가장 안전한 선택으로 만든다.

**필수 4개가 공백 문자열일 때 무엇을 하는가는 확인 필요다.** 브리프는
"필수는 넷뿐이고 나머지가 비어도 거절하지 않는다"까지만 정했고,
`title="   "` 같은 입력의 처리를 정하지 않았다. 저장할 때 `strip()` 한 값을
넣는다는 것만 확정이고(화면에 앞뒤 공백이 보이지 않게), 그 결과가 빈 문자열일 때
거절할지 그대로 담을지는 구현 전에 정해야 한다.

### 4.2 상한을 넘으면 자른다

기존 `limits.py` 상수를 그대로 쓴다. 새 상수를 만들지 않는다.

- `title` · `topic` — `TITLE_MAX` (200자)
- `rationale` · `outcome` · `limitation` · `interview` — `TEXT_MAX` (4096자)
- `body` — `BODY_MAX` (65536자). 자르면 `body_truncated=1` 을 세우고 메시지로 알린다
- `draft.markdown` — `BODY_MAX`. 자르면 `markdown_truncated=1`

자른 사실을 **응답 메시지로 알리되 거절하지 않는다**는 것이 기존 관례다.

`topic_slug` 는 `topic` 을 자른 **뒤에** 만든다. 순서를 바꾸면
같은 원문이 상한 근처에서 두 슬러그로 갈린다.

### 4.3 날짜 구간은 `clock.local_day_bounds` 만 쓴다

`occurred_at` 은 UTC ISO 문자열로 저장되는데 `/t` 의 '오늘'과 `/c` 의 '이 달',
`GET /v1/records` 의 `since`/`until` 은 전부 **사람이 보는 로컬 날짜** 개념이다.
`"2026-08-24"` 를 그대로 `"2026-08-24T00:00:00.000Z"` 로 써서 비교하면
KST 기준 오전 9시 이전에 남긴 기록이 통째로 앞 구간으로 샌다 —
`/t` 에서 아침 기록이 사라지는 형태로 바로 드러난다.

**경계는 예외 없이 `clock.local_day_bounds(date_str)` 로 만든다.** 직접 문자열을 잇지 않는다.
이 함수는 "지금"이 아니라 대상 날짜 자체의 오프셋을 쓰고, `dayview` 가 이미 이렇게 한다.

이 함수의 끝 경계는 서머타임에서 정확하지 않다(OUTSTANDING I5, 미해결).
시작에 고정 24시간을 더하기 때문이다. 한국 시간대에는 서머타임이 없어 이 로드맵에서는
드러나지 않지만, 새 코드가 결함의 범위를 넓히는 것이므로 **알고 쓴다.**
고치게 되면 `local_day_bounds` 한 곳만 고쳐도 `/d` · `/t` · `/c` 가 함께 낫는다.
그래서 여기서 별도 계산을 만들지 않고 굳이 이 함수를 부른다.

### 4.4 `MarkdownFileTarget` 은 저장소 내부 경로를 거부한다

기본 출력 경로는 `~/.warruru/drafts/YYYY/MM/YYYY-MM-DD-{slug}.md` 로 **고정**이고,
저장소 내부 경로가 인자로 들어오면 **예외를 던진다.**

이건 취향이 아니라 사고 방지 장치다. origin 은 public GitHub 저장소이고
`blog/` 는 이미 추적 중이다. 저장소 안에 초안을 떨구면 '비밀글'이 요구인 기능이
`git add -A` 한 번으로 미완성 사고 과정을 인터넷에 올린다.

**버린 대안:** `.gitignore` 한 줄로 막기. `git add -f`, 새 클론, 다른 도구 한 번이면 뚫린다.
통제가 git 계층 한 겹뿐인 것을 '파일시스템 수준 보장'이라 부를 수 없다.
경로 고정 + 예외는 뚫리지 않는다.

`blog/` 는 역할을 축소한다 — **사람이 읽고 '공개해도 된다'고 결정한 글만** 들어가는 자리다.
자동 생성 초안은 절대 들어가지 않는다는 한 줄을 `blog/README.md` 에 추가한다.

### 4.5 데몬이 꺼져 있을 때

봉투는 `~/.warruru/spool/{client_instance_id}.jsonl` 에 떨어지고
다음에 데몬이 뜰 때 흡수된다. **기록 실패로 개발이 멈추는 일은 없다.**

그런데 지금 코드는 이 내구성을 새 기록에 대해서만 정확히 우회한다.
`mcp/client.py` 의 `_NO_SPOOL_STATUSES = {400, 401, 404, 422}` 에 **404 가 들어 있다.**
`SingleInstanceLock` 때문에 구버전 데몬이 떠 있으면 `_spawn_daemon` 도 새로 띄우지 않으므로,
`/v1/records` 를 모르는 데몬에 닿는 순간 새 기록만 404 를 받고
**spool 도 dead-letter 도 없이 조용히 사라진다.**

- **쓰기 봉투에 한해 `_NO_SPOOL_STATUSES` 에서 404 를 제거한다.** `400`·`401`·`422` 는 유지한다.
- 흡수 단계에서 **모르는 `kind` 봉투는 무한 재시도 대신 dead-letter** 로 보낸다.
  지금은 경고만 남기고 `continue` 해서 `absorbed/` 로 넘어가며 조용히 사라진다.

**'쓰기 봉투 한정'이 코드에서 무엇인가.** `_NO_SPOOL_STATUSES` 는 **`send()` 만 참조하고
`query()` 는 이 상수를 보지 않는다.** 한정은 조건문이 아니라 이 참조 관계로 표현된다.
그래서 상수에서 404 를 빼도 조회 경로는 바뀌지 않는다.
두 경로가 같은 집합을 공유하도록 공용 자리로 끌어올리는 순간 이 한정이 조용히 깨지므로,
**상수는 `mcp/client.py` 안에 두고 `query()` 에서 참조하지 않는다.**

조회(`query()`)가 404 를 받을 때의 동작은 지금 그대로 둔다 — spool 하지 않고
`storage="NONE"` 과 오류 메시지를 돌려준다. 조회는 폴백할 대상이 없고 잃을 기록도 없다.
`get_topic_records` 가 `/v1/records` 를 모르는 데몬에 닿으면 빈손으로 돌아오지만
그 사실이 응답에 그대로 보이므로 조용한 유실이 아니다.

이 둘을 **새 기록을 얹기 전에 먼저 고친다.** 새 기능이 정확히 이 결함을 밟기 때문이다.
K2 를 고치면 경로 오타 같은 영구적 404 도 spool 에 쌓이지만,
`MAX_ATTEMPTS`(5) 뒤에 dead-letter 로 격리되므로 '조용한 유실'이 '시끄러운 격리'가 된다.
그쪽이 낫다.

### 4.5.1 404 를 spool 로 돌리는 것만으로는 부족하다

위 두 수정은 **새 데몬 안에 있다.** 그런데 K2 가 문제되는 상황은 정의상
**구버전 데몬이 떠 있는 상황**이고, 그 데몬은 새 코드를 갖고 있지 않다.

봉투가 spool 에 남아도 구버전 데몬의 스윕(`daemon/sweeper.py` → `absorb_all`)이
같은 파일을 집어 든다. 그 데몬의 `_HANDLERS` 에는 `learning_record` 키가 없으므로
`absorb.py` 가 경고만 남기고 `continue` 하고, 그 봉투는 `remaining` 에도 `dead` 에도
들어가지 않은 채 파일이 `absorbed/` 로 옮겨진다. **한 겹 뒤에서 똑같이 사라진다.**
dead-letter 수정은 새 데몬에만 있으니 이 경로를 막지 못한다.

**해법은 이미 코드에 있다 — 봉투 버전 게이트.**
`absorb_all` 은 파일을 붙잡기 전에 `_has_unknown_version(path)` 를 먼저 본다.
모르는 버전이 하나라도 섞여 있으면 **이름조차 건드리지 않고 그대로 둔다.**

그래서 이렇게 정한다.

- 어댑터는 `learning_record` 봉투를 **`envelope_version = 2`** 로 쓴다.
  기존 4종은 `1` 그대로다.
- 새 데몬은 지원 버전을 집합으로 갖는다 — `SUPPORTED_ENVELOPE_VERSIONS = {1, 2}`.
  `_has_unknown_version` 을 상수 하나와의 `!=` 비교에서 이 집합의 `not in` 으로 바꾼다.

결과: 구버전 데몬은 새 봉투가 든 파일을 통째로 **건너뛴다.** 유실이 아니라 대기다.
같은 파일에 든 기존 체크포인트 봉투도 함께 미뤄지지만, 다음에 새 데몬이 뜨면
전부 반영된다. **버전을 올리지 않으면 이 보장이 성립하지 않는다.**

`GET /v1/records` 를 모르는 데몬에 조회를 걸면 빈손으로 돌아오는데,
그건 응답에 보이므로 조용한 유실이 아니다(§4.5 위 문단).

### 4.5.2 이번에 고치지 않는 미해결 결함

`local/docs/OUTSTANDING.md` 기준으로 **K2 하나만** 고친다.
나머지는 그대로 열려 있고, 그중 **둘은 이 MVP 가 트래픽을 늘리는 경로 위에 있다.**

- **I1 — 기동 시 `absorb_all` 이 무방비.** `daemon/app.py` 가 `lifespan` 안에서
  try/except 없이 부른다. spool 파일에 잘못된 UTF-8 바이트 하나가 있으면
  `UnicodeDecodeError` 가 lifespan 을 뚫고 나가 **데몬이 영구히 부팅 실패**한다.
  원인이 디스크 파일이라 재시도해도 매번 재발한다.
  이번 MVP 는 spool 봉투 종류를 늘리므로 그 파일에 쓰는 빈도가 올라간다.
- **K1 — 오프라인 `finish_work` 가 `work_id` 를 잃는다.** 같은 spool 경로다.
- I2(잘못된 `occurred_at`) · I4(흡수 시 귀속이 '지금' 기준) ·
  I5(`local_day_bounds` 서머타임 끝 경계) · K3~K8 도 열려 있다.

새 코드가 같은 함정을 **새로 파지 않게만** 한다(§4.3). 수리는 한 바퀴가 돈 뒤로 미룬다.
다만 **I1 은 예외로 둘지 한 바퀴 안에 판단한다** — 데몬이 안 뜨면 나머지가 전부 무의미하고,
고치는 비용은 `try/except` 한 겹과 `errors="replace"` 디코드뿐이다.

```
record_learning
   │  400/401/422 → 거절 그대로, spool 안 함
   ├─ 데몬 있음 ──▶ POST /v1/records ──▶ learning.record()
   └─ 못 닿음 ────▶ spool JSONL
                      │ 다음 기동
                      └─▶ absorb ──▶ learning.record()
                            └ 모르는 kind → dead-letter
```

---

## 5. 이전 스펙(2026-08-12)과의 정산

### 5.1 그대로 가져온 것

- **테이블 1개에 `kind` 4종**(EXPERIMENT / TROUBLESHOOTING / TECH_CHOICE / CONCEPT).
  종류를 테이블로 나누지 않는다는 판단은 유효하다.
- **`checkpoint` 를 확장하지 않는 이유.** 체크포인트는 *작업 중의 순간*이고
  학습 기록은 *면접에서 말할 수 있게 정리된 것*이다. 수명이 다르다.
- **`work_id` 자동 부착.** `sessions.attach` 가 붙이고 호출자는 세션 id 를 모른다.
- **git 스냅샷 · `occurred_at`/`recorded_at`/`source` · soft delete** 컬럼군.
- **한도는 거절이 아니라 자름**(`limits.py` 관례), 그리고 잘린 사실을 메시지로 알리기.
- **`interview` 컬럼.** 최종 목표가 "말할 수 있는 상태"라는 전제가 그대로다.
- **`project` 를 `repo_name` 으로 기록 시점에 고정.**
- **날짜 경계는 `clock.local_day_bounds` 하나로 통일.**
- **K2(404 가 spool 없이 버려진다) 수리.** 이전 스펙이 고치기로 한 그대로다.
  **이번에 고치는 미해결 결함은 K2 하나뿐이다.** 미지 `kind` 봉투를 dead-letter 로 보내는 것은
  OUTSTANDING 결함 id 가 붙어 있지 않은 **신규 보강**이다 — `OUTSTANDING.md` 의 C1 은
  '실패한 봉투가 재시도 없이 버려진다'이고 이미 해결됐다(`f762f5c` · `f9377a4` · `3189858`).
- **I4(귀속이 '지금' 기준)는 받아들인다**는 판단.
- **"문제 → 선택 → 구현 → 측정 → 결과 → 한계" 6단.** 이전 스펙에서는 상세 화면의
  필드 배치 순서였는데, 이번에는 **생성되는 글의 골격**으로 승격했다.

### 5.2 미룬 것

- `measurement` / `tech_option` 정규화 테이블, `MeasurementInput` / `OptionInput` 모델,
  `delta_of()` 개선률 계산 — 비교·집계 화면이 없는데 정규화부터 하면 첫 주가 사라진다.
- `week` 계산(`daemon/derive.py`)과 `roadmap_start_date` 설정,
  `load_or_create_daemon_config` 반환 형태 변경 — 주차는 글을 쓰는 데 필요 없다.
- `/records` 목록·상세 화면과 필터(`project` · `kind` · `tag` · `week` · `missing`) —
  이번 화면의 축은 필터가 아니라 **주제와 날짜**다.
- `list_records` / `get_record` 조회 툴 — `get_topic_records` 하나가 다듬기에 필요한 전부다.
- `?missing=interview` 복습 큐와 `⚠ 면접 문장 없음` 배지 — 같은 정보를
  `/t/{slug}` 의 '부족한 필드' 목록이 초안 만들기 직전에 보여준다.
- `mitigation` 컬럼과 `⚠ 보완책 없음` 배지 — 컬럼 자체를 이번에 두지 않는다.
  단점 보완은 `rationale` · `limitation` 안의 문장으로 받는다.
- 기록의 soft delete 웹 폼(`/web/records/{id}/delete`)과 `?deleted=1` —
  컬럼(`deleted_at`)은 두되 화면은 이번에 만들지 않는다.
- `back` 쿼리스트링 복귀 규칙 — 돌아갈 곳이 필터 조합이 아니라 `/t` 하나라 필요 없다.

### 5.3 뒤집은 것 (셋)

- **`topic` 자유 문자열 → `topic_slug` 정규화 병행.**
  이전 판단('오타는 목록 화면에서 눈에 보인다')은 `topic` 이 **필터**였을 때 성립한다.
  MVP 는 `topic` 을 GROUP BY 키이자 **글 한 편의 단위**로 승격시키므로,
  `connection pool` / `Connection Pool` 하나가 별개 주제가 되면 같은 이야기를 두 번 쓰게 된다.

- **`kind` 별 툴 4개 → 단일 툴 `record_learning`.**
  이전 근거는 'MCP JSON Schema 가 조건부 필수를 표현하지 못하니 툴을 나눠야 명확하다'였는데,
  그 명확함의 대가가 툴 표면적 4배다. 기록 여부가 100% 에이전트 재량인 구조에서는
  표면적이 넓을수록 '기록 안 하기'가 이긴다. 명확함은 툴 수가 아니라
  **응답에 실어 보내는 힌트**로 얻는다(§3.2).

- **필수 필드 미비 시 거절 → 거절 없음.**
  이전 근거는 '거절은 에이전트가 살아 있을 때 해야 고칠 수 있다'였고 그 자체는 맞다.
  다만 거절당한 에이전트가 실제로 하는 일은 '다시 채우기'가 아니라 '그냥 넘어가기'다.
  같은 목적(재료가 채워진 기록)을 **거절 대신 힌트**로 달성한다 —
  마찰 0으로 재료만 늘어난다.

---

## 6. 이번에 하지 않는 것

명시적으로 범위 밖이다. 각 항목에 이유가 하나씩 있다.

**발행 쪽**

- 티스토리 자동 발행(OAuth) — 공식 API 는 2024년 2월 종료됐고
  2026-08-18 확인 기준 관련 경로가 전부 404 다. 존재하지 않는 것에 일정을 묶을 수 없다.
- **직접 만드는 티스토리 MCP** — 사용자가 만들기로 정했다(2026-08-18).
  다만 이번 MVP 범위 밖이다. 첫 스파이크가 '글 작성'이 아니라
  '카카오 세션이 며칠 재사용되는가' 측정이라 소요 시간을 지금 잴 수 없다.
  약관 원문 확인이 선행 조건인데 정책 URL 이 404 라 **확인 못 했다.**
  붙는 자리는 파이썬 어댑터가 아니라 에이전트 쪽 MCP 다 — 데몬은 티스토리를 모른 채로 남는다.
  자세한 조건과 중단 기준은 `local/docs/adr/2026-08-18-publish-target.md`.
- `NotionTarget` / GitHub REST API 어댑터 — `PublishTarget` 만 있으면 나중에 파일 하나다.
  MVP 의 가치는 어댑터 개수가 아니라 종단 경로 1개다.

**데이터·지능 쪽**

- `measurement` / `tech_option` 정규화 테이블 — 비교·집계 화면이 없다(§5.2).
- 데몬 안의 LLM 호출(Ollama / OpenAI) — 서비스 기동·모델·프롬프트·타임아웃·재시도가
  전부 새로 필요하고 1주 이상이다. 글은 이미 사용자 앞에 떠 있는 에이전트가 쓴다.
- RAG / Qdrant / 임베딩 / 지식 블록 구조화 — 기록이 수십 건인 단계에서
  검색 인프라는 해결할 문제가 없는 해법이다.
- MCP 가 대화를 감시해 '중요한 것'을 자동 감지하는 장치 — 범위가 완전히 다른 프로젝트다.
  `AGENTS.md` 기록 규칙 문단(프롬프트)으로 대신하고, 한 주 뒤 기록 건수로 그 문단의 성능을 잰다.
- 학습 진도 추적 · 주차 계산 · 다음 주제 추천 · 분야별 커버리지 대시보드 —
  기록이 몇 주 쌓여 실제 데이터가 생긴 뒤에 설계해야 형태가 나온다. 이번엔 가이드 '문서'만.

**흐름·화면 쪽**

- `kind` 별 MCP 툴 분화와 필수 필드 미비 시 거절 — 거절은 '기록 안 하기'를
  가장 안전한 선택으로 만든다(§5.3).
- `draft_request` pull 큐 / `needs_input` 생성 차단 / 발행 전용 별도 프로세스 —
  목표 체인 위에 사람이 개입해야 하는 관문을 세운다. MVP 가 실제로 하는 일은 파일 하나 쓰기다.
- `topic` 별칭 병합 UI — slug 정규화로 대부분 잡히고, 남는 소수는 SQL 한 줄이 화면보다 싸다.
- 웹에서 초안 편집 · 리치 에디터 · 이미지 업로드 — 마크다운 파일이 이미 에디터로 열린다.
  화면은 보여주기만 한다.

**인프라·운영 쪽**

- `packages/agent` 4모듈(FastAPI :8000 + WebSocket + MySQL)과
  `packages/web-ui`(React + Vite + Zustand + Socket.IO, 8787 포트 요구) —
  현실과 정면 충돌하므로 확장이 아니라 폐기 대상이다.
- `services/sync` 와 크로스 플랫폼 동기화, 서버 운영(S3 / 중앙 저장소) —
  사용자가 'MVP 이후'로 정했다.
- `docs/architecture` · `docs/api` 12개 전역 문서 — 시스템이 데몬 하나면
  아키텍처 문서 4개가 필요 없다. 만드는 대신 약속을 지운다.
- 인증 강화 · 멀티유저 · 원격 접근 — 127.0.0.1 바인딩과 폼 토큰이 이미 있고 사용자는 1명이다.
- OUTSTANDING 결함 일괄 수리(I2 / I4 / I5) — K2 만 먼저 고친다(§4.5).
  새 기능이 정확히 그 결함을 밟기 때문이고, 나머지는 이 기능 없이도 있던 문제다.
