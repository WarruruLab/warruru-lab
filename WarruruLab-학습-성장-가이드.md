# WarruruLab 학습 성장 가이드

작성일: 2026-05-03

## 목표

이 프로젝트의 목표는 WarruruLab을 완성하는 것만이 아니다.

프로젝트를 끝냈을 때 아래 기술을 “써봤다”가 아니라, 왜 그렇게 설계했고 어떤 문제가 생겼으며 어떻게 해결했는지 설명할 수 있는 개발자가 되는 것이 목표다.

- Spring Boot
- Java
- 객체지향 설계와 디자인 패턴
- MySQL, SQL, DB 문제 해결
- JPA
- Local LLM
- RAG
- 서비스 간 통신
- 테스트와 운영 장애 대응

따라서 앞으로 Codex와 Claude Code는 기능을 대신 구현하는 도구가 아니라, 설계 리뷰어, 코드 리뷰어, 튜터, 테스트 코치로 사용한다.

## 핵심 원칙

```text
AI는 내가 작성한 것을 리뷰한다.
AI는 내가 이해한 것을 검증한다.
AI는 내가 놓친 것을 질문한다.
AI는 내가 만든 테스트를 보강한다.
AI는 전체 구현을 대신하지 않는다.
```

기능 하나를 만들 때 기본 흐름은 다음과 같다.

```text
내가 요구사항을 쓴다
-> 내가 설계 초안을 쓴다
-> AI가 설계를 리뷰한다
-> 내가 1차 구현한다
-> AI가 코드를 리뷰한다
-> 내가 테스트한다
-> AI가 테스트 누락을 찾는다
-> 내가 학습 로그를 쓴다
-> AI가 이해도를 점검한다
```

## AI에게 맡기면 안 되는 일

- 기능 전체 구현을 한 번에 맡기기
- Entity, Repository, Service, Controller를 통째로 생성하게 하기
- 이해하지 못한 코드를 그대로 반영하기
- 테스트 없이 “돌아갈 것 같은 코드”를 받기
- 설계 없이 바로 코드 생성하기
- 에러 로그를 읽지 않고 해결만 요청하기

이 방식은 프로젝트 속도는 빠르게 만들 수 있지만, 내 실력은 남지 않는다.

## AI에게 맡기면 좋은 일

- 설계에서 빠진 질문 찾기
- JPA 연관관계 위험 요소 리뷰
- 트랜잭션 경계 검토
- DB 인덱스와 쿼리 문제점 지적
- 코드 책임 분리 리뷰
- 디자인 패턴이 필요한지 판단
- 테스트 케이스 누락 찾기
- 에러 로그 원인 후보 정리
- RAG chunk, metadata, 검색 전략 리뷰
- 학습한 내용을 질문으로 검증

## WarruruLab 기능을 학습 단위로 바꾸기

앞으로 기능을 바로 구현하지 않고, 각 기능을 학습 주제로 연결한다.

| 기능 | 학습 주제 |
| --- | --- |
| DevTalk 세션/메시지 API | Spring Boot 계층 구조, DTO, 예외 처리 |
| DevTalk Local LLM 연동 | Java 인터페이스, 전략 패턴, timeout, fallback |
| DevTalk context 유지 | SQL 조회 최적화, 세션 설계, 프롬프트 구성 |
| MCP knowledge block 생성 | 서비스 분리, FastAPI, API 계약 |
| DevLog 초안 생성 | 프롬프트 설계, 긴 작업 처리, LLM 품질 관리 |
| RAG 서버 생성 | FastAPI, Qdrant, embedding, metadata filter |
| DevTalk RAG 검색 연동 | Spring RestClient, 외부 API 장애 처리 |
| MCP block RAG upsert | 이벤트 흐름, idempotency, 데이터 정합성 |
| DevLog RAG context 반영 | 검색 결과 평가, 글 생성 품질 개선 |
| Redis Streams 도입 | Message Queue, 비동기 처리, retry |
| JPA 전환 | Entity 설계, 연관관계, N+1, fetch join |
| 운영 안정화 | 로그, health check, Docker network, env 관리 |

## 1단계: Spring Boot 기반 구조

### 목표

DevTalk과 DevLog의 백엔드 기능을 직접 설계하고 구현할 수 있는 수준을 만든다.

### 학습할 것

- Controller, Service, Repository 계층 분리
- DTO와 도메인 객체 분리
- 요청/응답 흐름
- Validation
- 전역 예외 처리
- 환경변수와 `application.yml`
- 외부 API client 구성

### 프로젝트 적용

- DevTalk 메시지 생성/조회 API 직접 구현
- DevLog draft 조회/저장 API 직접 구현
- RAG client를 Spring Boot에서 호출
- LLM client 실패 시 fallback 처리

### AI 사용법

좋은 요청:

```text
내가 작성한 Controller/Service 구조를 리뷰해줘.
코드는 작성하지 말고 계층 책임이 섞인 부분만 지적해줘.
```

나쁜 요청:

```text
DevTalk API 만들어줘.
```

### 완료 기준

- Controller에 비즈니스 로직을 넣지 않는 이유를 설명할 수 있다.
- Service의 트랜잭션 경계를 어디에 둘지 판단할 수 있다.
- 외부 API 실패가 전체 서비스 실패로 번지지 않게 처리할 수 있다.

## 2단계: Java와 디자인 패턴

### 목표

기능이 커져도 유지보수 가능한 Java 코드를 작성한다.

### 학습할 것

- 캡슐화
- 책임 분리
- SOLID
- 인터페이스 기반 설계
- Strategy Pattern
- Factory Pattern
- Template Method Pattern
- record, enum, sealed class 활용

### 프로젝트 적용

- `LlmClient` 인터페이스로 Ollama, mock, Gemini 구현체 분리
- DevTalk 답변 생성과 DevLog 초안 생성 전략 분리
- 프롬프트 생성기를 별도 객체로 분리
- RAG 검색 전략을 collection별로 분리

### AI 사용법

```text
이 코드에 Strategy 패턴을 적용할 이유가 있는지 검토해줘.
패턴을 억지로 쓰는 상황이면 그렇게 말해줘.
```

### 완료 기준

- “왜 인터페이스로 분리했는가?”에 답할 수 있다.
- 새 LLM 제공자를 추가할 때 기존 코드 수정 범위를 설명할 수 있다.
- 패턴을 적용한 이유와 적용하지 않은 이유를 모두 설명할 수 있다.

## 3단계: MySQL, SQL, DB 문제 해결

### 목표

테이블만 만드는 수준이 아니라, 데이터 모델링과 성능 문제를 해결할 수 있게 된다.

### 학습할 것

- ERD 설계
- 정규화와 반정규화
- PK/FK 설계
- 인덱스
- 실행 계획
- cursor pagination
- 트랜잭션
- 동시성 문제
- 락과 데드락 기초

### 프로젝트 적용

- DevTalk session/message 조회 최적화
- DevLog block/draft 조회 최적화
- MCP block 중복 생성 방지
- RAG document metadata 검색 조건 설계
- `sessionId`, `topic`, `createdAt` 기준 인덱스 설계

### AI 사용법

```text
이 테이블 구조에서 인덱스 후보를 리뷰해줘.
정답을 바로 주지 말고, 어떤 쿼리를 기준으로 판단해야 하는지 먼저 질문해줘.
```

```text
이 실행 계획을 해석해줘.
바로 해결책을 주지 말고 병목 후보를 가능성 순서로 정리해줘.
```

### 완료 기준

- 인덱스를 왜 그 컬럼에 걸었는지 설명할 수 있다.
- 느린 쿼리를 실행 계획으로 확인할 수 있다.
- 트랜잭션 경계와 데이터 정합성 문제를 설명할 수 있다.

## 4단계: JPA 실전 전환

### 목표

JPA를 단순 CRUD 도구가 아니라, 동작 원리와 성능 이슈까지 이해하고 사용한다.

### 학습할 것

- Entity 매핑
- 연관관계 주인
- 지연 로딩과 즉시 로딩
- 영속성 컨텍스트
- 변경 감지
- JPQL
- fetch join
- DTO projection
- N+1 문제
- pagination 주의점
- QueryDSL

### 프로젝트 적용

- DevTalk Session-Message 관계 매핑
- DevLog Draft-Block 관계 매핑
- MCP knowledge block과 source message 관계 매핑
- 목록 조회에서 pagination 적용
- 상세 조회에서 필요한 연관 데이터만 fetch join

### AI 사용법

```text
이 엔티티 관계에서 N+1이 발생할 수 있는 조회를 찾아줘.
해결 코드는 주지 말고 어떤 API에서 문제가 생길지 설명해줘.
```

```text
이 연관관계에서 cascade와 orphanRemoval을 써도 되는지 리뷰해줘.
위험한 경우를 먼저 말해줘.
```

### 완료 기준

- JPA가 언제 SQL을 날리는지 설명할 수 있다.
- 지연 로딩을 기본으로 두는 이유를 설명할 수 있다.
- fetch join이 필요한 경우와 위험한 경우를 구분할 수 있다.

## 5단계: Local LLM 연동

### 목표

Ollama 기반 Local LLM을 안정적으로 서비스에 연결한다.

### 학습할 것

- Ollama API 구조
- prompt 설계
- system/user prompt 분리
- temperature, max tokens, context length
- timeout
- fallback
- 실패 응답 저장
- 프롬프트 버전 관리

### 프로젝트 적용

- DevTalk 빠른 응답 모델 설정
- DevLog 고품질 글 생성 모델 설정
- MCP block routing 모델 설정
- LLM 실패 시 사용자에게 보여줄 응답 설계

### AI 사용법

```text
이 프롬프트가 너무 많은 책임을 갖고 있는지 리뷰해줘.
검색 context, 사용자 질문, 출력 형식이 잘 분리되어 있는지 봐줘.
```

### 완료 기준

- 모델별 역할을 설명할 수 있다.
- LLM timeout과 실패를 서비스 관점에서 처리할 수 있다.
- 프롬프트를 코드와 분리해야 하는 이유를 설명할 수 있다.

## 6단계: MCP와 서비스 분리

### 목표

Spring Boot 서비스와 FastAPI 기반 지식 구조화 서비스를 분리해 운영하는 이유를 이해한다.

### 학습할 것

- FastAPI 기본 구조
- Pydantic schema
- REST API 계약
- 서비스 간 통신
- 장애 격리
- API versioning

### 프로젝트 적용

- DevTalk 메시지를 MCP로 전달
- MCP가 `concept`, `comparison`, `example`, `summary`, `blog_candidate` block 생성
- DevLog가 MCP block을 조회해 글감 선택
- MCP 장애 시 DevTalk/DevLog의 fallback 정책 설계

### AI 사용법

```text
MCP를 Spring Boot 내부 기능으로 두지 않고 별도 서비스로 분리한 이유를 검토해줘.
장점보다 단점과 운영 부담을 먼저 지적해줘.
```

### 완료 기준

- 서비스 분리 기준을 설명할 수 있다.
- API 계약이 깨졌을 때 어떤 문제가 생기는지 설명할 수 있다.
- MCP 장애가 전체 시스템에 미치는 영향을 줄일 수 있다.

## 7단계: RAG

### 목표

작은 Local LLM의 답변 품질을 검색 기반으로 보완하는 구조를 직접 구현한다.

### 학습할 것

- RAG 기본 개념
- chunking
- embedding
- vector database
- Qdrant
- similarity search
- metadata filter
- top-k 검색
- prompt context 구성
- hallucination 완화
- 출처 제공

### 프로젝트 적용

- CS 지식 베이스 구축
- MCP knowledge block embedding 저장
- DevTalk 질문 시 RAG 검색
- DevLog 초안 생성 시 RAG context 추가
- 개인 학습 기록을 `userId`, `sessionId`, `topic`으로 필터링

### AI 사용법

```text
이 RAG metadata 설계를 리뷰해줘.
세션별 검색, 주제별 검색, 개인 학습 기록 검색에 부족한 필드가 있는지 봐줘.
```

```text
chunk 단위를 주제별로 할지 문단별로 할지 고민 중이야.
검색 품질 관점에서 장단점을 비교해줘.
```

### 완료 기준

- RAG가 일반 LLM 호출과 다른 점을 설명할 수 있다.
- chunk 크기와 metadata 설계 이유를 설명할 수 있다.
- 검색 결과가 부정확할 때 개선 방향을 제시할 수 있다.

## 8단계: 테스트와 품질 관리

### 목표

기능 구현 후 스스로 검증 가능한 개발자가 된다.

### 학습할 것

- 단위 테스트
- 통합 테스트
- Repository 테스트
- Service 테스트
- Mocking
- Testcontainers
- API 테스트
- LLM 기능 테스트 전략

### 프로젝트 적용

- DevTalk SessionService 테스트
- DevLog DraftService 테스트
- LLM client mock 테스트
- RAG client 실패 테스트
- JPA Repository 테스트
- MySQL Testcontainers 적용

### AI 사용법

```text
이 테스트 케이스 목록을 리뷰해줘.
테스트 코드는 작성하지 말고 빠진 시나리오만 알려줘.
```

### 완료 기준

- 단위 테스트와 통합 테스트를 구분할 수 있다.
- LLM처럼 결과가 매번 달라지는 기능을 어떻게 테스트할지 설명할 수 있다.
- 테스트가 무엇을 보장하는지 말할 수 있다.

## 9단계: 운영과 장애 대응

### 목표

실제 서버에서 문제가 생겼을 때 로그와 설정을 보고 원인을 추적할 수 있게 된다.

### 학습할 것

- Docker network
- env 관리
- health check
- 로그 설계
- timeout
- retry
- DB connection 문제
- CORS
- reverse proxy
- queue와 비동기 처리

### 프로젝트 적용

- DevTalk DB 접근 실패 원인 분석
- CORS 403 원인 분석
- Ollama GPU 미연결 문제 해결
- DevLog 긴 초안 생성 timeout 조정
- Redis Streams로 긴 작업 비동기화 검토

### AI 사용법

```text
아래 에러 로그를 분석해줘.
바로 해결 명령어를 주지 말고 원인 후보와 내가 먼저 확인할 체크리스트를 줘.
```

### 완료 기준

- 로그만 보고 DB 문제와 LLM 문제를 구분할 수 있다.
- Docker 내부 주소와 public domain을 구분할 수 있다.
- env 변경이 컨테이너에 어떻게 반영되는지 설명할 수 있다.

## 기능별 권장 학습 순서

1. DevTalk의 현재 Spring Boot 구조를 직접 설명한다.
2. DevTalk Local LLM 호출 흐름을 코드로 따라간다.
3. DevTalk context 유지 로직을 직접 정리한다.
4. DevLog 초안 생성 흐름을 설명한다.
5. MCP block 생성 흐름을 설명한다.
6. RAG metadata schema를 직접 설계한다.
7. RAG API 스펙을 직접 작성한다.
8. DevTalk에서 RAG를 호출하는 client를 직접 구현한다.
9. MCP block을 RAG에 upsert하는 흐름을 직접 구현한다.
10. DevLog draft prompt에 RAG context를 직접 반영한다.
11. JPA 전환 대상을 하나 골라 직접 전환한다.
12. 느린 조회 하나를 골라 인덱스와 실행 계획을 확인한다.
13. 테스트를 작성하고 AI에게 누락 케이스를 리뷰받는다.
14. 학습한 내용을 DevLog로 정리한다.

## 이미 개발된 내용을 내 것으로 만드는 방법

현재까지 개발된 내용은 그냥 “이미 구현된 코드”로 두면 내 실력이 되지 않는다.

이미 만들어진 기능도 다시 학습 대상으로 바꿔야 한다. 기준은 단순하다.

```text
내가 설명할 수 없는 코드는 내 코드가 아니다.
내가 고칠 수 없는 구조는 내 실력이 아니다.
내가 장애를 재현할 수 없는 문제 해결은 내 경험이 아니다.
```

따라서 기존 구현은 다음 순서로 다시 흡수한다.

### 1. 기능 흐름을 말로 복원하기

먼저 코드를 보지 않고 기능 흐름을 직접 써본다.

예시:

```text
DevTalk Local LLM 응답 흐름

1. 사용자가 세션에서 메시지를 입력한다.
2. backend가 최근 메시지와 summary를 가져온다.
3. prompt composer가 LLM 입력을 만든다.
4. Ollama client가 local llm에 요청한다.
5. 응답을 message로 저장한다.
6. frontend가 응답을 화면에 보여준다.
```

그 다음 실제 코드를 보면서 틀린 부분을 표시한다.

이 과정에서 중요한 것은 “코드를 읽는 것”이 아니라 “내가 예상한 흐름과 실제 흐름의 차이를 찾는 것”이다.

### 2. 파일별 책임을 직접 정리하기

이미 구현된 파일을 하나씩 보면서 아래 형식으로 정리한다.

```text
파일명:
이 파일의 책임:
이 파일이 의존하는 것:
이 파일을 호출하는 곳:
변경되면 영향을 받는 기능:
내가 이해하지 못한 부분:
```

예를 들어 LLM 관련 파일이면 이렇게 정리한다.

```text
파일명: OllamaHttpClient
책임: Ollama API에 HTTP 요청을 보내고 응답을 LlmResult로 변환한다.
의존: RestClient, LlmProperties
호출: AiMessageService 또는 DraftService
변경 영향: DevTalk 답변 생성, DevLog 초안 생성
모르는 부분: timeout이 어디에서 설정되는지 다시 확인 필요
```

이 정리를 DevLog에 남기면 나중에 RAG 개인 학습 기록으로도 재사용할 수 있다.

### 3. 내가 직접 다시 그려보기

이미 개발된 구조를 다이어그램으로 다시 그린다.

처음에는 정확하지 않아도 된다.

```text
Controller
-> Service
-> Repository
-> MySQL

Service
-> PromptComposer
-> LlmClient
-> Ollama
```

다이어그램을 그린 뒤 AI에게 이렇게 요청한다.

```text
내가 현재 DevTalk LLM 호출 흐름을 이렇게 이해했어.
코드를 기준으로 틀린 흐름이나 빠진 구성요소만 지적해줘.
수정된 다이어그램을 바로 주지 말고, 내가 고칠 수 있게 질문으로 알려줘.
```

### 4. 테스트를 직접 추가해보기

이미 구현된 기능을 내 것으로 만드는 가장 좋은 방법은 테스트를 직접 추가하는 것이다.

처음부터 큰 통합 테스트를 만들 필요는 없다.

우선 아래처럼 작은 단위로 시작한다.

```text
Ollama 응답이 정상일 때 Success로 변환되는가?
Ollama 응답이 비어 있으면 Failure로 처리되는가?
RAG 검색 실패 시 LLM 답변 생성은 계속되는가?
context max chars를 넘으면 오래된 메시지가 잘리는가?
```

테스트를 작성하면 자연스럽게 다음을 이해하게 된다.

- 객체 생성 방식
- 의존성 주입 구조
- 실패 처리 방식
- 경계값
- 기존 코드의 숨은 가정

테스트 작성 후 AI에게는 이렇게 요청한다.

```text
내가 이 기능을 이해하기 위해 테스트를 작성했어.
테스트 코드 자체보다, 내가 놓친 동작 가정이 있는지 리뷰해줘.
```

### 5. 작은 리팩토링을 직접 해보기

이미 구현된 코드를 읽기만 하면 실력이 잘 늘지 않는다.

이해한 뒤에는 작은 리팩토링을 직접 해본다.

추천 리팩토링:

- 하드코딩된 값 env로 빼기
- 긴 메서드에서 prompt 생성 부분 분리
- 중복 DTO 변환 로직 분리
- 실패 응답 생성 로직 메서드화
- 테스트하기 어려운 static/helper 구조 개선
- 네이밍 개선

단, 리팩토링 전에 반드시 아래를 적는다.

```text
바꾸려는 이유:
현재 코드의 문제:
변경 후 기대 효과:
깨질 수 있는 기능:
검증할 테스트:
```

AI에게는 이렇게 요청한다.

```text
내가 이 리팩토링을 하려고 해.
과한 리팩토링인지, 실제 유지보수에 도움이 되는 변경인지 먼저 판단해줘.
```

### 6. 장애를 다시 재현해보기

이미 겪었던 문제는 다시 재현해야 내 경험이 된다.

현재까지 나온 대표 문제:

- CORS 설정 문제로 403 발생
- DB 계정/비밀번호 불일치로 500 발생
- Docker network 내부 주소와 public domain 혼동
- Ollama 컨테이너에 GPU가 붙지 않아 응답이 느림
- LLM context 길이와 max token 설정 문제

각 문제마다 아래 형식으로 복기한다.

```text
문제:
증상:
로그:
처음 세운 가설:
틀린 가설:
최종 원인:
해결 방법:
다음에 먼저 확인할 체크리스트:
```

이 작업은 DB, Docker, 운영 문제 해결 능력을 키우는 데 가장 효과적이다.

### 7. 커밋을 다시 읽고 설명하기

이미 만들어진 기능은 커밋 단위로 다시 읽는다.

각 커밋마다 아래 질문에 답한다.

```text
이 커밋은 어떤 문제를 해결했는가?
왜 이 파일들이 바뀌었는가?
대안은 무엇이었는가?
이 변경으로 생길 수 있는 부작용은 무엇인가?
테스트는 무엇을 보장하는가?
```

커밋 메시지를 보는 것이 아니라, 변경 이유를 설명할 수 있어야 한다.

AI에게는 이렇게 요청한다.

```text
이 커밋을 내가 이렇게 이해했어.
틀린 이해나 빠진 위험 요소를 리뷰해줘.
```

### 8. 블로그 글로 재작성하기

마지막으로 이미 구현된 기능을 블로그 글로 바꾼다.

단순 구현 설명이 아니라, 학습 글이어야 한다.

추천 글 구조:

```text
1. 왜 이 기능이 필요했는가
2. 처음에는 어떻게 생각했는가
3. 구현하면서 어떤 문제가 생겼는가
4. 최종 구조는 어떻게 되었는가
5. 이 과정에서 배운 Spring/DB/JPA/RAG 개념은 무엇인가
6. 다음에 개선할 점은 무엇인가
```

예시 글감:

- Gemini에서 Local LLM으로 바꾸면서 배운 외부 API 추상화
- Docker network와 domain을 혼동해서 생긴 DevTalk 장애
- DevLog에서 LLM 설정을 env로 분리한 이유
- 작은 Local LLM의 한계를 RAG로 보완하려는 이유
- MCP block 구조가 단순 요약이 아니라 knowledge block이어야 하는 이유

## 현재까지 개발된 기능별 복습 과제

### DevTalk

복습할 것:

- 세션과 메시지 저장 구조
- Local LLM 호출 흐름
- context 유지 방식
- env로 분리된 LLM 설정
- CORS와 DB 연결 문제

직접 해야 할 과제:

```text
DevTalk에서 사용자가 메시지를 보내면 어떤 클래스들을 거쳐 Ollama 응답이 저장되는지
파일명과 메서드명 기준으로 설명한다.
```

AI에게 요청:

```text
내가 정리한 DevTalk 메시지 처리 흐름을 리뷰해줘.
코드는 수정하지 말고 빠진 클래스나 잘못 이해한 책임만 지적해줘.
```

### DevLog

복습할 것:

- DevTalk 메시지 동기화 흐름
- MCP block 조회/저장 흐름
- draft 생성 흐름
- Ollama 전환 구조
- DevLog가 더 큰 모델을 써야 하는 이유

직접 해야 할 과제:

```text
DevLog가 블로그 초안을 만들 때 필요한 입력 데이터를
DevTalk, MCP, RAG, 사용자 선택값으로 나누어 정리한다.
```

AI에게 요청:

```text
이 DevLog 초안 생성 입력 설계를 리뷰해줘.
글 품질을 높이기 위해 빠진 context가 있는지 봐줘.
```

### MCP

복습할 것:

- message를 block으로 구조화하는 이유
- 기존 narrative block과 향후 knowledge block 차이
- block type 설계
- DevLog와의 연결 방식
- RAG upsert 대상으로서의 metadata

직접 해야 할 과제:

```text
MCP block type을 concept, comparison, example, misunderstanding, summary,
blog_candidate, reference로 나눴을 때 각 타입의 예시를 직접 작성한다.
```

AI에게 요청:

```text
내가 만든 MCP block type 예시를 리뷰해줘.
검색과 블로그 작성에 재사용하기 어려운 타입이 있는지 봐줘.
```

### RAG

복습할 것:

- 왜 RAG가 필요한가
- CS 지식 베이스와 개인 학습 기록의 차이
- collection 분리
- metadata filter
- sessionId 기반 검색
- topic 기반 검색

직접 해야 할 과제:

```text
RAG에 저장할 metadata schema를 직접 작성하고,
각 필드가 어떤 검색 문제를 해결하는지 설명한다.
```

AI에게 요청:

```text
이 RAG metadata 설계를 리뷰해줘.
세션별 검색, 주제별 검색, 블로그 글감 검색에 부족한 필드가 있는지 봐줘.
```

## 이미 개발된 코드 흡수 루틴

매일 개발 시작 전 30분:

```text
1. 어제 바뀐 파일 3개를 고른다.
2. 각 파일의 책임을 한 문장으로 쓴다.
3. 호출 흐름을 손으로 그린다.
4. 이해 안 되는 메서드 하나를 고른다.
5. AI에게 설명 검증을 요청한다.
```

매일 개발 종료 전 30분:

```text
1. 오늘 내가 이해한 개념 3개를 쓴다.
2. 오늘 틀린 가설 1개를 쓴다.
3. 오늘 본 에러나 로그 1개를 복기한다.
4. 내일 확인할 질문 1개를 남긴다.
5. DevLog 글감 후보를 하나 만든다.
```

주말 복습:

```text
1. 이번 주 커밋을 기능 단위로 묶는다.
2. 각 기능의 설계 이유를 다시 쓴다.
3. 테스트가 부족한 기능을 찾는다.
4. 블로그 글 하나로 정리한다.
5. 다음 주 학습 주제를 하나 정한다.
```

## Codex와 Claude Code 역할 분담

### Codex

Codex는 코드베이스 안에서 구조를 파악하고, 변경 범위를 좁히고, 코드 리뷰와 테스트 보조에 사용한다.

추천 사용:

- 현재 코드 흐름 파악
- 내가 작성한 코드 리뷰
- 테스트 실패 원인 분석
- 작은 범위의 리팩토링 제안
- 파일별 변경 영향도 확인

주의:

- 처음부터 전체 기능 구현을 맡기지 않는다.
- 내가 설계한 범위 안에서만 수정하게 한다.
- 코드 생성보다 리뷰와 검증에 더 자주 사용한다.

### Claude Code

Claude Code는 긴 설계 문서 검토, 개념 설명, 대안 비교, 학습 질문 생성에 사용한다.

추천 사용:

- 내가 작성한 설계 문서 리뷰
- JPA/RAG/DB 설계 대안 비교
- 학습 내용 검증 질문 생성
- 블로그 초안 구조 리뷰
- 내가 이해한 개념의 빈틈 찾기

주의:

- 장문의 설명을 그대로 복사하지 않는다.
- 최종 판단과 구현은 내가 한다.
- 학습 로그는 반드시 내 말로 다시 쓴다.

## 기능 하나를 구현할 때 사용할 템플릿

### 1. 요구사항 작성

```text
기능명:
왜 필요한가:
사용자 흐름:
성공 조건:
실패 조건:
```

### 2. 설계 초안 작성

```text
도메인 객체:
테이블:
API:
Service 책임:
Repository 책임:
트랜잭션 경계:
예상되는 예외:
```

### 3. AI 설계 리뷰 요청

```text
아래 설계를 리뷰해줘.
코드는 작성하지 말고 문제점과 질문만 제시해줘.

리뷰 기준:
- Spring Boot 계층 구조
- Java 객체 책임
- JPA 연관관계
- DB 정규화와 인덱스
- 트랜잭션
- 테스트 가능성
- 확장성
```

### 4. 직접 구현

```text
1차 구현은 내가 한다.
막히면 에러 로그와 내가 세운 가설을 먼저 적는다.
```

### 5. AI 코드 리뷰 요청

```text
아래 코드를 코드 리뷰해줘.
수정 코드는 바로 주지 말고 문제를 우선순위로 나눠줘.

중점:
- 버그 가능성
- 책임 분리
- JPA 성능
- 트랜잭션
- 테스트 부족
- 네이밍
```

### 6. 테스트 설계

```text
정상 케이스:
예외 케이스:
경계값:
외부 서비스 실패:
DB 실패:
동시 요청:
```

### 7. 학습 로그

```text
오늘 구현한 기능:
처음 이해한 방식:
구현하면서 틀렸던 생각:
새로 배운 개념:
아직 모르는 것:
다음에 확인할 것:
블로그 글감으로 남길 내용:
```

## 최종 실력 체크리스트

프로젝트를 마쳤을 때 아래 질문에 답할 수 있어야 한다.

### Spring Boot

- Controller, Service, Repository를 왜 나누는가?
- `@Transactional`은 어디에 두는가?
- 외부 API client 실패는 어떻게 처리하는가?
- env와 profile은 어떻게 관리하는가?

### Java와 디자인 패턴

- 이 프로젝트에서 인터페이스를 어디에 썼고 왜 썼는가?
- Strategy Pattern을 적용한 지점은 어디인가?
- 패턴을 적용하지 않은 이유를 설명할 수 있는가?
- 객체 책임이 잘못 분리된 코드를 찾아낼 수 있는가?

### DB와 SQL

- 주요 테이블의 인덱스 설계 이유는 무엇인가?
- 느린 쿼리를 어떻게 찾고 개선했는가?
- 트랜잭션 경계는 어디인가?
- 중복 저장과 데이터 정합성 문제를 어떻게 막았는가?

### JPA

- 영속성 컨텍스트가 무엇인가?
- 지연 로딩과 즉시 로딩의 차이는 무엇인가?
- N+1 문제를 어떻게 재현하고 해결했는가?
- fetch join과 DTO projection을 언제 쓰는가?

### RAG

- chunking 기준은 무엇인가?
- embedding 모델은 왜 선택했는가?
- Qdrant collection은 어떻게 나눴는가?
- metadata filter는 어떤 문제를 해결하는가?
- 검색 결과가 틀렸을 때 어떻게 개선하는가?

### 운영

- Docker network 내부 주소와 public domain을 구분할 수 있는가?
- CORS 403과 서버 500을 어떻게 구분하는가?
- DB connection error를 로그로 추적할 수 있는가?
- LLM timeout과 모델 성능 문제를 어떻게 조정하는가?

## 결론

WarruruLab은 단순 포트폴리오 프로젝트가 아니라, 학습 과정을 시스템으로 만드는 프로젝트다.

AI를 쓰지 않는 것이 목표가 아니다. AI를 쓰되, 구현 경험과 판단 능력이 나에게 남도록 써야 한다.

앞으로의 기준은 명확하다.

```text
AI가 구현한 프로젝트가 아니라,
AI를 리뷰어와 튜터로 사용해 내가 설계하고 구현한 프로젝트로 만든다.
```
