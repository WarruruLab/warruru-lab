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


def missing_fields(values: dict) -> list[str]:
    """비어 있는 선택 필드 이름. 순서는 `OPTIONAL_FIELDS` 정의 순서다.

    거절하지 않고 이 목록을 응답에 실어 보낸다. 기록 여부가 100% 에이전트
    재량인 구조에서 거절은 '기록 안 하기'를 가장 안전한 선택으로 만든다.
    """
    return [name for name in OPTIONAL_FIELDS if _is_blank(values.get(name))]


# 예시에 원래 값을 그대로 실을지, 자리표시자로 줄일지 가르는 길이.
# 본문은 6단 마크다운이라 길다. 통째로 실으면 응답이 기록 하나만큼 부풀고,
# 에이전트가 매 호출마다 그 비용을 낸다.
ECHO_MAX = 80


def example_call(values: dict, missing: list[str]) -> str:
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

    parts = [f"{name}={_literal(values.get(name))}" for name in REQUIRED_FIELDS]
    parts += [
        f"{name}={_literal(values.get(name))}"
        for name in OPTIONAL_FIELDS
        if name not in missing and not _is_blank(values.get(name))
    ]
    parts += [f'{name}="..."' for name in missing]
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
