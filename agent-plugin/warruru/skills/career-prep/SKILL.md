---
name: career-prep
description: Compare target-company job postings kept in the user's Notion archive against the learning records in the local Warruru daemon, and write per-company prep notes to ~/.warruru/career/. Use when the user asks about 회사별 준비 상태, 공고 기술스택 대조, 빈 곳이나 다음에 공부할 주제, 자소서 문항에 붙일 경험, or 포트폴리오 준비.
---

# 회사별 준비 대조

공고가 요구하는 것과 **내가 실제로 남긴 기록**을 맞춰 본다.
결과물의 핵심은 준비된 것이 아니라 **빈 곳**이다 — 그 자리가 다음 주에 공부하고
기록할 목록이고, 면접에서 대답 못 할 자리다.

## 자료가 사는 곳

- **공고 원본** — 노션 DB `백엔드 신입/인턴 채용공고 아카이브`.
  속성: `회사` `공고명` `채용유형` `신뢰도` `확인 기술스택` `출처 링크` `백엔드 직무`.
  **사람이 관리한다.** 스크랩도 사람이 한다.
- **기록** — 로컬 데몬. `get_topic_records` 로 읽는다.
- **산출물** — `~/.warruru/career/{회사-슬러그}.md`.

### 세 가지를 어긴 적이 없어야 한다

1. **저장소 안에 쓰지 않는다.** origin 이 public 이다. 초안이
   `~/.warruru/drafts/` 로 나간 것과 같은 이유다.
2. **단방향이다.** 노션 → 로컬. 대조 결과를 노션에 되쓰지 않는다.
   원본이 두 곳이 되면 어느 쪽이 맞는지 아무도 모른다.
3. **자소서 본문은 노션에 쓴다.** 로컬로 복사하지 않는다. 여기서 하는 일은
   문항에 **붙일 기록을 찾아 주는 것**까지다.

## 하는 일 넷

1. 노션 DB 를 질의한다. 회사가 지정되지 않았으면 무엇을 볼지 되묻는다.
2. `확인 기술스택` 을 아래 표로 슬러그로 바꾼다.
3. `get_topic_records` 로 슬러그별 기록을 읽는다.
4. 회사 파일을 6단으로 쓴다.

**`신뢰도` 가 `C: 신입 공고는 있으나 기술스택 불명확` 이면 대조에 쓰지 않는다.**
근거가 없는 기술 목록으로 만든 공부 계획은 근거가 없다. 그 행은 "공고 보강 필요"
로만 적는다.

## 공고 기술 → 로드맵 슬러그

원본은 `local/src/warruru_local/topics.py` 의 권장 슬러그 100개다.
**이 표가 그 100개를 빠짐없이 덮는다** — 표에 없는 기술이 공고에 나오면
로드맵 밖이라는 뜻이므로, 슬러그를 지어내지 말고 그대로 적어 사용자에게 알린다.

| 공고에 흔히 나오는 말 | 슬러그 |
|---|---|
| Java / JVM | `jvm-gc` `java-concurrency` |
| Spring / Spring Boot | `spring-di` `spring-mvc` `spring-transactional` `tx-boundary` `filter-vs-interceptor` |
| REST API / API 설계 | `api-error-handling` `dto-separation` `net-http` |
| JPA / ORM | `jpa-persistence-context` `jpa-lazy-loading` `jpa-n-plus-one` `jpa-fetch-join` `jpa-batch-size` `entity-association` `querydsl` |
| RDBMS / SQL / DB 설계 | `db-index` `db-transaction` `db-isolation` `db-lock` `db-normalization` `db-join` `db-execution-plan` `composite-index` `domain-erd` |
| 동시성 / 데이터 정합성 | `optimistic-vs-pessimistic-lock` `race-condition` `idempotency` |
| Redis / 캐싱 | `redis-data-types` `redis-ttl-eviction` `cache-target-selection` `cache-aside` `cache-invalidation` `cache-ttl-policy` `redis-cache-effect` |
| RabbitMQ / 메시지 큐 | `rabbitmq-basics` `rabbitmq-exchange-routing` `rabbitmq-ack` `rabbitmq-retry` `rabbitmq-dlq` `poison-message` `message-persistence` `consumer-failure` `consumer-restart` |
| Kafka / 이벤트 스트림 | `kafka-basics` `kafka-partition-offset` `kafka-consumer-group` `kafka-partition-throughput` `kafka-delivery-semantics` `kafka-offset-commit` `kafka-rebalancing` `rabbitmq-vs-kafka` `task-queue-vs-event-stream` |
| 비동기 / 실시간 | `sync-to-async` `sse-reconnect` |
| 성능 / 부하 테스트 | `k6-load-test` `latency-p95` |
| Docker / 컨테이너 | `dockerfile-multistage` `docker-compose` `docker-image-optimization` |
| Kubernetes | `k8s-pod-deployment` `k8s-service-ingress` `k8s-configmap-secret` `k8s-probe` `k8s-hpa` `k8s-necessity` |
| CI/CD | `github-actions-pipeline` |
| 모니터링 / 옵저버빌리티 | `prometheus-grafana` |
| AWS / 클라우드 인프라 | `aws-vpc` `public-private-subnet` `nat-gateway` `security-group-nacl` `ec2-vs-ecs` `aws-rds` `aws-elasticache` `aws-deploy` |
| Terraform / IaC | `terraform-state` `terraform-module` |
| Nginx / 로드밸런싱 | `nginx-reverse-proxy` `nginx-tls-termination` `load-balancing` `net-load-balancing` |
| 네트워크 | `net-tcp` `net-udp` `net-tls` `net-dns` `net-subnet-nat` `net-socket` |
| Linux / OS | `os-process-thread` `os-context-switch` `os-scheduling` `os-memory` `os-virtual-memory` `os-io` `os-deadlock` |
| 테스트 | `test-strategy` `mockito-unit-test` `spring-integration-test` |
| 아키텍처 / 구조 | `package-structure` |


## 회사 파일

앞머리(front matter)와 본문으로 나눈다. **나누는 기준은 변하는 속도다.**

- **앞머리** — 공고가 요구하는 것. 공고 뜰 때 한 번 정해지고 잘 안 변한다.
  화면이 이걸 읽어 배지·막대·표를 그린다.
- **본문** — 산문. 설명회 메모, 자소서 방향, 회사에 대한 판단.

**앞머리에 숫자를 적지 마라.** "기록 0건" 같은 것은 쓰는 순간 낡는다.
내가 얼마나 갖췄는지는 화면이 열 때마다 DB 에서 다시 센다 —
그래서 기록을 하나 남기면 모든 회사 화면의 숫자가 같이 움직인다.

```markdown
---
company: 현대오토에버
role: 엔터프라이즈IT / 백엔드
posting: 2026년 상반기 신입사원 채용 상세 모집요강
confidence: A
source: https://…
deadline: 2026-03-17
gates:
  - 영어회화자격(OPIc 또는 토익스피킹) | 미확인
  - 2026년 8월 이전 졸업 | 충족
required:
  - Java 21 | jvm-gc, java-concurrency
  - RDBMS | db-index, db-transaction, db-isolation
unmapped: MSA
---

# 메모

산문은 여기부터.
```

- `gates` 는 **지원 자체의 전제조건**이다. 어학·졸업연도·전공처럼 못 채우면
  기술 준비가 무의미해지는 것. 오른쪽은 `충족` 이거나 그 밖이고,
  **`충족` 이 아니면 전부 막힌 것으로 본다** — 모르는 것은 갖춘 것이 아니다.
- `required` 왼쪽은 **공고의 말 그대로**, 오른쪽은 위 표의 슬러그.
- `unmapped` 는 로드맵에 대응이 없는 것(`MSA` 등). 슬러그를 지어내지 마라.
- `deadline` 은 `YYYY-MM-DD`. 모르면 줄째로 뺀다.

파일 이름이 URL 이 된다. `^[a-z0-9][a-z0-9-]{0,63}$` 를 지켜라 —
`hyundai-autoever.md` · `lg-cns.md`. 벗어나면 화면이 열지 않는다.

## 자격증 노트

`~/.warruru/career/certs/{열쇠}.md`. 열쇠는 `topics.py` 의 `CERTIFICATIONS`
에 있다 — `jeongcheogi` · `sqld` · `network-2` · `linux-2` · `aws-saa`.

**자격증 노트는 시험 그 자체를 정리하는 문서다**(2026-09-01 확정).
슬러그 목록이 아니라 **단계(필기·실기, 1차·2차)** 가 주인공이다.
단계마다 과목 · 문제 유형 · 공부법 · 남은 일정이 다르기 때문이다.

화면이 먼저 답하는 것은 "언제 접수하나" 이고 목록은 접수일 가까운 순으로 선다.
슬러그 겹침은 맨 아래에 작게 남는다 — 기록과 잇는 유일한 끈이라 지우진 않는다.

```markdown
---
status: 필기 합격
issuer: 한국산업인력공단 (큐넷)
site: https://www.q-net.or.kr
checked: 2026-08-31
stages:
  - 필기 | 합격
  - 실기 | 준비중
links:
  - 종목 안내 | https://…
exams:
  - 2026-09-21 | 3회 실기 접수 | 9.21~9.23 · 사흘뿐이다 | | 실기
  - 2026-09-09 | 3회 필기 발표 | | 해당없음 | 필기
---

# 필기 — 끝났다

과목과 합격 기준.

# 실기 — 남은 것

## 무엇을 보나
## 문제 유형      ← 표로. 무엇이 어떤 모양으로 나오는지
## 어떻게 공부하나  ← 순서가 있는 목록으로
## 접수할 때 정할 것
```

- **`status` 는 취득 상태다** — `미시작` · `준비중` · `필기 합격` · `합격`.
  `합격` 이면 목록 맨 뒤로 가고 D-day 를 세지 않는다. 시험을 본 뒤에는
  이 줄을 고쳐라. 안 고치면 딴 자격증이 계속 재촉한다.
- `stages` 는 `이름 | 상태` 다. 이름은 자격증마다 다르다 — `필기`/`실기`,
  `1차`/`2차`, 단계가 없으면 `단일 시험`.
- `exams` 는 `날짜 | 이름 | 비고 | 해당없음? | 단계` 다. 다섯째 칸의 단계
  이름이 `stages` 와 같아야 그 칸에 붙는다. 넷째 칸이 `해당없음` 이면
  **D-day 로 세지 않는다** — 앞 단계 합격자만 보는 실기처럼 지금 내가 할 수
  없는 일정이다. 못 하는 일을 카운트다운하면 그 숫자가 거짓말이 된다.
- **지난 일정을 지우지 마라.** 지우면 "이번에 놓쳤다" 는 사실까지 사라진다.
- `checked` 는 일정을 확인한 날이다. 일정은 바뀐다.
- **응시료·문항 수처럼 자주 바뀌는 숫자는 옮겨 적지 마라.** 공식 사이트
  링크(`site`)를 남기고 거기서 보게 한다. 옮겨 적는 순간 낡는다.
- 자격증의 **주제 목록은 여기 적지 않는다.** 그건 `CERTIFICATIONS` 상수이고,
  화면이 로드맵 슬러그와 맞춰 준비도를 계산한다.

## 주제 노트

`~/.warruru/career/topics/{슬러그}.md`. `/t/{슬러그}` 에 붙고,
**질문은 묶음 화면이 모아 한 장으로 만든다.**

```markdown
---
label: 해시
group: 자료구조
refs:
  - Hash | https://github.com/.../Hash.md
asks:
  - 해시 충돌을 어떻게 해결하나? 체이닝과 개방주소법의 트레이드오프는?
  - HashMap 의 조회가 평균 O(1)인데 최악이 O(n)인 이유는?
---

# 무엇을 기록하나

Redis 자료구조를 쓰며 충돌·리해싱을 실제로 만난 순간.
```

**`asks` 는 본문이 아니라 앞머리에 둔다.** 산문이면 묶음 화면이 모을 수 없다.

## 묶음 노트

`~/.warruru/career/groups/{열쇠}.md`. 앞머리 없이 산문만 있으면 된다.

**CS 지식은 이 시스템에서 "면접 문서" 다**(2026-09-01 확정). 화면을 여는
이유가 "답할 수 있나 점검" 이라, 묶음 하나가 한 장이고 질문이 주인공이며
기록 건수는 맨 아래로 간다.

머리말에는 **그 묶음을 왜 이 순서로 보는지**를 적는다 — 무엇이 자주 같이
나오는지, 로드맵의 어느 주제와 짝인지. 개념 설명은 적지 마라, 참고 링크가 있다.

- **기록이 아니다.** 기록은 *내가 한 일* 이고 이쪽은 *남이 정리해 둔 것* 이다.
  섞으면 주제 화면의 건수가 "내가 남긴 것" 을 뜻하지 않게 된다.
- `refs` 는 `http(s)` 만 걸린다. **경로를 지어내지 마라** — 저장소 트리에서
  실제로 확인한 것만 적는다. 404 가 뜨는 링크 하나가 이 화면 전체를 못 믿게 만든다.
- '확인할 것' 은 **면접에서 묻는 형태의 질문**으로 적는다. 요약을 옮겨 적으면
  원문보다 나쁜 요약이 하나 더 생길 뿐이다.

## LLM 이 할 일과 하지 않을 일

노션의 공고를 읽고 위 앞머리로 옮기는 것이 이 스킬의 일이다.
**그 옮기는 판단만 한다.**

하는 일 — 공고 산문에서 기술 키워드 뽑기 · 지원 자격 뽑기 · 마감일 찾기 ·
키워드를 슬러그로 잇기 · 본문 요약.

**하지 않는 일** 셋:

- **세지 않는다.** 내 기록이 몇 건인지는 데몬이 SQL 로 센다. 사람이나 모델이
  세면 틀리고, 틀렸다는 것을 아무도 확인하지 못한다.
- **없는 것을 채우지 않는다.** 공고에 기술스택이 없으면 `required` 를 비운다.
  다른 회사 공고나 일반적인 백엔드 상식으로 메우면, 그 위에 세운 공부 계획은
  근거가 없다. 노션의 `신뢰도` 가 `C` 인 행은 아예 대조하지 않는다.
- **원문을 대체하지 않는다.** `source` 링크와 `## 2. 요구 기술` 의 원문
  인용을 반드시 남긴다. 요약이 틀렸을 때 되짚을 곳이 거기뿐이다.

## 본문 절

앞머리가 배지·막대·표·빈 곳을 맡으므로 본문에는 **산문만** 남는다.
공고 메타나 슬러그별 건수를 여기 다시 적지 마라 — 두 곳에 있으면 어긋난다.

```markdown
# 메모

## 요구 기술 원문
공고 문장을 **그대로** 인용한다(`>` 인용문). 해석해서 바꾸지 않는다.
요약이 틀렸을 때 되짚을 곳이 여기다.

## 이 회사에 대해 아는 것
설명회·기사·직무 소개에서 안 것. 출처를 함께 적는다.

## 자소서 문항
노션 링크와 문항. 각 문항 아래에 붙일 기록의 제목과 record_id.
붙일 기록이 없으면 **없다고 쓴다.** 본문은 노션에 쓴다.

## 남은 일
확인 못 한 것. 다음 기수 일정.
```


## 지어내지 않는다

- 기록이 0건이면 0건이다. 비슷한 주제로 채우지 않는다.
- 공고에 없는 기술을 "아마 볼 것" 으로 넣지 않는다.
- 자소서 문항은 **본 것만** 적는다. 작년 문항을 올해 것처럼 쓰지 않는다.
- 회사 정보가 노션에 없으면 만들어 내지 말고 사용자에게 채워 달라고 한다.

빈 곳을 메우는 방법은 하나다 — 그 주제를 공부하고 `record_learning` 으로 남기는 것.
그러면 다음에 이 대조를 돌릴 때 그 칸이 채워진다.
