"""주제 문자열의 정규화. 입력만으로 답이 나오는 순수 모듈이다.

**이 파일은 `warruru_local` 안의 어떤 모듈도 임포트하지 않는다.** 그게 존재 이유다.
`mcp/` 는 `daemon/` 을 한 번도 임포트하지 않는데, 데몬이 꺼져 spool 로 떨어진
응답에서도 `topic_slug` 와 결손 필드는 채워져야 한다. 순수 함수여야만
어댑터가 데몬 없이 혼자 계산할 수 있다.

원문 `topic` 은 사람이 적은 말이라 화면에 그대로 보여야 하고, 집계는 표기 변형에
흔들리면 안 된다. 그래서 둘을 함께 저장하고 **집계 · 필터 · 글 생성은 예외 없이
슬러그 기준**으로 한다.
"""

from __future__ import annotations

import json
import re
import unicodedata

# 슬러그로 만들 수 없는 주제가 모이는 자리. 비어 있는 집계 키를 만들 수는 없다.
# 화면의 '미분류' 구획에서 눈에 띄므로 조용히 묻히지는 않는다.
FALLBACK_SLUG = "misc"

# 유사 슬러그로 볼 최소 겹침. 너무 짧으면 아무 슬러그나 걸린다 —
# `C++` 의 슬러그 `c` 는 거의 모든 슬러그에 포함된다.
SIMILAR_MIN = 3

# 힌트 개수. SPOOL 경로(similar_recommended)와 데몬 경로(records.similar_slugs)가
# 서로 다른 개수를 돌려주면, 같은 호출의 힌트가 데몬 생사에 따라 달라진다.
SIMILAR_LIMIT = 5


def match_slugs(target: str, candidates) -> list[str]:
    """`target` 과 비슷한 후보만 남긴다. 순서는 손대지 않고 거르기만 한다.

    조건은 양쪽에 건다. 후보 쪽에 길이 조건이 없으면 짧은 쓰레기 슬러그가
    모든 힌트에 달라붙고, 에이전트는 그 힌트를 따른다.
    """
    target = (target or "").strip()
    if len(target) < SIMILAR_MIN:
        return []
    return [
        candidate for candidate in candidates
        if candidate != target
        and len(candidate) >= SIMILAR_MIN
        and (target in candidate or candidate in target)
    ]


def is_recommended(slug: str | None) -> bool:
    """이 슬러그가 31주 로드맵의 권장 목록에 있는가.

    `similar_slugs` 로는 이 사실을 알 수 없다. 그쪽은 `candidate != target`
    으로 자기 자신을 빼므로, 권장 슬러그를 **그대로** 적으면 오히려 빈 목록이
    온다. 되돌려 줄 "비슷한 다른 것" 이 없기 때문이지 목록 밖이라서가 아닌데,
    받는 쪽에서는 그 둘이 구분되지 않는다(평가 기준 A13, 2026-08-25 채점).

    그래서 값 하나를 따로 둔다. `similar_slugs` 의 의미는 손대지 않는다.

    **원문이 아니라 슬러그를 받는다.** 여기서 다시 정규화하면 규칙이 두 곳에
    살게 되고, 한쪽만 바뀌었을 때 조용히 어긋난다. 정규화는 `slugify` 한 곳이다.
    """
    return slug in _RECOMMENDED_SET


def similar_recommended(slug: str, limit: int = SIMILAR_LIMIT) -> list[str]:
    """권장 슬러그 상수 갈래만 본다. **SPOOL 응답용이다.**

    데몬이 꺼져 있으면 DB 갈래는 못 보지만 상수는 임포트 한 번이면 읽힌다.
    그래서 힌트가 가장 필요한 첫날에도 SPOOL 응답이 비지 않는다.
    """
    return sorted(match_slugs(slug, RECOMMENDED_SLUGS))[:limit]


# 비어도 거절하지 않는 필드들. 순서가 곧 결손 목록의 순서다.
OPTIONAL_FIELDS = ("rationale", "outcome", "limitation", "interview")

# 기록을 만들려면 반드시 있어야 하는 것. 예시 재호출이 이 넷을 되돌려 준다.
REQUIRED_FIELDS = ("kind", "topic", "title", "body")

_SEPARATORS = re.compile(r"[\s_]+")
_DROP = re.compile(r"[^\w-]", re.UNICODE)
_DASHES = re.compile(r"-{2,}")


def slugify(topic: str) -> str:
    """주제 원문을 집계 키로 바꾼다.

    NFKC · trim · 소문자 · 공백과 언더스코어를 하이픈으로 · 나머지 기호 제거 ·
    연속 하이픈 축약 · 양끝 하이픈 제거.

    한글은 **버리지 않는다.** 버리면 모든 한글 주제가 한 덩어리로 뭉친다.
    로드맵의 권장 슬러그는 전부 영문이라 충돌하지 않는다.

    멱등이다 — 결과를 다시 넣어도 같은 값이 나온다. 권장 슬러그 상수가
    이 성질에 기대고 있어서 테스트로 잠가 두었다.

    **알고 받는 한계.** 기호는 구분자가 아니라 그냥 지운다.
    그래서 `JPA N+1` 은 `jpa-n1` 이 되고 권장 슬러그 `jpa-n-plus-one` 과
    영영 만나지 않는다. `C++` 과 `C#` 은 둘 다 `c` 로 뭉친다.
    기호를 살리는 규칙(`+` → `-plus`)은 어느 기호까지 살릴지 끝이 없어서 넣지 않았다.
    대신 응답의 `similar_slugs` 힌트가 권장 슬러그를 먼저 보여 주는 것으로 막는다 —
    사람이 아니라 에이전트가 주제를 적으므로, 힌트를 읽고 맞추는 쪽이 싸다.
    """
    text = unicodedata.normalize("NFKC", topic or "").strip().lower()
    text = _SEPARATORS.sub("-", text)
    text = _DROP.sub("", text)
    text = _DASHES.sub("-", text).strip("-")
    return text or FALLBACK_SLUG


# 글 한 편을 쓰기에 있어야 하는 필드. 비어 있으면 그 절이 TODO 로 남는다.
MATERIAL_FIELDS = ("rationale", "outcome", "limitation", "interview")


def _has(row: dict, name: str) -> bool:
    """공백만 있는 값은 비어 있는 것으로 본다.

    `shortages` 와 `material_fill` 이 **이 함수 하나**를 쓴다. 두 곳이 다르게
    세면 재료 막대와 '부족한 필드' 문장이 같은 주제를 두고 다른 말을 한다.
    """
    return bool((row.get(name) or "").strip())


def material_fill(records: list[dict]) -> list[dict]:
    """글 한 편에 필요한 네 필드가 얼마나 찼는가. `{field, filled, total}`.

    `shortages` 는 **부족한 것만** 돌려주므로 화면에서 막대를 그릴 수 없다 —
    다 찬 필드가 목록에서 빠져 칸 수가 주제마다 달라진다.
    이 함수는 네 칸을 **항상 같은 순서로** 돌려준다. 그래야 주제 사이를
    눈으로 비교할 수 있고, 그 비교가 이 화면이 존재하는 이유다.
    """
    total = len(records)
    return [
        {
            "field": name,
            "filled": sum(1 for row in records if _has(row, name)),
            "total": total,
        }
        for name in MATERIAL_FIELDS
    ]


def shortages(records: list[dict]) -> list[dict]:
    """이 주제로 글을 쓰기에 부족한 필드. `{field, blank, total}` 목록.

    **화면과 툴이 이 함수 하나를 쓴다.** 같은 사실을 두 곳에서 따로 계산하면
    두 문구가 갈라지고, 갈라진 뒤에는 어느 쪽이 옳은지 모른다.
    순수 함수라 어댑터도 데몬 없이 부를 수 있다.
    """
    total = len(records)
    found = []
    for name in MATERIAL_FIELDS:
        blank = sum(1 for row in records if not _has(row, name))
        if blank:
            found.append({"field": name, "blank": blank, "total": total})
    return found


def normalize_topic(raw: str | None, max_length: int) -> tuple[str, str]:
    """주제 원문과 슬러그를 함께 만든다. **자른 뒤에** 슬러그를 만든다.

    순서를 바꾸면 같은 원문이 상한 근처에서 두 슬러그로 갈리고, 그 둘은 영영
    한 주제로 모이지 않는다. 어댑터(SPOOL 응답)와 데몬(저장)이 **이 함수 하나**를
    부른다 — 각자 같은 두 줄을 손으로 적으면 한쪽만 바뀌었을 때
    힌트가 알려준 슬러그와 실제 저장된 슬러그가 조용히 어긋난다.

    `limits.clamp_text` 를 여기서 부르지 않는 이유는 이 모듈이 아무것도
    임포트하지 않기 때문이다. 자르는 규칙은 인자로 받는다.
    """
    text = (raw or "")[:max_length].strip()
    return text, slugify(text)


def missing_fields(values: dict) -> list[str]:
    """비어 있는 필드 이름. 필수 넷을 먼저, 그다음 선택 넷을 정의 순서대로.

    거절하지 않고 이 목록을 응답에 실어 보낸다. 기록 여부가 100% 에이전트
    재량인 구조에서 거절은 '기록 안 하기'를 가장 안전한 선택으로 만든다.

    **필수 필드가 공백뿐이어도 여기 들어간다** (2026-08-18 확정).
    거절하면 위와 같은 이유로 기록이 줄고, 조용히 빈 채로 저장하면
    목록 화면에서 보이지 않으면서 성공한 것처럼 보인다. 둘 다 나쁘다.
    저장은 하되 결손으로 보고해서 에이전트가 곧바로 채우게 한다.
    """
    return [
        name for name in REQUIRED_FIELDS + OPTIONAL_FIELDS
        if _is_blank(values.get(name))
    ]


# 예시에 원래 값을 그대로 실을지, 자리표시자로 줄일지 가르는 길이.
# 본문은 6단 마크다운이라 길다. 통째로 실으면 응답이 기록 하나만큼 부풀고,
# 에이전트가 매 호출마다 그 비용을 낸다.
ECHO_MAX = 80


def example_call(
    values: dict, missing: list[str], record_id: str | None = None
) -> str:
    """결손 필드를 채워 같은 툴을 다시 부르는 예시.

    **반드시 문법이 맞는 파이썬이어야 한다.** 이 문자열의 유일한 용도가
    복사해서 다시 부르는 것이기 때문이다. 줄바꿈이 든 본문을 그대로 따옴표
    안에 넣으면 깨진 코드가 나가고, 그걸 받은 에이전트는 보강을 포기한다.
    그래서 값은 `json.dumps` 로 감싼다 — 그 결과는 파이썬 문자열 리터럴로도 유효하다.

    긴 값(`ECHO_MAX` 초과)은 `"..."` 로 줄인다. 자리표시자인 것이 한눈에 보여야
    에이전트가 원래 값을 다시 넣는다. 짧은 값은 그대로 실어 복사만으로 끝나게 한다.

    이미 채워진 선택 필드도 함께 실어 준다. 빼면 그 예시를 복사한 순간
    사용자가 이미 준 근거가 사라진다.
    """
    if not missing:
        return ""

    blank = set(missing)
    # record_id 가 맨 앞이다. 이게 빠지면 예시를 복사한 순간 새 id 가
    # 만들어져, 보강 대신 거의 같은 기록이 하나 더 생긴다.
    parts = [f'record_id="{record_id}"'] if record_id else []
    for name in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        if name in blank:
            parts.append(f'{name}="..."')
        elif not _is_blank(values.get(name)):
            parts.append(f"{name}={_literal(values.get(name))}")
    return "record_learning(" + ", ".join(parts) + ")"


def _is_blank(value) -> bool:
    """`None` 과 공백뿐인 문자열만 비어 있는 것으로 본다.

    `not value` 로 판정하면 나중에 숫자나 불리언 필드가 생겼을 때
    `0` 과 `False` 가 결손으로 보고되어, 이미 준 값을 다시 달라고 하게 된다.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _literal(value) -> str:
    """파이썬 문자열 리터럴. `json.dumps` 의 결과는 파이썬에서도 유효하다.

    직접 따옴표만 바꿔치기하면 역슬래시와 줄바꿈에서 깨진다.
    """
    if value is None:
        return "None"
    text = str(value)
    if len(text) > ECHO_MAX:
        return '"..."'
    return json.dumps(text, ensure_ascii=False)


# 슬러그를 **공고에 흔히 나오는 말**로 묶은 것. 화면에서만 쓴다.
# 첫 칸은 URL 에 쓰는 열쇠다 — 라벨은 사람이 읽는 말이라 언제든 다듬을 수
# 있어야 하는데, 그게 주소에 들어가면 링크가 같이 깨진다.
#
# `RECOMMENDED_SLUGS` 는 로드맵 주차 순서라 공부 순서를 말하고, 이쪽은
# "공고가 이 말을 쓰면 어느 슬러그를 보면 되는가" 를 말한다. 두 순서가 달라서
# 한 상수로 합칠 수 없다 — 대신 **같은 100개를 빠짐없이 겹치지 않게 덮는지**
# 를 테스트가 본다. 덮지 못하면 기술스택 화면에서 슬러그가 조용히 사라진다.
SLUG_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("java", "Java / JVM", ("jvm-gc", "java-concurrency")),
    ("spring", "Spring / Spring Boot", ("spring-di", "spring-mvc", "spring-transactional",
                              "tx-boundary", "filter-vs-interceptor")),
    ("api", "REST API / API 설계", ("api-error-handling", "dto-separation", "net-http")),
    ("jpa", "JPA / ORM", ("jpa-persistence-context", "jpa-lazy-loading", "jpa-n-plus-one",
                   "jpa-fetch-join", "jpa-batch-size", "entity-association", "querydsl")),
    ("db", "RDBMS / SQL / DB 설계", ("db-index", "db-transaction", "db-isolation", "db-lock",
                              "db-normalization", "db-join", "db-execution-plan",
                              "composite-index", "domain-erd")),
    ("concurrency", "동시성 / 데이터 정합성", ("optimistic-vs-pessimistic-lock", "race-condition",
                          "idempotency")),
    ("redis", "Redis / 캐싱", ("redis-data-types", "redis-ttl-eviction", "cache-target-selection",
                    "cache-aside", "cache-invalidation", "cache-ttl-policy",
                    "redis-cache-effect")),
    ("rabbitmq", "RabbitMQ / 메시지 큐", ("rabbitmq-basics", "rabbitmq-exchange-routing", "rabbitmq-ack",
                          "rabbitmq-retry", "rabbitmq-dlq", "poison-message",
                          "message-persistence", "consumer-failure", "consumer-restart")),
    ("kafka", "Kafka / 이벤트 스트림", ("kafka-basics", "kafka-partition-offset", "kafka-consumer-group",
                          "kafka-partition-throughput", "kafka-delivery-semantics",
                          "kafka-offset-commit", "kafka-rebalancing", "rabbitmq-vs-kafka",
                          "task-queue-vs-event-stream")),
    ("async", "비동기 / 실시간", ("sync-to-async", "sse-reconnect")),
    ("perf", "성능 / 부하 테스트", ("k6-load-test", "latency-p95")),
    ("docker", "Docker / 컨테이너", ("dockerfile-multistage", "docker-compose",
                       "docker-image-optimization")),
    ("k8s", "Kubernetes", ("k8s-pod-deployment", "k8s-service-ingress", "k8s-configmap-secret",
                    "k8s-probe", "k8s-hpa", "k8s-necessity")),
    ("cicd", "CI/CD", ("github-actions-pipeline",)),
    ("monitoring", "모니터링 / 옵저버빌리티", ("prometheus-grafana",)),
    ("aws", "AWS / 클라우드 인프라", ("aws-vpc", "public-private-subnet", "nat-gateway",
                        "security-group-nacl", "ec2-vs-ecs", "aws-rds",
                        "aws-elasticache", "aws-deploy")),
    ("terraform", "Terraform / IaC", ("terraform-state", "terraform-module")),
    ("nginx", "Nginx / 로드밸런싱", ("nginx-reverse-proxy", "nginx-tls-termination",
                       "load-balancing", "net-load-balancing")),
    ("network", "네트워크", ("net-tcp", "net-udp", "net-tls", "net-dns", "net-subnet-nat",
               "net-socket")),
    ("os", "Linux / OS", ("os-process-thread", "os-context-switch", "os-scheduling", "os-memory",
                    "os-virtual-memory", "os-io", "os-deadlock")),
    ("test", "테스트", ("test-strategy", "mockito-unit-test", "spring-integration-test")),
    ("architecture", "아키텍처 / 구조", ("package-structure",)),
)


# 슬러그의 한글 이름. **화면에서만 쓴다.**
#
# 기록·URL·집계는 전부 슬러그로 간다 — 여기를 고쳐도 그쪽은 안 흔들린다.
# 반대로 `ds-hash` 를 배지에 그대로 띄우면 훑을 때 읽히지 않는다.
# 이름이 없는 슬러그는 슬러그를 그대로 쓴다(도구를 만들며 남긴 것들).
SLUG_LABELS: dict[str, str] = {
    "net-tcp": "TCP",
    "net-udp": "UDP",
    "net-http": "HTTP",
    "net-tls": "TLS",
    "net-dns": "DNS",
    "net-subnet-nat": "서브넷 · NAT",
    "net-socket": "소켓",
    "net-load-balancing": "네트워크 로드밸런싱",
    "os-process-thread": "프로세스 · 스레드",
    "os-context-switch": "컨텍스트 스위칭",
    "os-scheduling": "CPU 스케줄링",
    "os-memory": "메모리 관리",
    "os-virtual-memory": "가상 메모리",
    "os-io": "입출력",
    "os-deadlock": "데드락",
    "db-index": "인덱스",
    "db-transaction": "트랜잭션",
    "db-isolation": "격리 수준",
    "db-lock": "락",
    "db-normalization": "정규화",
    "db-join": "조인",
    "db-execution-plan": "실행 계획",
    "spring-di": "의존성 주입",
    "spring-mvc": "Spring MVC",
    "filter-vs-interceptor": "필터 vs 인터셉터",
    "dto-separation": "DTO 분리",
    "api-error-handling": "API 예외 처리",
    "spring-transactional": "@Transactional",
    "tx-boundary": "트랜잭션 경계",
    "jvm-gc": "JVM GC",
    "java-concurrency": "자바 동시성",
    "test-strategy": "테스트 전략",
    "mockito-unit-test": "Mockito 단위 테스트",
    "spring-integration-test": "스프링 통합 테스트",
    "package-structure": "패키지 구조",
    "domain-erd": "도메인 ERD",
    "entity-association": "엔티티 연관관계",
    "jpa-persistence-context": "영속성 컨텍스트",
    "jpa-lazy-loading": "지연 로딩",
    "jpa-n-plus-one": "N+1 문제",
    "jpa-fetch-join": "페치 조인",
    "jpa-batch-size": "배치 사이즈",
    "querydsl": "QueryDSL",
    "composite-index": "복합 인덱스",
    "optimistic-vs-pessimistic-lock": "낙관적 vs 비관적 락",
    "race-condition": "경쟁 상태",
    "redis-data-types": "Redis 자료구조",
    "redis-ttl-eviction": "TTL · 축출 정책",
    "cache-target-selection": "캐시 대상 선정",
    "cache-aside": "Cache Aside",
    "cache-invalidation": "캐시 무효화",
    "cache-ttl-policy": "캐시 TTL 정책",
    "k6-load-test": "k6 부하 테스트",
    "latency-p95": "p95 지연",
    "redis-cache-effect": "Redis 캐시 효과",
    "sync-to-async": "동기 → 비동기 전환",
    "rabbitmq-basics": "RabbitMQ 기초",
    "rabbitmq-exchange-routing": "익스체인지 · 라우팅",
    "rabbitmq-ack": "ACK · NACK",
    "rabbitmq-retry": "재시도",
    "rabbitmq-dlq": "DLQ",
    "poison-message": "포이즌 메시지",
    "message-persistence": "메시지 영속성",
    "consumer-failure": "컨슈머 장애",
    "idempotency": "멱등성",
    "sse-reconnect": "SSE 재연결",
    "consumer-restart": "컨슈머 재기동",
    "kafka-basics": "Kafka 기초",
    "kafka-partition-offset": "파티션 · 오프셋",
    "kafka-consumer-group": "컨슈머 그룹",
    "kafka-partition-throughput": "파티션 처리량",
    "kafka-delivery-semantics": "전달 보장",
    "kafka-offset-commit": "오프셋 커밋",
    "kafka-rebalancing": "리밸런싱",
    "rabbitmq-vs-kafka": "RabbitMQ vs Kafka",
    "task-queue-vs-event-stream": "작업 큐 vs 이벤트 스트림",
    "dockerfile-multistage": "멀티스테이지 빌드",
    "docker-compose": "Docker Compose",
    "docker-image-optimization": "이미지 최적화",
    "nginx-reverse-proxy": "Nginx 리버스 프록시",
    "nginx-tls-termination": "TLS 종료",
    "load-balancing": "로드밸런싱",
    "aws-vpc": "VPC",
    "public-private-subnet": "퍼블릭 · 프라이빗 서브넷",
    "nat-gateway": "NAT 게이트웨이",
    "security-group-nacl": "보안 그룹 · NACL",
    "ec2-vs-ecs": "EC2 vs ECS",
    "aws-rds": "RDS",
    "aws-elasticache": "ElastiCache",
    "aws-deploy": "AWS 배포",
    "terraform-state": "Terraform 상태",
    "terraform-module": "Terraform 모듈",
    "github-actions-pipeline": "GitHub Actions 파이프라인",
    "k8s-pod-deployment": "파드 · 디플로이먼트",
    "k8s-service-ingress": "서비스 · 인그레스",
    "k8s-configmap-secret": "ConfigMap · Secret",
    "k8s-probe": "프로브",
    "k8s-hpa": "HPA 오토스케일링",
    "prometheus-grafana": "Prometheus · Grafana",
    "k8s-necessity": "쿠버네티스가 필요한가",
    "ds-array-linkedlist": "배열 · 연결 리스트",
    "ds-stack-queue": "스택 · 큐",
    "ds-hash": "해시",
    "ds-tree-bst": "트리 · 이진탐색트리",
    "ds-heap": "힙",
    "ds-graph": "그래프",
    "ds-btree": "B-Tree · B+Tree",
    "ds-trie": "트라이",
    "algo-complexity": "시간 · 공간 복잡도",
    "algo-sorting": "정렬",
    "algo-binary-search": "이분 탐색",
    "algo-dfs-bfs": "DFS · BFS",
    "algo-dp": "동적 계획법",
    "algo-greedy": "그리디",
    "algo-shortest-path": "최단 경로",
    "arch-cpu": "CPU 동작 원리",
    "arch-cache-memory": "캐시 메모리",
    "arch-memory-hierarchy": "메모리 계층",
    "arch-floating-point": "부동 소수점",
    "arch-von-neumann": "폰 노이만 구조",
    "lang-compile-process": "컴파일 과정",
    "lang-jvm-memory": "JVM 메모리 구조",
    "lang-call-by-value": "Call by Value",
    "lang-string-pool": "String 풀",
    "lang-collection": "컬렉션 프레임워크",
    "lang-exception": "예외 처리",
    "lang-serialization": "직렬화",
    "oop-solid": "SOLID",
    "oop-polymorphism": "다형성",
    "oop-inheritance-composition": "상속 vs 합성",
    "oop-immutable": "불변 객체",
    "pattern-singleton": "싱글톤",
    "pattern-factory": "팩토리 메서드",
    "pattern-strategy": "전략 패턴",
    "pattern-observer": "옵저버 패턴",
    "pattern-template-method": "템플릿 메서드",
    "pattern-proxy": "프록시 패턴",
    "web-cookie-session": "쿠키 · 세션",
    "web-http-method": "HTTP 메서드",
    "web-http-status": "HTTP 상태 코드",
    "web-rest": "REST API",
    "web-jwt": "JWT",
    "web-oauth": "OAuth",
    "web-csrf-xss": "CSRF · XSS",
    "web-was-vs-webserver": "웹 서버 vs WAS",
    "dist-cap": "CAP 정리",
    "dist-replication": "복제",
    "dist-sharding": "샤딩",
    "dist-consistent-hashing": "일관성 해싱",
    "llm-token-context": "토큰 · 컨텍스트 윈도",
    "llm-prompt-design": "프롬프트 설계",
    "llm-structured-output": "구조화 출력",
    "llm-sampling": "샘플링 파라미터",
    "llm-cost-latency": "비용 · 지연",
    "llm-streaming": "스트리밍 응답",
    "llm-prompt-cache": "프롬프트 캐싱",
    "llm-eval": "평가",
    "agent-loop": "에이전트 루프",
    "agent-tool-use": "툴 호출",
    "agent-context-window": "컨텍스트 관리",
    "agent-memory": "에이전트 메모리",
    "agent-planning": "계획 · 분해",
    "agent-guardrail": "가드레일 · 권한",
    "agent-failure-recovery": "실패 복구",
    "multi-agent-orchestration": "오케스트레이션",
    "multi-agent-handoff": "핸드오프",
    "multi-agent-shared-state": "공유 상태",
    "multi-agent-cost": "토큰 비용",
    "multi-agent-necessity": "멀티가 필요한가",
    "mcp-stdio-transport": "stdio 트랜스포트",
    "mcp-tool-schema": "툴 스키마",
    "mcp-client-handshake": "클라이언트 식별",
    "mcp-server-lifecycle": "서버 수명주기",
    "agent-hook": "훅",
    "agent-skill": "스킬",
    "agent-plugin": "플러그인 배포",
    "rag-chunking": "청킹",
    "rag-embedding": "임베딩",
    "rag-vector-search": "벡터 검색",
    "rag-reranking": "리랭킹",
}


def label_of(slug: str) -> str:
    return SLUG_LABELS.get(slug, slug)


def roadmap_index(slug: str) -> int:
    """31주 로드맵에서 몇 번째인가. 목록 밖이면 맨 뒤다.

    `RECOMMENDED_SLUGS` 의 순서가 곧 주차 순서다. **주차 번호는 세지 않는다**
    — 밀리면 "늦었다" 가 매일 보이고, 그건 로드맵 문서가 하지 않기로 한 일이다.
    순서만 안다.
    """
    try:
        return RECOMMENDED_SLUGS.index(slug)
    except ValueError:
        return len(RECOMMENDED_SLUGS)


def is_known(slug: str) -> bool:
    """이 슬러그가 **앞으로 기록이 쌓일 자리**인가.

    `is_recommended` 와 다르다. 그쪽은 "31주 로드맵 위인가" 이고, 이쪽은
    로드맵이든 CS 든 화면이 이름을 아는 주제인가를 묻는다. 기록이 아직
    없어도 화면을 보여줘야 하는 자리를 가르는 값이다.
    """
    return slug in SLUG_LABELS


def group_of(slug: str) -> tuple[str, str] | None:
    """이 슬러그가 속한 묶음. `(열쇠, 라벨)` 이다."""
    for key, label, slugs in SLUG_GROUPS + CS_GROUPS + AI_GROUPS:
        if slug in slugs:
            return key, label
    return None


def certs_of(slug: str) -> list[tuple[str, str]]:
    """이 슬러그가 나오는 자격증들. `(열쇠, 이름)` 이다."""
    return [
        (key, name) for key, name, slugs in CERTIFICATIONS if slug in slugs
    ]


# 로드맵 100개에 **없는** CS 기초. 출처는 아래 둘이다(2026-08-31 확인).
#
#   TeachYourselfCS-KR      https://github.com/minnsane/TeachYourselfCS-KR
#   tech-interview-for-developer
#                           https://github.com/gyoogle/tech-interview-for-developer
#
# 31주 로드맵은 **직접 만들어 보는 것**을 다룬다. 그래서 운영체제·네트워크·
# 데이터베이스는 이미 있는데, 면접에서 실제로 묻는 자료구조·알고리즘·
# 컴퓨터구조·디자인패턴·웹 기초가 통째로 비어 있었다.
#
# **`RECOMMENDED_SLUGS` 에 합치지 않는다.** 그쪽은 로드맵 부록 A 가 원본이고
# 문서가 곧 데이터다. 여기 것을 섞으면 "로드맵 위인가" 라는 질문에 답할 수
# 없게 된다 — 기록의 `recommended` 플래그가 뜻을 잃는다.
CS_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ds", "자료구조", (
        "ds-array-linkedlist", "ds-stack-queue", "ds-hash", "ds-tree-bst",
        "ds-heap", "ds-graph", "ds-btree", "ds-trie",
    )),
    ("algo", "알고리즘", (
        "algo-complexity", "algo-sorting", "algo-binary-search", "algo-dfs-bfs",
        "algo-dp", "algo-greedy", "algo-shortest-path",
    )),
    ("cpu", "컴퓨터구조", (
        "arch-cpu", "arch-cache-memory", "arch-memory-hierarchy",
        "arch-floating-point", "arch-von-neumann",
    )),
    ("lang", "자바 · 런타임", (
        "lang-compile-process", "lang-jvm-memory", "lang-call-by-value",
        "lang-string-pool", "lang-collection", "lang-exception",
        "lang-serialization",
    )),
    ("oop", "객체지향", (
        "oop-solid", "oop-polymorphism", "oop-inheritance-composition",
        "oop-immutable",
    )),
    ("pattern", "디자인패턴", (
        "pattern-singleton", "pattern-factory", "pattern-strategy",
        "pattern-observer", "pattern-template-method", "pattern-proxy",
    )),
    ("web", "웹 기초", (
        "web-cookie-session", "web-http-method", "web-http-status", "web-rest",
        "web-jwt", "web-oauth", "web-csrf-xss", "web-was-vs-webserver",
    )),
    ("dist", "분산시스템", (
        "dist-cap", "dist-replication", "dist-sharding",
        "dist-consistent-hashing",
    )),
)

CS_SLUGS: tuple[str, ...] = tuple(
    slug for _, _, slugs in CS_GROUPS for slug in slugs
)


# 세 번째 축이다. 로드맵도 CS 도 아니고, **지금 이 도구를 만들며 매일
# 부딪히는 것**이다(2026-09-04 추가). MCP 서버·훅·플러그인은 이미 만들어
# 놓고도 남길 자리가 없어서 `spool-durability` 처럼 목록 밖으로 샜다.
#
# 재료는 넷이다 — Codex 공식문서 · Claude Code 공식문서 ·
# 『AI 에이전트 엔지니어링』 · 『AI 앱 개발 올인원 가이드』.
#
# **`RECOMMENDED_SLUGS` 에 합치지 않는다.** CS 와 같은 이유다(위 주석 참조).
# 로드맵은 문서가 원본이고, 이쪽은 문서 밖에서 새로 연 자리다.
AI_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("llm", "LLM 다루기", (
        "llm-token-context", "llm-prompt-design", "llm-structured-output",
        "llm-sampling", "llm-cost-latency", "llm-streaming",
        "llm-prompt-cache", "llm-eval",
    )),
    ("agent", "에이전트", (
        "agent-loop", "agent-tool-use", "agent-context-window", "agent-memory",
        "agent-planning", "agent-guardrail", "agent-failure-recovery",
    )),
    ("multi-agent", "멀티 에이전트", (
        "multi-agent-orchestration", "multi-agent-handoff",
        "multi-agent-shared-state", "multi-agent-cost", "multi-agent-necessity",
    )),
    ("mcp", "MCP · 에이전트 확장", (
        "mcp-stdio-transport", "mcp-tool-schema", "mcp-client-handshake",
        "mcp-server-lifecycle", "agent-hook", "agent-skill", "agent-plugin",
    )),
    ("rag", "RAG", (
        "rag-chunking", "rag-embedding", "rag-vector-search", "rag-reranking",
    )),
)

AI_SLUGS: tuple[str, ...] = tuple(
    slug for _, _, slugs in AI_GROUPS for slug in slugs
)


# 갖고 있는 책이 덮는 주제. **장(章) 단위가 아니라 책 단위다.**
#
# 목차를 확인하지 않고 장 번호를 적으면 그 순간 이 화면을 못 믿게 된다.
# 여기 적힌 것은 "이 책을 읽으면 이 주제들에 답할 수 있게 된다" 는 판단이고,
# 판단한 것은 사람이 아니라 에이전트다 — 틀리면 고쳐라(2026-09-02).
#
# 자격증처럼 **겹쳐도 된다.** `db-index` 는 Real MySQL 이자 면접 CS 노트다.
BOOK_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("net-topdown", "컴퓨터 네트워킹 하향식 접근", (
        "net-tcp", "net-udp", "net-http", "net-tls", "net-dns", "net-socket",
        "net-subnet-nat", "net-load-balancing", "web-http-method",
        "web-http-status", "load-balancing",
    )),
    ("dinosaur", "운영체제 (공룡책)", (
        "os-process-thread", "os-context-switch", "os-scheduling", "os-memory",
        "os-virtual-memory", "os-io", "os-deadlock", "race-condition",
        "java-concurrency",
    )),
    ("honja-cs", "혼자 공부하는 컴퓨터구조 + 운영체제", (
        "arch-cpu", "arch-cache-memory", "arch-memory-hierarchy",
        "arch-floating-point", "arch-von-neumann",
        "os-process-thread", "os-context-switch", "os-scheduling", "os-memory",
        "os-virtual-memory", "os-io", "os-deadlock",
    )),
    ("design-pattern-java", "Java 언어로 배우는 디자인패턴 입문", (
        "pattern-singleton", "pattern-factory", "pattern-strategy",
        "pattern-observer", "pattern-template-method", "pattern-proxy",
        "oop-polymorphism", "oop-inheritance-composition",
    )),
    ("ddd-start", "도메인 주도 개발 시작하기", (
        "domain-erd", "entity-association", "package-structure",
        "tx-boundary", "dto-separation", "oop-inheritance-composition",
        "optimistic-vs-pessimistic-lock",
    )),
    ("jpa-kim", "자바 ORM 표준 JPA 프로그래밍", (
        "jpa-persistence-context", "jpa-lazy-loading", "jpa-n-plus-one",
        "jpa-fetch-join", "jpa-batch-size", "entity-association", "querydsl",
        "optimistic-vs-pessimistic-lock", "spring-transactional",
    )),
    ("toby-spring", "토비의 스프링 vol.1", (
        "spring-di", "spring-mvc", "spring-transactional", "tx-boundary",
        "oop-solid", "pattern-template-method", "pattern-strategy",
        "pattern-proxy", "test-strategy", "mockito-unit-test",
    )),
    ("real-mysql", "Real MySQL 1 · 2", (
        "db-index", "db-transaction", "db-isolation", "db-lock",
        "db-execution-plan", "db-join", "composite-index",
        "optimistic-vs-pessimistic-lock", "ds-btree",
    )),
    ("system-design", "가상 면접 사례로 배우는 대규모 시스템 설계 기초", (
        "dist-cap", "dist-replication", "dist-sharding",
        "dist-consistent-hashing", "cache-aside", "cache-invalidation",
        "cache-target-selection", "load-balancing", "latency-p95",
        "sync-to-async", "task-queue-vs-event-stream", "idempotency",
    )),
    ("it-infra", "그림으로 배우는 IT 인프라 구조", (
        "os-io", "arch-memory-hierarchy", "net-socket", "net-load-balancing",
        "nginx-reverse-proxy", "load-balancing", "db-index", "cache-aside",
    )),
    ("this-is-java", "이것이 자바다", (
        "lang-collection", "lang-exception", "lang-call-by-value",
        "lang-string-pool", "java-concurrency", "oop-polymorphism",
    )),
    ("effective-java", "이펙티브 자바", (
        "oop-immutable", "oop-inheritance-composition", "oop-polymorphism",
        "lang-serialization", "lang-string-pool", "lang-exception",
        "lang-collection", "java-concurrency",
    )),
    ("modern-java", "모던 자바 인 액션", (
        "lang-collection", "java-concurrency", "sync-to-async",
    )),
    ("clean-code", "클린 코드", (
        "package-structure", "test-strategy", "mockito-unit-test",
        "lang-exception",
    )),
    ("clean-arch", "클린 아키텍처", (
        "package-structure", "oop-solid", "oop-inheritance-composition",
        "dto-separation", "domain-erd",
    )),
    ("cs-note", "면접을 위한 CS 전공 노트", (
        "ds-array-linkedlist", "ds-stack-queue", "ds-hash", "ds-tree-bst",
        "ds-heap", "ds-graph", "algo-complexity", "algo-sorting",
        "algo-binary-search", "algo-dfs-bfs", "algo-dp",
        "net-tcp", "net-udp", "net-http", "net-dns",
        "os-process-thread", "os-scheduling", "os-deadlock",
        "db-index", "db-transaction", "db-normalization", "db-join",
        "pattern-singleton", "pattern-factory", "oop-solid",
        "web-cookie-session", "web-rest", "web-jwt", "web-csrf-xss",
        "web-was-vs-webserver",
    )),
    ("object-oriented", "객체지향의 사실과 오해", (
        "oop-polymorphism", "oop-inheritance-composition", "oop-solid",
        "domain-erd",
    )),

    # 2026-09-04 에 빌린 3권. 반납일은 코드에 없다 —
    # `~/.warruru/career/books/{열쇠}.md` 의 `due` 가 원본이다.
    ("docker-k8s-start", "시작하세요! 도커/쿠버네티스", (
        "dockerfile-multistage", "docker-compose", "docker-image-optimization",
        "k8s-pod-deployment", "k8s-service-ingress", "k8s-configmap-secret",
        "k8s-probe", "k8s-hpa", "k8s-necessity", "prometheus-grafana",
    )),
    ("aws-network", "따라 하며 배우는 AWS 네트워크 입문", (
        "aws-vpc", "public-private-subnet", "nat-gateway",
        "security-group-nacl", "net-subnet-nat", "net-dns",
        "net-load-balancing", "load-balancing",
    )),
    ("kafka-practice", "실전 카프카 개발부터 운영까지", (
        "kafka-basics", "kafka-partition-offset", "kafka-consumer-group",
        "kafka-partition-throughput", "kafka-delivery-semantics",
        "kafka-offset-commit", "kafka-rebalancing", "message-persistence",
        "consumer-failure", "consumer-restart", "idempotency",
    )),

    ("redis-practice", "실전 레디스", (
        "redis-data-types", "redis-ttl-eviction", "cache-target-selection",
        "cache-aside", "cache-invalidation", "cache-ttl-policy",
        "redis-cache-effect", "dist-replication", "dist-sharding",
    )),
    ("http-guide", "HTTP 완벽 가이드", (
        "net-http", "net-tcp", "net-tls", "net-dns", "web-http-method",
        "web-http-status", "web-cookie-session", "web-was-vs-webserver",
        "nginx-reverse-proxy",
    )),
    # 문화·프로세스 책이라 슬러그가 적게 붙는다. **적은 것이 맞다** —
    # 억지로 늘리면 이 화면의 숫자가 뜻을 잃는다.
    ("google-swe", "구글 엔지니어는 이렇게 일한다", (
        "test-strategy", "mockito-unit-test", "spring-integration-test",
        "github-actions-pipeline",
    )),

    # AI 축의 재료. **공식문서도 여기 둔다** — 종이인지 아닌지가 아니라
    # "읽으면 어느 주제가 채워지는가" 가 이 목록의 기준이다.
    ("ai-agent-eng", "AI 에이전트 엔지니어링", (
        "agent-loop", "agent-tool-use", "agent-context-window", "agent-memory",
        "agent-planning", "agent-guardrail", "agent-failure-recovery",
        "multi-agent-orchestration", "multi-agent-handoff",
        "multi-agent-shared-state", "multi-agent-cost", "multi-agent-necessity",
        "llm-structured-output", "llm-eval",
    )),
    ("ai-app-guide", "AI 앱 개발 올인원 가이드", (
        "llm-token-context", "llm-prompt-design", "llm-sampling",
        "llm-structured-output", "llm-streaming", "llm-cost-latency",
        "llm-prompt-cache", "rag-chunking", "rag-embedding",
        "rag-vector-search", "rag-reranking",
    )),
    ("claude-code-docs", "Claude Code 공식문서", (
        "agent-hook", "agent-skill", "agent-plugin", "agent-tool-use",
        "agent-guardrail", "agent-context-window", "multi-agent-orchestration",
        "mcp-tool-schema", "mcp-stdio-transport", "mcp-server-lifecycle",
    )),
    ("codex-docs", "Codex 공식문서", (
        "agent-hook", "agent-plugin", "agent-guardrail",
        "mcp-stdio-transport", "mcp-tool-schema", "mcp-client-handshake",
        "mcp-server-lifecycle",
    )),
)


# 자격증마다 **로드맵 주제와 겹치는 부분**. 시험 범위 자체가 아니다.
#
# 이 목록은 "이 자격증을 딸 때 공부하는 것 중, 이 프로젝트에 기록으로 남길
# 만한 것" 이다. 시험에는 나오지만 로드맵에 없는 것(정보처리기사의 소프트웨어
# 생명주기, 리눅스마스터의 명령어 암기 같은 것)은 여기 없다.
# **그러니 이 화면의 준비도가 100% 여도 합격을 뜻하지 않는다.**
#
# 겹쳐도 된다. `SLUG_GROUPS` 는 100개를 한 번씩 나누지만 이쪽은 자격증마다
# 같은 슬러그를 다시 본다 — `db-index` 는 정보처리기사이자 SQLD 다.
CERTIFICATIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("jeongcheogi", "정보처리기사", (
        "db-normalization", "db-index", "db-transaction", "db-join",
        "db-execution-plan", "domain-erd", "entity-association",
        "net-tcp", "net-udp", "net-http", "net-tls", "net-dns",
        "net-subnet-nat", "net-socket",
        "os-process-thread", "os-context-switch", "os-scheduling", "os-memory",
        "os-virtual-memory", "os-io", "os-deadlock",
        "package-structure", "test-strategy",
    )),
    ("sqld", "SQLD", (
        "db-normalization", "db-join", "db-index", "db-transaction",
        "db-isolation", "db-lock", "db-execution-plan", "composite-index",
        "domain-erd", "entity-association",
    )),
    ("network-2", "네트워크관리사 2급", (
        "net-tcp", "net-udp", "net-http", "net-tls", "net-dns",
        "net-subnet-nat", "net-socket", "net-load-balancing", "load-balancing",
    )),
    ("linux-2", "리눅스마스터 2급", (
        "os-process-thread", "os-context-switch", "os-scheduling", "os-memory",
        "os-virtual-memory", "os-io", "os-deadlock",
    )),
    # TOPCIT 은 합격/불합격이 아니라 **점수(0~1000) 와 수준(1~5)** 이다.
    # 그래서 이 목록의 뜻이 다른 자격증과 미묘하게 다르다 — "따려면 공부할 것"
    # 이 아니라 "이미 아는 만큼 점수가 나오는 것" 이라, 준비도 막대가 곧
    # 예상 수준에 가깝다. 다만 비즈니스 영역 175점은 로드맵에 없어서
    # **여기 안 들어온다.** 그 몫은 이 화면이 답하지 못한다.
    ("topcit", "TOPCIT", (
        "db-normalization", "db-index", "db-transaction", "db-join",
        "db-isolation", "db-execution-plan", "domain-erd", "entity-association",
        "package-structure", "test-strategy", "mockito-unit-test",
        "os-process-thread", "os-scheduling", "os-memory",
        "net-tcp", "net-udp", "net-http", "net-dns", "net-tls",
        "net-subnet-nat", "load-balancing",
    )),
    ("aws-saa", "AWS SAA", (
        "aws-vpc", "public-private-subnet", "nat-gateway", "security-group-nacl",
        "ec2-vs-ecs", "aws-rds", "aws-elasticache", "aws-deploy", "load-balancing",
    )),
)


# 원본은 `docs/guides/backend-infra-roadmap-31w.md` 부록 A 다. **문서가 곧 데이터다.**
# 자동 반영은 없으므로 문서를 고치면 여기도 함께 고친다.
# 이미 기록이 쌓인 슬러그의 이름은 바꾸지 않는다 — 바꾸면 그 주제가 둘로 갈라진다.
RECOMMENDED_SLUGS: tuple[str, ...] = (
    "net-tcp", "net-udp", "net-http", "net-tls", "net-dns", "net-subnet-nat", "net-socket",
    "net-load-balancing", "os-process-thread", "os-context-switch", "os-scheduling",
    "os-memory", "os-virtual-memory", "os-io", "os-deadlock", "db-index", "db-transaction",
    "db-isolation", "db-lock", "db-normalization", "db-join", "db-execution-plan", "spring-di",
    "spring-mvc", "filter-vs-interceptor", "dto-separation", "api-error-handling",
    "spring-transactional", "tx-boundary", "jvm-gc", "java-concurrency", "test-strategy",
    "mockito-unit-test", "spring-integration-test", "package-structure", "domain-erd",
    "entity-association", "jpa-persistence-context", "jpa-lazy-loading", "jpa-n-plus-one",
    "jpa-fetch-join", "jpa-batch-size", "querydsl", "composite-index",
    "optimistic-vs-pessimistic-lock", "race-condition", "redis-data-types",
    "redis-ttl-eviction", "cache-target-selection", "cache-aside", "cache-invalidation",
    "cache-ttl-policy", "k6-load-test", "latency-p95", "redis-cache-effect", "sync-to-async",
    "rabbitmq-basics", "rabbitmq-exchange-routing", "rabbitmq-ack", "rabbitmq-retry",
    "rabbitmq-dlq", "poison-message", "message-persistence", "consumer-failure", "idempotency",
    "sse-reconnect", "consumer-restart", "kafka-basics", "kafka-partition-offset",
    "kafka-consumer-group", "kafka-partition-throughput", "kafka-delivery-semantics",
    "kafka-offset-commit", "kafka-rebalancing", "rabbitmq-vs-kafka",
    "task-queue-vs-event-stream", "dockerfile-multistage", "docker-compose",
    "docker-image-optimization", "nginx-reverse-proxy", "nginx-tls-termination",
    "load-balancing", "aws-vpc", "public-private-subnet", "nat-gateway", "security-group-nacl",
    "ec2-vs-ecs", "aws-rds", "aws-elasticache", "aws-deploy", "terraform-state",
    "terraform-module", "github-actions-pipeline", "k8s-pod-deployment", "k8s-service-ingress",
    "k8s-configmap-secret", "k8s-probe", "k8s-hpa", "prometheus-grafana", "k8s-necessity"
)


# 판정 전용 집합. RECOMMENDED_SLUGS 는 순서가 의미를 가지므로 튜플로 두고,
# 멤버십만 여기서 상수 시간으로 본다.
_RECOMMENDED_SET = frozenset(RECOMMENDED_SLUGS)
