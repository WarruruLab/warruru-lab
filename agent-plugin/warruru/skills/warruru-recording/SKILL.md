---
name: warruru-recording
description: Record development learnings into the local Warruru daemon through the warruru MCP tools, and turn them into a draft. Use whenever a measurement changed, a bug was diagnosed and fixed, one option was chosen over alternatives, or a CS concept became concrete in the code — and when the user asks to organize records by topic, build a draft, or polish one. Works in any repository; the records live outside it.
---

# Warruru 기록

이 스킬은 **저장소와 무관하게** 동작한다. 기록은 코드가 아니라
`~/.warruru/warruru.db` 와 `~/.warruru/drafts/` 로 간다. 어느 프로젝트를
열어 두었든 규칙은 같다.

툴이 보이지 않으면 `warruru` MCP 서버가 안 붙은 것이다. 없는 툴을 부른 척하지
말고 그 사실을 사용자에게 말한다.

## 언제 부르는가

아래 넷 중 하나가 일어나면 **묻지 말고 그 자리에서** `record_learning` 을 부른다.
"기록할까요?" 라고 물으면 흐름이 끊기고, 끊기면 안 남는다.

- **수치가 달라졌을 때** — `kind='EXPERIMENT'`.
  전후 값을 둘 다 적는다. "빨라졌다" 가 아니라 "p95 320ms→90ms".
- **고장났다 고쳤을 때** — `kind='TROUBLESHOOTING'`.
  증상 · 진짜 원인 · 고친 방법 셋이 한 벌이다.
- **여러 후보 중 하나를 골랐을 때** — `kind='TECH_CHOICE'`.
  고른 것보다 **버린 것과 버린 이유**가 면접에서 쓰인다.
- **CS 개념을 이해했을 때** — `kind='CONCEPT'`.
  코드에서 부딪혀 알게 된 것이면 "무엇인지" 가 아니라 "그래서 지금 이 코드의
  무엇이 설명되는지" 를 적는다.
  **읽어서 안 것도 남긴다**(2026-09-01 정함). 자료구조·알고리즘처럼 만들다
  부딪히지 않는 주제가 있어서, 코드에서 만날 때까지 기다리면 영영 안 남는다.
  대신 **내 말로** 적는다 — 옮겨 적은 문장은 기록이 아니라 사본이고,
  면접에서 그대로 드러난다. 코드에서 확인한 것이 있으면 `outcome` 에 적는다.

단순 탐색 · 오타 수정 · 포맷팅 · 같은 테스트 재실행은 남기지 않는다.
한 턴에 같은 내용을 두 번 남기지 않는다.

## 어떻게 부르는가

필수는 `kind` · `topic` · `title` · `body` 넷뿐이다.
`rationale` · `outcome` · `limitation` · `interview` 는 비어도 거절당하지 않는다.

**재료가 없으면 지어내지 마라.** 특히 `limitation` 과 `rationale` 은 사용자
머릿속에만 있다. 비운 채로 저장한 다음 **그 자리에서 되물어라** —
"풀 크기를 30 이상으로 못 올린 이유가 무엇이었나요?"
답을 받으면 **응답에 실려 온 `record_id` 를 그대로 넘겨** 같은 툴을 다시 부른다.
`record_id` 없이 다시 부르면 거의 같은 기록이 하나 더 생긴다.
지어낸 문장은 면접장에서 안 나온다. 그게 이 도구의 유일한 실패 방식이다.

응답에서 읽을 것:

- `missing_fields` · `example_call` — 거절 대신 오는 것이다.
  `example_call` 은 복사해서 바로 다시 부를 수 있는 형태다.
- `missing_fields_scope` 가 `call_args` 면 그 목록은 **이번 호출 인자만** 본
  값이다(데몬이 꺼진 채 보강한 경우). 이미 채워 둔 필드를 다시 묻지 마라.
- `recommended` 가 `true` 면 로드맵 위의 주제를 정확히 짚은 것이다.
- `similar_slugs` 는 **비슷한 다른 것**만 준다. 자기 자신은 빠지므로,
  권장 슬러그를 그대로 적었을 때 비는 것이 정상이다.
- **`spool_backlog` 이 있으면 그 기록은 아직 DB 에 없다.** 데몬이 꺼져 있어
  spool 로 떨어진 것이다. 그 수가 계속 늘면 사용자에게 말한다 —
  "나중에 반영됩니다" 를 곧이곧대로 옮기지 마라.

## 주제는 이 목록에서 고른다

`topic` 은 원문 그대로 적는다. 정규화(`topic_slug`)는 시스템이 한다.

**같은 개념에 매번 같은 문자열을 쓰는 것이 이 도구의 전부다.** `connection pool`
과 `커넥션 풀` 과 `db-pool` 은 서로 다른 세 주제가 되고, 초안을 만들 때 재료가
세 조각으로 갈라진다. 시스템은 동의어를 합쳐 주지 않는다.

그래서 **아래 목록에 맞는 것이 있으면 그것을 그대로 적는다.** 한글로 적으면
한글 슬러그가 되어 이 목록과 절대 만나지 않는다. 목록에 없는 주제라면
영문 소문자 하이픈으로 짓되, 그 뒤로는 그 표기를 고수한다.

`net-tcp` · `net-udp` · `net-http` · `net-tls`
`net-dns` · `net-subnet-nat` · `net-socket` · `net-load-balancing`
`os-process-thread` · `os-context-switch` · `os-scheduling` · `os-memory`
`os-virtual-memory` · `os-io` · `os-deadlock` · `db-index`
`db-transaction` · `db-isolation` · `db-lock` · `db-normalization`
`db-join` · `db-execution-plan` · `spring-di` · `spring-mvc`
`filter-vs-interceptor` · `dto-separation` · `api-error-handling` · `spring-transactional`
`tx-boundary` · `jvm-gc` · `java-concurrency` · `test-strategy`
`mockito-unit-test` · `spring-integration-test` · `package-structure` · `domain-erd`
`entity-association` · `jpa-persistence-context` · `jpa-lazy-loading` · `jpa-n-plus-one`
`jpa-fetch-join` · `jpa-batch-size` · `querydsl` · `composite-index`
`optimistic-vs-pessimistic-lock` · `race-condition` · `redis-data-types` · `redis-ttl-eviction`
`cache-target-selection` · `cache-aside` · `cache-invalidation` · `cache-ttl-policy`
`k6-load-test` · `latency-p95` · `redis-cache-effect` · `sync-to-async`
`rabbitmq-basics` · `rabbitmq-exchange-routing` · `rabbitmq-ack` · `rabbitmq-retry`
`rabbitmq-dlq` · `poison-message` · `message-persistence` · `consumer-failure`
`idempotency` · `sse-reconnect` · `consumer-restart` · `kafka-basics`
`kafka-partition-offset` · `kafka-consumer-group` · `kafka-partition-throughput` · `kafka-delivery-semantics`
`kafka-offset-commit` · `kafka-rebalancing` · `rabbitmq-vs-kafka` · `task-queue-vs-event-stream`
`dockerfile-multistage` · `docker-compose` · `docker-image-optimization` · `nginx-reverse-proxy`
`nginx-tls-termination` · `load-balancing` · `aws-vpc` · `public-private-subnet`
`nat-gateway` · `security-group-nacl` · `ec2-vs-ecs` · `aws-rds`
`aws-elasticache` · `aws-deploy` · `terraform-state` · `terraform-module`
`github-actions-pipeline` · `k8s-pod-deployment` · `k8s-service-ingress` · `k8s-configmap-secret`
`k8s-probe` · `k8s-hpa` · `prometheus-grafana` · `k8s-necessity`

## CS 기초는 이쪽 목록에서 고른다

로드맵 100개에는 자료구조·알고리즘·컴퓨터구조·디자인패턴·웹 기초가 없다.
로드맵이 **직접 만들어 보는 것**을 다루기 때문인데, 면접에서는 이쪽을 묻는다.
그래서 목록을 하나 더 둔다.

| 묶음 | 슬러그 |
|---|---|
| 자료구조 | `ds-array-linkedlist` `ds-stack-queue` `ds-hash` `ds-tree-bst` `ds-heap` `ds-graph` `ds-btree` `ds-trie` |
| 알고리즘 | `algo-complexity` `algo-sorting` `algo-binary-search` `algo-dfs-bfs` `algo-dp` `algo-greedy` `algo-shortest-path` |
| 컴퓨터구조 | `arch-cpu` `arch-cache-memory` `arch-memory-hierarchy` `arch-floating-point` `arch-von-neumann` |
| 자바 · 런타임 | `lang-compile-process` `lang-jvm-memory` `lang-call-by-value` `lang-string-pool` `lang-collection` `lang-exception` `lang-serialization` |
| 객체지향 | `oop-solid` `oop-polymorphism` `oop-inheritance-composition` `oop-immutable` |
| 디자인패턴 | `pattern-singleton` `pattern-factory` `pattern-strategy` `pattern-observer` `pattern-template-method` `pattern-proxy` |
| 웹 기초 | `web-cookie-session` `web-http-method` `web-http-status` `web-rest` `web-jwt` `web-oauth` `web-csrf-xss` `web-was-vs-webserver` |
| 분산시스템 | `dist-cap` `dist-replication` `dist-sharding` `dist-consistent-hashing` |

**여기 것은 `recommended: true` 가 아니다.** 그 플래그는 "31주 로드맵 위인가"
를 뜻하고 이쪽은 로드맵 밖이라서다. 잘못 적은 것이 아니니 신경 쓰지 마라.

출처는 [TeachYourselfCS-KR](https://github.com/minnsane/TeachYourselfCS-KR) 과
[tech-interview-for-developer](https://github.com/gyoogle/tech-interview-for-developer) 다.

## 글로 만들 때

- 하루 끝에 `http://127.0.0.1:8787/t` 를 열면 그날 기록이 주제로 묶여 있다.
- 주제를 눌러 [초안 만들기] 를 누르면 6단 마크다운이
  `~/.warruru/drafts/YYYY/MM/` 에 생긴다. **LLM 호출은 0이다.**
- 빈 절은 `TODO:` 로 남는다. 그 자리가 곧 "면접에서 대답 못 할 부분" 이다.
  **지어내서 채우지 마라** — 기록을 보강하고 다시 만든다.
- 초안 화면이 주는 `polish topic=... draft=...` 한 줄을 받으면
  `get_topic_records` 로 재료를 읽고, 다듬은 글을 `save_draft` 로 덮어쓴다.
  그 툴의 `missing_summary` 가 비어 있는 필드를 알려준다 — **되물어라.**

## 초안은 저장소 밖에 앉는다

착지점은 `~/.warruru/drafts/YYYY/MM/` 이다. 저장소 안 경로를 인자로 넘기면
쓰기 어댑터가 예외를 던진다. 취향이 아니라 사고 방지 장치다 —
지금 열려 있는 저장소가 public 일 수 있다.
