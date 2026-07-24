# 기능 명세서 - 통합 AI 에이전트

**작성일:** 2026-07-24
**최종 업데이트:** 2026-07-24
**버전:** 1.0.0

---

## 1. 기능 개요

통합 AI 에이전트는 4개 모듈로 구성됩니다:
- 💬 Chat Module: 학습 대화
- 🧠 Structure Module: 지식 구조화
- 📝 Draft Module: 블로그 초안
- 📊 Record Module: 개발 기록

---

## 2. Chat Module (학습 대화)

### 2.1 실시간 학습 대화

**목적:** 사용자의 학습 질문에 즉시 답변

**입력:**
```json
{
  "sessionId": "session-123",
  "message": "Spring Boot에서 JPA N+1 문제 해결 방법은?",
  "userId": "pswaa"
}
```

**출력:**
```json
{
  "messageId": "msg-456",
  "content": "N+1 문제는 ...",
  "ragResults": [...],
  "timestamp": "2026-07-24T10:30:00Z"
}
```

**처리 흐름:**
1. 사용자 질문 수신
2. RAG 검색 (Qdrant) - 과거 학습 기록
3. Context 구성 (RAG + 최근 대화)
4. Ollama LLM 호출 (qwen2.5:3b)
5. 응답 생성 및 DB 저장
6. Structure Module 자동 트리거

**예외 상황:**
- RAG 검색 실패 → LLM만 사용
- LLM 타임아웃 → "처리 중 오류 발생" 메시지
- DB 저장 실패 → 로그 기록, 사용자에게 알림

**우선순위:** P0 (최고)

---

### 2.2 세션 관리

**목적:** 대화를 주제별로 그룹핑

**기능:**
- 세션 생성
- 세션 목록 조회
- 세션별 메시지 조회
- 세션 삭제

**우선순위:** P0

---

### 2.3 RAG 검색

**목적:** 과거 학습 기록에서 관련 정보 검색

**입력:** 사용자 질문 (텍스트)

**출력:** Top-K 관련 문서 (기본 5개)

**검색 대상:**
- Knowledge Block (과거 학습)
- CS 지식 베이스
- 개인 블로그 아카이브

**우선순위:** P0

---

## 3. Structure Module (지식 구조화)

### 3.1 자동 Knowledge Block 생성

**목적:** 대화를 재사용 가능한 knowledge block으로 전환

**입력:** Chat Module 메시지

**출력:**
```json
{
  "blockId": "block-789",
  "blockType": "concept",
  "topic": "JPA",
  "summary": "N+1 문제 해결 - fetch join",
  "tags": ["JPA", "N+1", "fetch-join"],
  "status": "success",
  "messages": ["msg-456", "msg-457"]
}
```

**처리 흐름:**
1. Chat 메시지 수신
2. **1단계: Route 판단** (Ollama qwen2.5:3b)
   - APPEND: 기존 block에 추가
   - NEW_BLOCK: 새 block 생성
3. **2단계: Metadata 생성** (Ollama gpt-oss-20b)
   - blockType, status, topic, summary, tags
4. DB 저장
5. RAG 인덱싱 트리거

**Block Types:**
- `concept`: 개념 설명
- `comparison`: 비교 분석
- `example`: 구체적 예시
- `misunderstanding`: 오해했던 내용
- `summary`: 정리/요약
- `blog_candidate`: 블로그 글감

**우선순위:** P0

---

### 3.2 Block 조회 및 관리

**기능:**
- Topic별 block 조회
- Block 상세 조회
- Block 수정
- Block 병합
- Block 삭제

**우선순위:** P1

---

## 4. Draft Module (블로그 초안)

### 4.1 블로그 초안 생성

**목적:** Knowledge block을 블로그 글로 전환

**입력:**
```json
{
  "topic": "JPA N+1 문제 해결",
  "blockIds": ["block-789", "block-790"],
  "style": "technical",  // technical, casual, tutorial
  "ragContext": true
}
```

**출력:** Markdown 블로그 초안

**처리 흐름:**
1. Block 조회 (DB)
2. RAG 검색 (관련 학습 기록)
3. Context 구성 (Block + RAG)
4. Prompt 생성
5. Ollama LLM 호출 (gpt-oss-20b - 고품질)
6. Markdown 생성
7. DB 저장

**초안 구조:**
```markdown
# [제목]

## 배경
[문제 상황]

## 원인
[근본 원인]

## 해결 방법
[구체적 해결 방법]

## 예시
[코드 예시]

## 교훈
[배운 점]

## 참고 자료
[링크]
```

**우선순위:** P0

---

### 4.2 초안 관리

**기능:**
- 초안 목록 조회
- 초안 수정
- 초안 삭제
- 초안 상태 관리 (작성 중, 검토 중, 완료)

**우선순위:** P1

---

### 4.3 Tistory 발행 (연동)

**목적:** 완성된 초안을 Tistory에 자동 발행

**기능:**
- OAuth 인증
- 카테고리 설정
- 태그 설정
- 공개 범위 설정
- 발행 후 local blog/ 저장

**우선순위:** P2

---

## 5. Record Module (개발 기록)

### 5.1 MCP 프로토콜 지원

**목적:** AI Agent (Codex/Claude Code) 작업 기록

**프로토콜:** MCP (stdio)

**지원 메시지:**
- `start_work`: 작업 시작
- `record_checkpoint`: 중요 시점 기록
- `finish_work`: 작업 완료

**우선순위:** P0

---

### 5.2 작업 기록 저장

**저장 데이터:**
```json
{
  "sessionId": "work-session-123",
  "tool": "claude-code",
  "machineId": "mac-m1",
  "gitBranch": "feature/new-api",
  "gitCommit": "abc123",
  "startedAt": "2026-07-24T09:00:00Z",
  "finishedAt": "2026-07-24T12:00:00Z",
  "checkpoints": [
    {
      "timestamp": "2026-07-24T10:00:00Z",
      "description": "API 설계 완료",
      "context": "..."
    }
  ]
}
```

**우선순위:** P0

---

### 5.3 타임라인 조회

**기능:**
- 날짜별 작업 기록 조회
- Tool별 필터링
- 검색 (키워드, Git context)

**우선순위:** P1

---

## 6. 공통 기능

### 6.1 WebSocket 실시간 스트리밍

**목적:** LLM 응답을 실시간으로 사용자에게 전달

**프로토콜:** Socket.IO

**이벤트:**
- `chat:stream`: Chat 응답 스트리밍
- `draft:stream`: Draft 생성 스트리밍

**우선순위:** P0

---

### 6.2 에러 처리

**전략:**
- LLM 타임아웃: 30초
- DB 재시도: 3회
- 로그 기록: ERROR 레벨
- 사용자 알림: 명확한 에러 메시지

**우선순위:** P0

---

### 6.3 로깅 및 모니터링

**로그 레벨:**
- DEBUG: 개발 시
- INFO: 주요 작업 (Chat, Structure, Draft)
- ERROR: 예외 상황

**모니터링:**
- LLM 응답 시간
- RAG 검색 시간
- DB 쿼리 시간

**우선순위:** P1

---

## 7. 우선순위 정리

| 우선순위 | 기능 |
|---------|------|
| **P0 (MVP)** | Chat 대화, RAG 검색, Structure 생성, Draft 생성, Record MCP, WebSocket |
| **P1 (필수)** | 세션 관리, Block 관리, 초안 관리, 타임라인, 로깅 |
| **P2 (향후)** | Tistory 발행, Analytics, Learning Path |

---

## 8. 제한사항

- **동시 사용자:** 1명 (본인만)
- **LLM 동시 호출:** 1개 (순차 처리)
- **WebSocket 연결:** 브라우저당 1개
- **파일 업로드:** 지원 안 함 (텍스트만)
- **이미지 생성:** 지원 안 함

---

## 9. 성능 목표

| 기능 | 목표 시간 |
|------|----------|
| Chat 응답 | 2-5초 |
| RAG 검색 | 500ms |
| Structure 생성 | 1-3초 |
| Draft 생성 | 10-30초 |
| DB 조회 | 100ms |

---

## 10. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-07-24 | 1.0.0 | 초안 작성 |

---

**상태:** ✅ 확정
**다음 단계:** 인터페이스 명세서 작성
