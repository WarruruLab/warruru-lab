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

import re
import unicodedata

# 슬러그로 만들 수 없는 주제가 모이는 자리. 비어 있는 집계 키를 만들 수는 없다.
# 화면의 '미분류' 구획에서 눈에 띄므로 조용히 묻히지는 않는다.
FALLBACK_SLUG = "misc"

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
    """
    text = unicodedata.normalize("NFKC", topic or "").strip().lower()
    text = _SEPARATORS.sub("-", text)
    text = _DROP.sub("", text)
    text = _DASHES.sub("-", text).strip("-")
    return text or FALLBACK_SLUG


def missing_fields(values: dict) -> list[str]:
    """비어 있는 선택 필드 이름. 순서는 `OPTIONAL_FIELDS` 정의 순서다.

    거절하지 않고 이 목록을 응답에 실어 보낸다. 기록 여부가 100% 에이전트
    재량인 구조에서 거절은 '기록 안 하기'를 가장 안전한 선택으로 만든다.
    """
    return [name for name in OPTIONAL_FIELDS if _is_blank(values.get(name))]


def example_call(values: dict, missing: list[str]) -> str:
    """결손 필드를 채워 같은 툴을 다시 부르는 예시.

    복사해서 바로 실행할 수 있어야 한다. 다시 타이핑하게 만들면 안 채운다.
    그래서 필수 필드는 원래 값을 그대로 되돌려 준다.
    """
    if not missing:
        return ""

    parts = [f"{name}={_literal(values.get(name))}" for name in REQUIRED_FIELDS]
    parts += [f'{name}="..."' for name in missing]
    return "record_learning(" + ", ".join(parts) + ")"


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return not value


def _literal(value) -> str:
    if value is None:
        return "None"
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


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
