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

## 회사 파일 6단

```markdown
# {회사} — {직무}

## 1. 공고
채용유형 · 신뢰도 · 출처 링크 · 확인한 날짜

## 2. 요구 기술
공고 원문의 키워드를 **그대로** 옮긴다. 해석해서 바꾸지 않는다.

## 3. 내 기록
슬러그별 건수. 0건도 0건이라고 쓴다.

## 4. 빈 곳          ← 이 절이 이 문서의 이유다
기록 0건인 슬러그. 공고에서 비중이 큰 순서로.

## 5. 자소서 문항
노션 링크와 문항. 각 문항 아래에 붙일 기록의 제목과 record_id.
문항에 붙일 기록이 없으면 **없다고 쓴다.**

## 6. 남은 일
마감일, 확인 못 한 것.
```

## 지어내지 않는다

- 기록이 0건이면 0건이다. 비슷한 주제로 채우지 않는다.
- 공고에 없는 기술을 "아마 볼 것" 으로 넣지 않는다.
- 자소서 문항은 **본 것만** 적는다. 작년 문항을 올해 것처럼 쓰지 않는다.
- 회사 정보가 노션에 없으면 만들어 내지 말고 사용자에게 채워 달라고 한다.

빈 곳을 메우는 방법은 하나다 — 그 주제를 공부하고 `record_learning` 으로 남기는 것.
그러면 다음에 이 대조를 돌릴 때 그 칸이 채워진다.
