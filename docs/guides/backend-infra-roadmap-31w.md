# 백엔드·인프라 31주 학습 로드맵 (2027년 3월 공채)

> **이 문서는 문서다. 그 이상이 아니다.**
> 진도 추적, 주차 자동 계산, 다음 주제 추천, 분야별 커버리지 대시보드 —
> 이번 MVP 는 그중 아무것도 만들지 않는다. 시스템은 이 파일을 읽지 않는다.
> 데몬도, MCP 어댑터도, 웹 화면도 런타임에 이 마크다운을 파싱하지 않는다.
> **사람이 읽는다.** 그리고 사람이 이 문서의 슬러그 목록을 손으로 코드에 옮겨 적는다.
> 그 한 번의 필사(§0.5)가 문서와 코드 사이의 유일한 연결이다.

**작성일:** 2026-08-18
**원본:** 노션 「2027년 3월 공채 백엔드·인프라 취준 로드맵」 (최종 수정 2026-08-12)
**기간:** 2026-08-12(1주차) ~ 2027-03-08 이후 공채(31주차)
**상태:** 원본 이관 + 권장 `topic_slug` 병기. 코드 0줄.

**목표:** 2027년 3월 공채까지 Java/Spring 기반 백엔드 역량을 중심으로
DB·캐시·메시징·클라우드·컨테이너 운영 경험을 프로젝트에 연결한다.

**프로젝트 역할:** 산책온 = 서비스 백엔드/성능/클라우드,
StackUp = 비동기/메시징/이벤트 처리.

---

## 0. 이 문서를 어떻게 쓰는가

원본에 없던 것은 이 0장과 주차마다 붙은 `slug:` 줄뿐이다.
주차 배치·학습 항목·체크박스는 원본 그대로다.

### 0.1 왜 31주차의 여섯 단계를 맨 앞에 두는가

원본은 「문제 → 선택 → 구현 → 측정 → 결과 → 한계」를 31주차(이력서/면접) 항목에 두었다.
그 자리에 두면 31주차에 처음 해 보는 일이 된다. 그때는 이미 늦다 —
5주차의 N+1 개선에서 "개선 전 쿼리가 몇 개였는지"는 그날 적지 않으면 복원되지 않는다.

**이 여섯 단계는 마지막 주의 과제가 아니라 31주 내내의 기록 형식이다.**

| 단계 | 그 자리에서 답해야 할 질문 |
|---|---|
| 문제 | 무엇이 느리거나 깨졌거나 정해지지 않았는가 |
| 선택 | 후보가 무엇이었고 왜 이것을 골랐는가 |
| 구현 | 실제로 무엇을 바꿨는가 (커밋이 증거다) |
| 측정 | 바꾸기 전 숫자와 바꾼 뒤 숫자 |
| 결과 | 그래서 무엇이 달라졌는가 |
| 한계 | 이 방법이 못 하는 것, 더 못 올린 이유 |

원본이 든 예시 두 개가 이 형식의 완성형이다.

> 외부 지도 API 호출이 추천 응답시간의 주요 병목이라고 판단해 Cache Aside 방식으로
> Redis 를 적용하고 TTL 및 Cache Miss 전략을 설계했다.

> GitHub Repository 분석 작업이 장시간 수행되어 HTTP 요청과 작업 수행을 분리하기 위해
> RabbitMQ 기반 비동기 처리 구조를 도입했다.

### 0.2 기록 필드와 여섯 단계의 대응

기록은 MCP 툴 하나로 남는다. 필수는 넷뿐이다.

```
record_learning(
  kind, topic, title, body,      # 필수 4개
  [rationale, outcome,           # 아래 4개는 선택
   limitation, interview]        # 비어도 거절 안 함
)
```

여섯 단계를 이 필드에 어떻게 나눠 담을지는 다음을 권장한다.

- **문제** → `title` 과 `body` 앞부분. 제목에 증상과 숫자를 같이 넣는다.
- **선택** → `rationale`. 후보를 늘어놓고 왜 이것인지 적는 자리다.
- **구현** → `body`. 코드 자체는 적지 않는다 — 커밋이 자동으로 붙는다(§0.4).
- **측정** → `body` 또는 `outcome` 안의 텍스트. 측정값 전용 테이블은 만들지 않는다.
- **결과** → `outcome`.
- **한계** → `limitation`. 이 칸이 비어 있는 것이 곧 면접에서 막히는 지점이다.
- (공통) **면접 문장** → `interview`.

`rationale` · `outcome` · `limitation` 이 비어도 기록은 저장된다.
거절하면 개발 흐름 한가운데의 에이전트는 다시 채우지 않고 그냥 넘어가기 때문이다.
대신 성공 응답이 "비어 있는 필드"와 "그 필드를 채워 다시 부르는 예시 호출"을 돌려주고,
주제 화면이 "이 주제로 글을 쓰기에 부족한 필드"를 상시 표시한다.

`daemon/draft.py` 의 조립기가 이 기록들을 여섯 단으로 묶어 마크다운 한 편을 만든다.
빈 자리는 지우지 않고 `TODO: 여기서 무엇을 판단했는가?` 로 남는다.
그 TODO 목록이 곧 "면접에서 대답 못 할 부분" 목록이다.

**확인 필요:** 위 필드 ↔ 절 대응은 이 문서의 권장안이다.
조립기의 최종 매핑 규칙은 `daemon/draft.py` 구현 시점에 확정된다.

### 0.3 「매주 반드시 하나 이상」 네 항목을 기록 종류에 연결한다

원본의 체크리스트 네 줄은 이 시스템의 `kind` 와 이렇게 대응한다.
왼쪽은 상황이고, 오른쪽은 그 자리에서 부를 `kind` 다.

- **실험 결과 → `kind='EXPERIMENT'`**
  바꿨더니 숫자가 달라졌을 때. 인덱스를 걸었더니 실행계획이 바뀌었을 때,
  Fetch Join 후 쿼리 수가 줄었을 때, k6 결과 p95 가 내려갔을 때.
  **바꾸기 전 숫자를 모르면 이 기록은 못 쓴다.** 그래서 측정은 바꾸기 전에 한다.
  `outcome` 에 전/후 숫자를 함께 적는다.

- **Troubleshooting → `kind='TROUBLESHOOTING'`**
  돌던 것이 깨졌다가 고쳐졌을 때. 증상 → 원인 → 해결이 한 덩어리로 들어간다.
  원인을 못 찾고 우회했다면 그 사실을 `limitation` 에 적는다.
  이 칸을 비워 두면 몇 주 뒤 "그때 뭐가 원인이었더라"만 남는다.

- **Architecture Decision Record → `kind='TECH_CHOICE'`**
  둘 이상 중에 하나를 골랐을 때. 20주차 RabbitMQ vs Kafka 가 대표적이지만,
  1주차의 패키지 구조, 6주차의 트랜잭션 경계, 25주차의 EC2 vs ECS 도 전부 여기다.
  **후보와 버린 이유가 `rationale` 에 없으면 그 기록은 면접에서 못 쓴다.**
  "기술을 넣지 않기로 한 결정"도 같은 kind 로 남긴다 — 28주차의 K8s 필요성 평가가 그렇다.

- **CS 3회 루틴 / 개념 학습 → `kind='CONCEPT'`**
  화·목·토 루틴과 30주차 CS 집중이 전부 여기다.
  `body` 는 **내 말로 다시 쓴 문장**이어야 한다. 남의 문장은 면접장에서 안 나온다.

- **코드 → 별도 kind 가 없다.**
  기록을 남기는 순간 데몬이 git 스냅샷(repo/branch/commit/dirty)을 찍어 함께 저장한다.
  즉 코드는 기록의 종류가 아니라 모든 기록에 딸리는 증거다.
  다만 산책온·StackUp 은 별도 저장소이므로, **그 저장소 안에서 에이전트를 띄워야**
  스냅샷이 그 주의 실제 커밋을 가리킨다. 이 저장소에서 남기면 엉뚱한 커밋이 붙는다.

한 주에 네 종류를 다 채우라는 뜻이 아니다. 원본 문구대로 **하나 이상**이다.
다만 한 주가 통째로 `CONCEPT` 만이면 그 주는 프로젝트에 손을 안 댄 주다.

### 0.4 topic_slug — 이 문서의 핵심 부가가치

`topic` 은 원문 그대로 저장되지만, 집계·필터·글 생성은 전부 `topic_slug` 기준이다.
그래서 같은 주제를 매번 다르게 부르면 한 이야기가 여러 조각으로 갈라지고,
같은 내용을 두 번 쓰게 된다. `connection pool` / `Connection Pool` / `커넥션 풀` 이
전부 다른 주제가 되는 상황을 막으려고 **주차마다 슬러그를 미리 정해 둔다.**

**규칙**

- 소문자 영문, 하이픈 구분. 예: `jpa-n-plus-one`, `cache-aside`, `rabbitmq-dlq`, `aws-vpc`.
- 정규화는 시스템이 한다(NFKC · trim · 소문자 · 공백/언더스코어→하이픈 · 연속 하이픈 축약).
  즉 `JPA N+1` 로 불러도 슬러그는 만들어진다. 다만 그렇게 하면 이름이 흔들린다.
- **한 주차에 2~4개면 충분하다.** 학습 항목 전부에 슬러그를 붙이지 않았다 —
  읽고 끝날 항목(1주차 Collection·Exception, 2주차 DispatcherServlet 개요 등)에는
  붙이지 않았고, **실제로 기록이 남을 것**에만 붙였다.
- **겹치면 합친다.** 4주차 인덱스, 9주차 커버링 인덱스, 토요일 CS 인덱스는
  전부 `db-index` 계열로 모은다. 같은 것을 두 이름으로 부르지 않는다.
- 여기 없는 주제가 나오면 새로 만든다. 이 목록은 상한이 아니라 출발점이다.
  다만 만들기 전에 기록 응답이 주는 "유사 슬러그" 힌트를 먼저 본다.

### 0.5 문서와 코드를 잇는 유일한 지점

부록 A 의 슬러그 목록이 `local/src/warruru_local/topics.py` 의
권장 슬러그 상수의 **원본**이다. 옮기는 방법은 사람의 복사·붙여넣기 하나뿐이다.
시스템이 이 파일을 열어 읽는 경로는 없고, 만들지도 않는다.

그래서 이 문서를 고치면 `topics.py` 도 같이 고쳐야 한다.
자동 동기화를 만들지 않는 이유는 하나다 — 로드맵은 31주에 몇 번 바뀌고,
그 몇 번을 위해 파서와 그 파서의 테스트를 유지하는 값이 안 된다.

### 0.6 이 문서가 하지 않는 일

- **오늘이 몇 주차인지 알려주지 않는다.** 날짜를 보고 사람이 센다.
- **밀렸는지 알려주지 않는다.** 진도 추적 기능은 이번 MVP 에 없다.
- **다음에 뭘 하라고 추천하지 않는다.** 추천은 기록이 몇 주 쌓여
  실제 데이터가 생긴 뒤에 설계해야 형태가 나온다.
- **주차별 커버리지를 집계하지 않는다.** 화면은 날짜(`/c`, `/d`)와
  주제(`/t`)로만 묶는다. 주차는 화면에 존재하지 않는 개념이다.

이 넷을 만들지 않기로 한 이유는 같다 — 첫 한 바퀴(기록 → 주제 화면 → 초안 → 발행)가
돌기 전에 붙이는 계기판은, 잴 것이 없는 계기판이다.

---

## 1. 최종 기술 스택

- **깊게:** Java, Spring Boot, JPA, RDBMS
- **프로젝트에서 제대로 사용:** Redis, RabbitMQ, Docker, AWS
- **원리 이해 + 적용:** Kafka, Terraform, Monitoring
- **직접 적용 + 개념 설명:** Kubernetes
- **공통 기반:** Linux, Network, Git, CI/CD, Testing

---

## 2. 프로젝트별 역할

### 산책온

- Java / Spring Boot / JPA / RDBMS
- Redis 캐싱 및 성능 개선
- Docker / AWS / Terraform
- Monitoring
- Kubernetes 실험 적용

**핵심 포트폴리오 소재:** 도메인 설계, N+1, 인덱스, 트랜잭션, Redis,
외부 API 장애 처리, 성능 테스트, AWS 인프라

### StackUp

- Java / Spring Boot
- RabbitMQ / SSE
- Retry / DLQ / Idempotency
- Consumer 장애 및 재처리
- Kafka 비교 실험

**핵심 포트폴리오 소재:** 동기→비동기 전환 근거, ACK/NACK, Retry, DLQ,
중복 메시지, SSE 재연결, RabbitMQ vs Kafka

---

## 3. 주차별 계획

각 주차의 `slug:` 줄이 이 문서에서 추가된 부분이다.
체크박스는 원본 그대로이며, 이 문서가 그 상태를 추적하지 않는다.

### 1주차 · 2026-08-12 ~ 2026-08-16 — Java/Spring 현황 정리 + 산책온 구조 확정

**학습**
- Java 객체지향, Interface / Abstract Class
- Collection, Exception
- Spring IoC / DI, Bean Lifecycle

**산책온**
- Backend Package 구조 확정
- 핵심 도메인 및 Entity 후보 정리
- User / WalkRequest / WalkRoute / WalkHistory / Preference / Feedback

**산출물**
- [ ] Backend Architecture 문서
- [ ] ERD 초안
- [ ] 패키지 구조 선택 이유 정리

`slug:` `package-structure`(TECH_CHOICE) · `domain-erd`(TECH_CHOICE) · `spring-di`(CONCEPT)

"패키지 구조 선택 이유"는 후보를 늘어놓고 고르는 일이므로 첫 `TECH_CHOICE` 다.
계층형이냐 도메인형이냐를 `rationale` 에, 이 구조가 불편해질 지점을 `limitation` 에 적는다.
Collection·Exception 은 슬러그를 붙이지 않았다 — 읽고 넘어가는 항목이다.

### 2주차 · 2026-08-17 ~ 2026-08-23 — Spring MVC / REST API

**학습**
- DispatcherServlet
- Controller / Service / Repository
- DTO / Validation
- ExceptionHandler
- Filter / Interceptor

**산책온**
- [ ] 산책 요청 생성 API
- [ ] 사용자 선호 조회 API
- [ ] 산책 기록 저장 API
- [ ] API 명세 작성

**면접 포인트**
- Filter 와 Interceptor 차이
- Entity 와 DTO 를 분리하는 이유

`slug:` `filter-vs-interceptor`(CONCEPT) · `dto-separation`(TECH_CHOICE) ·
`api-error-handling`(TECH_CHOICE)

면접 포인트 두 개는 이 주에 `interview` 필드까지 채워서 남긴다.
이 주는 질문이 미리 나와 있는 드문 주라 답을 문장으로 확정할 수 있다.

### 3주차 · 2026-08-24 ~ 2026-08-30 — JPA 기본

**학습**
- Persistence Context
- Entity Lifecycle / Dirty Checking
- Lazy Loading / Proxy
- Cascade
- 단방향 / 양방향 연관관계

**산책온**
- [ ] Entity 구현
- [ ] 관계 설정
- [ ] Repository 작성
- [ ] ERD v1 완성

`slug:` `jpa-persistence-context`(CONCEPT) · `jpa-lazy-loading`(CONCEPT) ·
`entity-association`(TECH_CHOICE)

양방향 연관관계를 어디에 걸고 어디에 안 걸었는지가 5주차 N+1 의 원인이 된다.
그 판단을 `entity-association` 에 남겨 두면 5주차에 원인을 되짚을 수 있다.

### 4주차 · 2026-08-31 ~ 2026-09-06 — SQL / RDBMS

**학습**
- PK / FK / JOIN
- 정규화
- Index / B+Tree
- Transaction 기본

**산책온**
- [ ] 최근 산책 기록 조회 SQL 분석
- [ ] 사용자 피드백 조회
- [ ] 지역별 코스 조회
- [ ] 추천 후보 조회

`slug:` `db-index`(CONCEPT) · `db-normalization`(CONCEPT) · `db-transaction`(CONCEPT)

`db-index` 는 9주차와 토요일 CS 루틴에서 계속 재사용한다.
9주차에 이 주제로 초안을 만들 때 4주차의 개념 정리와 9주차의 측정이 한 편에 들어간다.

### 5주차 · 2026-09-07 ~ 2026-09-13 — JPA 심화

**학습**
- N+1
- Fetch Join / EntityGraph
- JPQL / QueryDSL
- Batch Size

**산책온**
- [ ] N+1 재현
- [ ] 개선 적용
- [ ] 개선 전후 SQL 비교 기록

`slug:` `jpa-n-plus-one`(EXPERIMENT) · `jpa-fetch-join`(CONCEPT) ·
`jpa-batch-size`(EXPERIMENT) · `querydsl`(TECH_CHOICE)

**이 주가 첫 `EXPERIMENT` 다.** "N+1 재현"을 먼저 하는 이유가 여기 있다 —
재현하면서 **개선 전 쿼리 수를 세어 두어야** 개선 후 숫자가 의미를 갖는다.
`outcome` 에 "쿼리 N개 → M개" 를 그대로 적는다.
Fetch Join 으로 못 잡는 경우(컬렉션 둘 이상, 페이징)를 `limitation` 에 적는다.

### 6주차 · 2026-09-14 ~ 2026-09-20 — Transaction

**학습**
- ACID
- Isolation Level
- Dirty Read / Non-repeatable Read / Phantom Read
- Spring `@Transactional`

**산책온**
- [ ] 산책 완료 등 상태 변경 로직 트랜잭션 설계
- [ ] 예외 발생 시 롤백 실험

`slug:` `db-isolation`(CONCEPT) · `spring-transactional`(CONCEPT) ·
`tx-boundary`(TECH_CHOICE)

"롤백 실험"은 이름은 실험이지만 숫자가 안 나온다. 체크 예외/언체크 예외별로
롤백 여부가 갈리는 것을 확인한 것이므로 `CONCEPT` 로 남기는 편이 정확하다.
트랜잭션 경계를 Service 에 둘지 어디에 둘지가 `tx-boundary`(TECH_CHOICE)다.

### 7주차 · 2026-09-21 ~ 2026-09-27 — Lock / 동시성

**학습**
- Race Condition / Lost Update
- Optimistic Lock / Pessimistic Lock

**산책온**
- [ ] 동시성 발생 가능 영역 선정
- [ ] 동시 요청 테스트
- [ ] Lock 적용 전후 비교

`slug:` `db-lock`(CONCEPT) · `optimistic-vs-pessimistic-lock`(TECH_CHOICE) ·
`race-condition`(EXPERIMENT)

"Lock 적용 전후 비교"는 두 가지가 섞여 있다 — 정합성(깨지던 것이 안 깨진다)과
성능(처리량이 얼마나 떨어지는가). 둘 다 숫자로 적는다.
락을 걸어서 잃은 것을 `limitation` 에 적지 않으면 이 기록은 반쪽이다.

### 8주차 · 2026-09-28 ~ 2026-10-04 — 테스트 전략

**학습**
- JUnit5 / Mockito
- Unit Test / Integration Test / Repository Test

**산책온**
- [ ] Service Unit Test
- [ ] Repository Test
- [ ] Controller Integration Test
- [ ] 무엇을 어떤 테스트로 검증했는지 정리

`slug:` `test-strategy`(TECH_CHOICE) · `mockito-unit-test`(CONCEPT) ·
`spring-integration-test`(CONCEPT)

"무엇을 어떤 테스트로 검증했는지 정리"가 `test-strategy` 의 본체다.
무엇을 **테스트하지 않기로 했는지**와 그 이유가 `rationale` 에 들어가야
면접에서 쓸 수 있는 기록이 된다.

### 9주차 · 2026-10-05 ~ 2026-10-11 — DB 성능 최적화

**학습**
- Execution Plan
- Composite Index / Selectivity / Covering Index

**산책온**
- [ ] EXPLAIN 기반 Slow Query 분석
- [ ] 인덱스 적용
- [ ] 응답시간/실행계획 Before & After 기록

`slug:` `db-execution-plan`(CONCEPT) · `db-index`(EXPERIMENT, 4주차와 동일 슬러그) ·
`composite-index`(EXPERIMENT)

인덱스를 걸어서 느려지거나 안 쓰이는 경우가 반드시 한 번은 나온다.
그게 가장 좋은 기록이다 — `TROUBLESHOOTING` 으로 따로 남기고 원인을 적는다.
쓰기 성능과 저장공간이라는 대가를 `limitation` 에 적는다.

### 10주차 · 2026-10-12 ~ 2026-10-18 — Redis 기본

**학습**
- String / Hash / List / Set / Sorted Set
- TTL / Eviction

**산책온**
- [ ] Docker Redis 구성
- [ ] Spring Redis 연결
- [ ] 캐시 적용 대상 선정

`slug:` `redis-data-types`(CONCEPT) · `redis-ttl-eviction`(CONCEPT) ·
`cache-target-selection`(TECH_CHOICE)

"캐시 적용 대상 선정"이 이 주의 핵심 기록이다 —
**무엇을 캐시하지 않기로 했는지와 그 이유**가 11~12주차 이야기의 전제가 된다.

### 11주차 · 2026-10-19 ~ 2026-10-25 — Cache

**학습**
- Cache Aside
- Write Through / Write Back
- Cache Invalidation

**산책온**
- [ ] 외부 지도 API 응답 캐싱
- [ ] 추천 후보 또는 지역 인기 코스 캐싱
- [ ] TTL 정책 정의

`slug:` `cache-aside`(TECH_CHOICE) · `cache-invalidation`(CONCEPT) ·
`cache-ttl-policy`(TECH_CHOICE)

`cache-aside` 는 31주차 예시 문장에 직접 등장하는 주제다.
Write Through/Back 을 안 고른 이유까지 `rationale` 에 있어야 그 문장이 만들어진다.
TTL 을 그 숫자로 정한 근거가 없으면 면접에서 가장 먼저 무너지는 지점이다.

### 12주차 · 2026-10-26 ~ 2026-11-01 — 성능 테스트

**학습/도구**
- k6
- Throughput / Average Latency / p95 / p99 / Error Rate

**산책온**
- [ ] Redis 적용 전 테스트
- [ ] Redis 적용 후 테스트
- [ ] 병목과 개선 효과 문서화

`slug:` `k6-load-test`(CONCEPT) · `latency-p95`(CONCEPT) ·
`redis-cache-effect`(EXPERIMENT)

**이 주에 11주차 기록이 완성된다.** 10~12주차 세 주가 `cache-aside` 한 편의
"선택 → 구현 → 측정 → 결과"다. 측정 결과를 `cache-aside` 슬러그로도 한 건 남겨
초안 하나에 전부 모이게 하는 편이 낫다.
평균이 아니라 p95/p99 를 적는다 — 평균은 면접에서 되물음을 받는다.

### 13주차 · 2026-11-02 ~ 2026-11-08 — RabbitMQ 기본

**학습**
- Producer / Consumer
- Queue / Exchange / Binding / Routing Key

**StackUp**
- [ ] 기존 GitHub 분석 비동기 구조 재점검
- [ ] 메시지 흐름 다이어그램 작성

`slug:` `rabbitmq-basics`(CONCEPT) · `rabbitmq-exchange-routing`(CONCEPT) ·
`sync-to-async`(TECH_CHOICE)

`sync-to-async` 가 StackUp 서사의 뿌리다 — 31주차 예시 문장 두 번째가 이것이다.
"왜 동기로 두면 안 됐는가"를 응답시간 숫자로 적어 두면 그 문장이 저절로 나온다.

### 14주차 · 2026-11-09 ~ 2026-11-15 — ACK / Retry

**학습**
- ACK / NACK
- Auto ACK / Manual ACK
- Retry

**StackUp**
- [ ] Consumer 실패 시나리오 구현
- [ ] 재시도 정책 설정
- [ ] 장애 재현

`slug:` `rabbitmq-ack`(TECH_CHOICE) · `rabbitmq-retry`(TECH_CHOICE) ·
`consumer-failure`(TROUBLESHOOTING)

Auto ACK 를 쓰지 않은 이유가 `rabbitmq-ack` 의 `rationale` 이다.
재시도 횟수·간격을 그 값으로 정한 근거가 없으면 숫자가 임의값으로 들린다.

### 15주차 · 2026-11-16 ~ 2026-11-22 — DLQ / Reliability

**학습**
- Poison Message
- Durable Queue
- Message Persistence

**StackUp**
- [ ] Main Queue → Retry → DLQ 구성
- [ ] 실패 메시지 추적 방법 정리

`slug:` `rabbitmq-dlq`(TECH_CHOICE) · `poison-message`(TROUBLESHOOTING) ·
`message-persistence`(TECH_CHOICE)

Persistence 를 켜서 잃은 처리량이 있으면 그 숫자가 `limitation` 이다.
"DLQ 에 쌓인 메시지를 실제로 어떻게 다시 넣는가"까지 적어야 운영 이야기가 된다.

### 16주차 · 2026-11-23 ~ 2026-11-29 — Idempotency + SSE

**StackUp**
- [ ] 중복 메시지 처리
- [ ] Consumer 재시작 실험
- [ ] SSE 연결 끊김/재연결 처리
- [ ] 동일 작업 중복 수행 방지

`slug:` `idempotency`(TECH_CHOICE) · `sse-reconnect`(TROUBLESHOOTING) ·
`consumer-restart`(EXPERIMENT)

멱등키를 무엇으로 잡았는지, 그 키를 어디에 얼마나 보관하는지가 `idempotency` 의 본체다.
보관 기간을 넘긴 중복은 못 막는다 — 그게 `limitation` 이다.

### 17주차 · 2026-11-30 ~ 2026-12-06 — Kafka 기본

**학습**
- Broker / Topic / Partition / Offset
- Producer / Consumer

**실습**
- [ ] Docker Kafka 환경 구성
- [ ] 기본 Producer/Consumer 실습

`slug:` `kafka-basics`(CONCEPT) · `kafka-partition-offset`(CONCEPT)

17~19주차는 StackUp 에 넣기 위한 학습이 아니라 **20주차에 안 넣기로 결정하기 위한**
학습일 수 있다. 그 경우에도 여기 기록이 있어야 20주차 ADR 이 근거를 갖는다.

### 18주차 · 2026-12-07 ~ 2026-12-13 — Consumer Group / Partition

**학습/실험**
- [ ] Partition 1 + Consumer 1
- [ ] Partition 3 + Consumer 3
- [ ] 처리량 차이 비교

`slug:` `kafka-consumer-group`(CONCEPT) · `kafka-partition-throughput`(EXPERIMENT)

처리량이 3배가 안 나오는 것이 정상이다. **안 나온 이유를 적는 것**이 이 실험의 값이다.

### 19주차 · 2026-12-14 ~ 2026-12-20 — Kafka Reliability

**학습**
- At-most-once / At-least-once / Exactly-once
- Offset Commit
- Rebalancing
- Replication

**실습**
- [ ] Consumer 장애 실험
- [ ] Offset 처리 방식 비교

`slug:` `kafka-delivery-semantics`(CONCEPT) · `kafka-offset-commit`(EXPERIMENT) ·
`kafka-rebalancing`(TROUBLESHOOTING)

16주차 `idempotency` 와 여기 `at-least-once` 가 같은 이야기의 양쪽이다.
초안을 쓸 때 두 슬러그를 함께 꺼내 읽는다.

### 20주차 · 2026-12-21 ~ 2026-12-27 — RabbitMQ vs Kafka

**StackUp 기준 비교**
- Task Queue vs Event Stream
- Routing / Replay / Ordering
- Consumer 모델 / Throughput

**산출물**
- [ ] StackUp 에 RabbitMQ 와 Kafka 중 무엇이 적절한지 ADR 작성
- [ ] 기술을 넣지 않는 이유까지 설명 가능하게 정리

`slug:` `rabbitmq-vs-kafka`(TECH_CHOICE) · `task-queue-vs-event-stream`(CONCEPT)

**31주 통틀어 가장 중요한 단일 기록이다.** 후보 둘, 각각의 장단점,
StackUp 의 어떤 특성 때문에 이것을 골랐는지, 고른 것의 단점을 어떻게 보완했는지 —
이 네 덩어리가 다 있어야 한다. 13~19주차 기록 전부가 이 한 편의 재료다.
"기술을 넣지 않는 이유"도 같은 기록의 `rationale` 안에 적는다.

### 21주차 · 2026-12-28 ~ 2027-01-03 — Docker

**학습**
- Image / Container / Layer
- Volume / Network
- Dockerfile / Multi-stage Build
- Docker Compose

**산책온**
- [ ] Spring + Redis + DB Compose 구성
- [ ] 이미지 빌드 최적화

`slug:` `dockerfile-multistage`(EXPERIMENT) · `docker-compose`(CONCEPT) ·
`docker-image-optimization`(EXPERIMENT)

"이미지 빌드 최적화"는 숫자가 바로 나온다 — 이미지 크기 MB, 빌드 시간 초.
바꾸기 전 값을 먼저 적어 둔다.

### 22주차 · 2027-01-04 ~ 2027-01-10 — Linux + Network

**Network**
- TCP / UDP / DNS
- HTTP / HTTPS / TLS
- NAT / Routing / Subnet

**Linux**
- ip, ss, curl, dig, ping, traceroute, tcpdump

**실습**
- [ ] 개인 Ubuntu 서버에서 네트워크 흐름 추적
- [ ] tcpdump 로 요청 패킷 확인

`slug:` `net-tcp`(CONCEPT) · `net-dns`(CONCEPT) · `net-tls`(CONCEPT) ·
`net-subnet-nat`(CONCEPT)

**화요일 CS 루틴과 같은 계열을 그대로 쓴다.** 이 주에 몰아서 하는 것이지
새 주제가 아니다. 여기서 쌓인 `net-*` 기록이 24주차 VPC 설계의 전제이고,
30주차 CS 집중에서 다시 읽는다.

### 23주차 · 2027-01-11 ~ 2027-01-17 — Nginx / Reverse Proxy

**학습**
- Reverse Proxy / Forward Proxy
- TLS Termination
- Load Balancing
- Keep Alive

**산책온**
- [ ] Internet → Nginx → Spring 구조 구성
- [ ] HTTPS 적용

`slug:` `nginx-reverse-proxy`(TECH_CHOICE) · `nginx-tls-termination`(CONCEPT) ·
`load-balancing`(CONCEPT)

HTTPS 적용은 거의 확실히 한 번은 막힌다(인증서 발급, 리다이렉트 루프, 혼합 콘텐츠).
막힌 것을 `TROUBLESHOOTING` 으로 남긴다 — 이 주의 가장 쓸모 있는 기록이 그것이다.

### 24주차 · 2027-01-18 ~ 2027-01-24 — AWS Network

**학습**
- VPC / CIDR
- Public / Private Subnet
- Route Table
- Internet Gateway / NAT Gateway
- Security Group / NACL

**산책온**
- [ ] VPC 설계
- [ ] Public/Private Subnet 분리
- [ ] ALB / Application / RDS 네트워크 구조 설계

`slug:` `aws-vpc`(TECH_CHOICE) · `public-private-subnet`(TECH_CHOICE) ·
`nat-gateway`(TECH_CHOICE) · `security-group-nacl`(CONCEPT)

CIDR 를 그 범위로 자른 근거를 `rationale` 에 적는다. 나중에 못 늘린다.
NAT Gateway 는 비용이 크다 — 쓸지 말지의 판단과 그 비용이 `nat-gateway` 의 본체다.
원본이 "네트워크 관심은 AWS VPC·Linux 네트워크 실습과 연계해 확장한다"고 적은 지점이
여기다. 22주차 `net-subnet-nat` 기록을 옆에 두고 읽는다.

### 25주차 · 2027-01-25 ~ 2027-01-31 — AWS Application

**산책온**
- [ ] ALB
- [ ] EC2 또는 ECS
- [ ] RDS
- [ ] ElastiCache
- [ ] S3
- [ ] Route53
- [ ] CloudWatch
- [ ] 실제 운영환경 배포

`slug:` `ec2-vs-ecs`(TECH_CHOICE) · `aws-rds`(TECH_CHOICE) ·
`aws-elasticache`(TECH_CHOICE) · `aws-deploy`(TROUBLESHOOTING)

원본의 "EC2 **또는** ECS" 가 곧 `TECH_CHOICE` 한 건이라는 신호다.
`aws-elasticache` 는 10~12주차 로컬 Redis 와 무엇이 달랐는지를 적는 자리다.
첫 운영 배포는 반드시 막힌다. 막힌 것들을 `aws-deploy` 아래 여러 건으로 쌓는다.

### 26주차 · 2027-02-01 ~ 2027-02-07 — Terraform + CI/CD

**Terraform**
- Provider / Resource / Variable / Output / State / Module

**CI/CD**
- GitHub Actions → Build → Test → Docker Image → Deploy

**산책온**
- [ ] AWS 주요 인프라 IaC 전환
- [ ] CI/CD 파이프라인 구축

`slug:` `terraform-state`(CONCEPT) · `terraform-module`(TECH_CHOICE) ·
`github-actions-pipeline`(TECH_CHOICE)

`terraform-state` 는 상태 파일을 어디에 두기로 했는지(로컬/S3/잠금)가 핵심이다.
"25주차에 콘솔로 만든 것을 코드로 옮길 때 무엇이 안 맞았는가"가
이 주의 가장 좋은 `TROUBLESHOOTING` 재료다.

### 27주차 · 2027-02-08 ~ 2027-02-14 — Kubernetes 기본

**학습**
- Pod / ReplicaSet / Deployment
- Service / Ingress
- ConfigMap / Secret

**실습**
- [ ] kind 또는 minikube 구성
- [ ] 산책온 Docker Image 배포

`slug:` `k8s-pod-deployment`(CONCEPT) · `k8s-service-ingress`(CONCEPT) ·
`k8s-configmap-secret`(CONCEPT)

이 주는 `CONCEPT` 위주가 맞다. 원본이 K8s 를 "직접 적용 + 개념 설명" 등급으로
둔 것과 일치한다 — 깊게 판 척하지 않는 것이 면접에서 안전하다.

### 28주차 · 2027-02-15 ~ 2027-02-21 — Kubernetes 운영 + Monitoring

**학습**
- Liveness Probe / Readiness Probe
- Rolling Update
- HPA

**Monitoring**
- Prometheus / Grafana
- CPU / Memory / JVM / HTTP Latency / Error Rate

**실습**
- [ ] 운영 지표 대시보드 구성
- [ ] 현재 산책온 규모에 K8s 가 꼭 필요한지 평가 문서 작성

`slug:` `k8s-probe`(CONCEPT) · `k8s-hpa`(EXPERIMENT) ·
`prometheus-grafana`(CONCEPT) · `k8s-necessity`(TECH_CHOICE)

**`k8s-necessity` 가 이 주의 진짜 산출물이다.** "지금 규모에는 필요 없다"는 결론도
근거가 붙으면 강한 기록이다 — 20주차 "기술을 넣지 않는 이유"와 같은 종류다.
자기가 쓴 기술을 안 써도 된다고 말할 수 있는 것이 이 로드맵의 목표에 가장 가깝다.

### 29주차 · 2027-02-22 ~ 2027-02-28 — 프로젝트 총정리

> 이 시점부터 새로운 기술 추가 금지.

**산책온**
- [ ] Architecture
- [ ] DB 설계 / JPA
- [ ] Redis / Performance
- [ ] AWS / Infra
- [ ] 대표 Troubleshooting 3개

**StackUp**
- [ ] RabbitMQ / SSE
- [ ] Retry / DLQ / Idempotency
- [ ] Kafka 비교
- [ ] 대표 Troubleshooting 3개

`slug:` **새 슬러그를 만들지 않는다.**

원본의 "새로운 기술 추가 금지"를 기록 쪽으로 옮기면 "새 슬러그 추가 금지"다.
이 주에 하는 일은 기존 슬러그로 **되돌아가 빈 필드를 채우는 것**이다.
주제 화면의 "부족한 필드" 목록과 초안의 `TODO:` 줄이 이 주의 작업 목록 그 자체다.
`limitation` 과 `interview` 가 비어 있는 기록부터 채운다.
"대표 Troubleshooting 3개"는 새로 쓰는 게 아니라 쌓인 것 중에서 고르는 일이다.

### 30주차 · 2027-03-01 ~ 2027-03-07 — CS 집중

- [ ] Java: JVM / GC / Collection / Concurrency
- [ ] Spring: DI / MVC / Transaction / JPA
- [ ] DB: Index / Transaction / Lock
- [ ] Network: TCP / HTTP / DNS / TLS
- [ ] OS: Process / Thread / Memory

`slug:` 새 슬러그는 `jvm-gc` · `java-concurrency` 둘뿐. 나머지는 전부 재사용 —
`db-index` · `db-transaction` · `db-lock` · `net-tcp` · `net-http` · `net-dns` ·
`net-tls` · `os-process-thread` · `os-memory` · `spring-di` · `spring-transactional`

재사용이 핵심이다. 30주차에 `db-index-review` 같은 새 슬러그를 만들면
4주차·9주차 기록과 갈라져 한 주제가 세 조각이 된다.
같은 슬러그로 다시 남기면 그 주제의 초안 한 편이 학습·측정·복습을 다 담는다.

### 31주차 · 2027-03-08 ~ 공채 — 이력서 / 면접

**설명 방식 전환**
- 기술 이름만 나열하지 않는다.
- **문제 → 선택 → 구현 → 측정 → 결과 → 한계** 순서로 설명한다.

**예시**
> 외부 지도 API 호출이 추천 응답시간의 주요 병목이라고 판단해 Cache Aside 방식으로
> Redis 를 적용하고 TTL 및 Cache Miss 전략을 설계했다.

> GitHub Repository 분석 작업이 장시간 수행되어 HTTP 요청과 작업 수행을 분리하기 위해
> RabbitMQ 기반 비동기 처리 구조를 도입했다.

`slug:` **새 슬러그 없음. 이 주에는 기록이 아니라 초안을 만든다.**

§0.1 에서 앞으로 끌어올린 여섯 단계가 원래 있던 자리가 여기다.
30주 동안 형식을 지켰다면 이 주에 할 일은 주제 화면에서 슬러그를 골라
[초안 만들기] 를 누르는 것뿐이다. 조립기가 여섯 단으로 묶어 준다.
남아 있는 `TODO:` 줄이 곧 아직 대답할 수 없는 질문이고, 이 주에 그것만 채운다.

---

## 4. 매주 공통 루틴

### 평일
- Java / Spring / DB 기본기
- 해당 주차 핵심 기술 학습
- 프로젝트 적용

### 주 3회 CS

원본의 요일 배치는 그대로 두고, 슬러그 접두어만 정한다.
**세 계열은 31주 내내 같은 이름을 쓴다.** 매주 새 이름을 만들면
30주차 CS 집중에서 되읽을 덩어리가 남지 않는다.

- **화요일 · Network → `net-` 계열**
  `net-tcp` · `net-udp` · `net-http` · `net-tls` · `net-dns` ·
  `net-subnet-nat` · `net-socket` · `net-load-balancing`
- **목요일 · OS → `os-` 계열**
  `os-process-thread` · `os-context-switch` · `os-scheduling` · `os-memory` ·
  `os-virtual-memory` · `os-io` · `os-deadlock`
- **토요일 · DB → `db-` 계열**
  `db-index` · `db-transaction` · `db-isolation` · `db-lock` ·
  `db-normalization` · `db-join` · `db-execution-plan`

**세 계열의 kind 는 기본적으로 `CONCEPT` 다.** 다만 프로젝트에 적용해
숫자가 나오면 같은 슬러그에 `EXPERIMENT` 로 한 건 더 남긴다 —
슬러그를 바꾸지 않는다. 9주차의 `db-index` 가 그 예다.
개념과 측정이 같은 슬러그 아래 있어야 초안 한 편이 완성된다.

`body` 는 반드시 내 말로 쓴다. 요약을 붙여넣으면 기록 건수만 늘고
30주차에 읽을 것이 없다.

### 주말
- 프로젝트 구현
- 성능/장애 테스트
- 주간 학습 정리

**주간 학습 정리 = 초안 만들기.** 주말에 `/t` 화면을 열어
그 주에 3건 이상 쌓인 슬러그를 하나 골라 [초안 만들기] 를 누른다.
빈 절의 `TODO:` 가 그 주에 못 본 것이고, 그게 다음 주 첫 질문이다.

### 매주 반드시 하나 이상 남길 것

- [ ] 코드 → 별도 kind 없음. 기록에 git 스냅샷으로 자동으로 붙는다
- [ ] 실험 결과 → `kind='EXPERIMENT'`
- [ ] Troubleshooting → `kind='TROUBLESHOOTING'`
- [ ] Architecture Decision Record → `kind='TECH_CHOICE'`

(§0.3 에 각 항목을 언제 부르는지 적었다. CS 루틴은 `kind='CONCEPT'` 다.)

---

## 5. 3월 최종 포지셔닝

> **Java/Spring 기반 서비스 백엔드를 설계하고 DB·캐시 성능을 개선했으며,
> 메시지 기반 비동기 처리와 클라우드 운영환경까지 경험한 신입 백엔드 엔지니어**

추가 지원 가능 직무: Backend / Cloud / Infra / DevOps.
네트워크 관심은 AWS VPC·Linux 네트워크 실습과 연계해 확장한다.

---

## 부록 A. 권장 topic_slug 전체 목록

`local/src/warruru_local/topics.py` 의 권장 슬러그 상수는 이 목록에서 온다.
옮기는 것은 사람이 한다(§0.5). 중복 등장하는 슬러그는 한 번만 적었다.

### CS 루틴 계열 (31주 내내 재사용)

- `net-tcp` `net-udp` `net-http` `net-tls` `net-dns` `net-subnet-nat`
  `net-socket` `net-load-balancing`
- `os-process-thread` `os-context-switch` `os-scheduling` `os-memory`
  `os-virtual-memory` `os-io` `os-deadlock`
- `db-index` `db-transaction` `db-isolation` `db-lock`
  `db-normalization` `db-join` `db-execution-plan`

### Java / Spring

- `spring-di` `spring-mvc` `filter-vs-interceptor` `dto-separation`
  `api-error-handling` `spring-transactional` `tx-boundary`
- `jvm-gc` `java-concurrency`
- `test-strategy` `mockito-unit-test` `spring-integration-test`

### JPA / RDBMS

- `package-structure` `domain-erd` `entity-association`
- `jpa-persistence-context` `jpa-lazy-loading` `jpa-n-plus-one`
  `jpa-fetch-join` `jpa-batch-size` `querydsl`
- `composite-index` `optimistic-vs-pessimistic-lock` `race-condition`

### Redis / 성능

- `redis-data-types` `redis-ttl-eviction` `cache-target-selection`
- `cache-aside` `cache-invalidation` `cache-ttl-policy`
- `k6-load-test` `latency-p95` `redis-cache-effect`

### 메시징

- `sync-to-async` `rabbitmq-basics` `rabbitmq-exchange-routing`
  `rabbitmq-ack` `rabbitmq-retry` `rabbitmq-dlq`
  `poison-message` `message-persistence` `consumer-failure`
- `idempotency` `sse-reconnect` `consumer-restart`
- `kafka-basics` `kafka-partition-offset` `kafka-consumer-group`
  `kafka-partition-throughput` `kafka-delivery-semantics`
  `kafka-offset-commit` `kafka-rebalancing`
- `rabbitmq-vs-kafka` `task-queue-vs-event-stream`

### 인프라 / 클라우드

- `dockerfile-multistage` `docker-compose` `docker-image-optimization`
- `nginx-reverse-proxy` `nginx-tls-termination` `load-balancing`
- `aws-vpc` `public-private-subnet` `nat-gateway` `security-group-nacl`
- `ec2-vs-ecs` `aws-rds` `aws-elasticache` `aws-deploy`
- `terraform-state` `terraform-module` `github-actions-pipeline`
- `k8s-pod-deployment` `k8s-service-ingress` `k8s-configmap-secret`
  `k8s-probe` `k8s-hpa` `prometheus-grafana` `k8s-necessity`

---

## 부록 B. 이 문서를 고칠 때

- 주차 배치와 학습 항목은 노션 원본이 정본이다. 여기서 임의로 바꾸지 않는다.
- 슬러그를 고치거나 더하면 `topics.py` 상수도 같이 고친다. 자동 반영은 없다.
- **이미 기록이 쌓인 슬러그의 이름은 바꾸지 않는다.** 바꾸면 그 주제가 둘로 갈라진다.
  꼭 바꿔야 하면 이름만 바꾸는 게 아니라 기존 행의 `topic_slug` 도 함께 고쳐야 하고,
  그건 화면이 아니라 SQL 한 줄로 한다(별칭 병합 UI 는 만들지 않는다).
- 진도·주차·추천 기능을 이 문서에 붙이자는 제안이 나오면 §0.6 을 먼저 읽는다.
  기록이 몇 주 쌓인 뒤 실제 데이터를 보고 설계하기로 한 항목이다.

**Last Updated:** 2026-08-18
