# WarruruLab 내일 작업 계획

작성일: 2026-05-02

## 현재 방향

WarruruLab의 방향은 기존의 “개발 중간 과정 기록”에서 “학습 대화와 지식 자산화”로 바뀌었다.

핵심 목표는 다음과 같다.

- CS, 프레임워크, 인프라 지식을 DevTalk에서 대화로 학습한다.
- Local LLM을 사용해 외부 API 비용과 의존성을 줄인다.
- 작은 모델의 부족한 답변 품질은 RAG로 보완한다.
- MCP가 대화를 knowledge block으로 구조화한다.
- DevLog가 knowledge block과 RAG context를 바탕으로 블로그 초안을 만든다.
- 최종 글은 사람이 검토해 blog 디렉터리에 학습 자산으로 남긴다.

## 전체 시스템 아키텍처 정리

내일 먼저 WarruruLab 전체 시스템 아키텍처 문서를 잡는다.

정리해야 할 흐름은 다음과 같다.

```text
사용자
-> DevTalk
   -> Local LLM 빠른 답변
   -> RAG 검색 결과 반영
   -> 세션/메시지 저장
-> MCP
   -> 메시지를 knowledge block으로 구조화
   -> block metadata 생성
   -> RAG upsert 대상 생성
-> RAG
   -> CS 지식 베이스 검색
   -> 개인 학습 기록 검색
   -> 블로그 아카이브 검색
-> DevLog
   -> block 선택
   -> RAG context 검색
   -> 고품질 Local LLM으로 초안 생성
-> Blog
   -> 사람이 검토한 최종 Markdown 저장
```

아키텍처 문서에서 반드시 구분해야 하는 축은 다음과 같다.

- 브라우저에서 접근하는 public endpoint
- Docker network 내부에서 접근하는 service endpoint
- Local LLM을 공유하는 AI container
- RAG API와 Vector DB
- 긴 작업을 큐로 넘길지 여부

## 각 서비스 README 재작성 기준

README는 단순 실행 방법보다 “이 서비스가 WarruruLab에서 왜 존재하는지”가 먼저 보여야 한다.

### DevTalk

DevTalk README는 다음 메시지를 중심으로 정리한다.

- DevTalk은 학습 대화 입력 계층이다.
- 빠른 응답이 중요하므로 가벼운 Local LLM을 사용한다.
- RAG로 CS/프레임워크 지식을 검색해 답변 품질을 보완한다.
- 세션별 대화는 개인 학습 기록으로 남고, 이후 MCP와 DevLog가 사용한다.

추가로 정리할 내용:

- 세션별 context 유지 방식
- RAG 검색 우선순위
- DevTalk에서 사용하는 LLM env
- DevTalk이 직접 글을 쓰지 않는 이유

### MCP

MCP README는 다음 메시지를 중심으로 정리한다.

- MCP는 대화 원문을 knowledge block으로 바꾸는 서비스다.
- 요약기가 아니라 검색과 글 작성을 위한 구조화 계층이다.
- block type은 개발 이슈가 아니라 학습 자산화 기준으로 바꾼다.

검토할 block type:

- `concept`
- `comparison`
- `example`
- `misunderstanding`
- `summary`
- `blog_candidate`
- `reference`

추가로 정리할 내용:

- RAG에 저장할 metadata
- block 생성/append 기준
- 누락 메시지 복구 방식
- DevLog가 block을 선택하는 기준

### DevLog

DevLog README는 다음 메시지를 중심으로 정리한다.

- DevLog는 학습 기록을 블로그 초안으로 바꾸는 서비스다.
- 개인이 혼자 사용하는 서비스이므로 속도보다 품질을 우선한다.
- 서버에서 가능한 가장 좋은 Local LLM 모델을 DevLog에 배정한다.
- RAG context를 함께 넣어 글의 근거와 밀도를 높인다.

추가로 정리할 내용:

- block 선택 기반 초안 생성 흐름
- topic 단위 글감 묶기
- DevLog 모델 env 권장값
- 최종 Markdown 저장 흐름

### Blog

Blog README는 다음 메시지를 중심으로 정리한다.

- Blog는 AI 초안 저장소가 아니라 사람이 검토한 최종 학습 자산 저장소다.
- 최종 글은 다시 RAG의 `blog_archive`에 넣을 수 있는 품질을 목표로 한다.
- DevTalk, MCP, DevLog 개발 과정도 별도 카테고리로 남긴다.

## RAG 레포 생성 검토

RAG는 별도 레포로 분리하는 방향을 고민한다.

분리 장점:

- DevTalk, MCP, DevLog가 모두 사용하는 공통 검색 계층으로 관리하기 쉽다.
- Vector DB, embedding, reindex 작업을 독립적으로 운영할 수 있다.
- 이후 서비스가 추가되어도 같은 RAG API를 재사용할 수 있다.

분리 단점:

- 레포와 배포 단위가 하나 늘어난다.
- 초기에는 API, Docker, env, 테스트까지 새로 관리해야 한다.
- 아직 검색 스키마가 확정되지 않았기 때문에 과하게 빨리 분리하면 수정 비용이 생길 수 있다.

현재 추천:

1. RAG 설계를 문서로 먼저 확정한다.
2. 최소 API 스펙을 정한다.
3. 별도 `rag` 레포를 만든다.
4. DevTalk에 먼저 검색 연동한다.
5. MCP에서 knowledge block upsert를 연동한다.
6. DevLog에서 draft 생성 시 RAG context를 사용한다.

## RAG 초기 설계안

초기 기술 선택 후보:

- API 서버: FastAPI
- Vector DB: Qdrant
- Embedding model: `nomic-embed-text`
- LLM runtime: Ollama

초기 collection:

```text
cs_knowledge
personal_learning
blog_archive
project_docs
```

초기 API:

```text
POST /v1/documents
POST /v1/search
POST /v1/reindex
GET  /v1/health
```

검색 요청 예시:

```json
{
  "query": "Redis Streams를 메시지 큐로 사용할 때 장단점",
  "collections": ["cs_knowledge", "personal_learning"],
  "filter": {
    "userId": "pswaa",
    "sessionId": "optional-session-id",
    "topic": "redis"
  },
  "topK": 5
}
```

문서 metadata 최소값:

```json
{
  "userId": "pswaa",
  "sessionId": "session-id",
  "blockId": "block-id",
  "service": "mcp",
  "sourceType": "knowledge_block",
  "topic": "redis",
  "tags": ["redis", "stream", "message-queue"],
  "createdAt": "2026-05-02T10:30:00"
}
```

## Message Queue 도입 검토

하나의 Ollama 컨테이너에 DevTalk, MCP, DevLog, RAG embedding 작업이 몰릴 수 있다.

다만 DevTalk의 짧은 대화 응답까지 큐로 넘기면 사용자 경험이 나빠질 수 있다. 따라서 초기에는 아래처럼 나눈다.

동기 처리:

- DevTalk의 짧은 대화 응답
- RAG 검색
- 단건 block 조회

비동기 처리 후보:

- DevLog 긴 글 초안 생성
- RAG 대량 indexing
- embedding batch 작업
- MCP reconciliation
- blog archive reindex

초기 후보는 Redis Streams가 적당하다.

RabbitMQ는 메시지 브로커 역할이 더 명확하지만, 현재 프로젝트 규모에서는 Redis를 cache, queue, stream 용도로 함께 학습하고 활용하는 편이 낫다.

## 내일 우선순위

1. WarruruLab 전체 시스템 아키텍처 문서 작성
2. 각 서비스 README를 최종 방향으로 다시 다듬기
3. RAG 레포 분리 여부 결정
4. RAG 최소 API 스펙 작성
5. Docker Compose에 RAG, Qdrant, Ollama 연결 방향 정리
6. DevTalk의 RAG 검색 연동 지점 파악
7. MCP의 knowledge block upsert 지점 파악
8. DevLog의 RAG context draft prompt 반영 지점 파악

## 내일 바로 확인할 질문

- RAG를 별도 레포로 만들 것인가, 임시로 루트 하위 디렉터리에서 시작할 것인가?
- Vector DB는 Qdrant로 확정할 것인가?
- embedding 모델은 `nomic-embed-text`로 시작할 것인가?
- 개인 학습 기록과 공통 CS 지식 베이스를 같은 RAG 서버에서 collection만 분리할 것인가?
- DevLog 긴 글 생성은 바로 큐를 도입할 것인가, 동기 호출로 먼저 완성할 것인가?

## 임시 결론

RAG는 WarruruLab에서 Local LLM의 품질을 끌어올리는 핵심 계층이다.

처음부터 완벽한 AI Agent를 만들기보다, DevTalk에서 질문하고, RAG가 근거를 보강하고, MCP가 지식 블록을 만들고, DevLog가 블로그 초안으로 전환하는 흐름을 먼저 완성한다.

그 다음 개인 학습 기록, 블로그 아카이브, 프로젝트 문서를 RAG에 계속 넣으면서 나에게 맞는 개인 학습 AI Agent 시스템으로 확장한다.
