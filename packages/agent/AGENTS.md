# packages/agent - 통합 AI 에이전트

## 서비스 개요

**통합 AI 에이전트**는 WarruruLab의 핵심 서비스입니다. 학습 대화, 지식 구조화, 블로그 초안 생성, 개발 기록 관리를 하나의 통합 시스템으로 제공합니다.

### 핵심 가치

- **All-In-One**: 4개 모듈을 단일 프로세스로 실행
- **Fast**: localhost 통신으로 네트워크 지연 0ms
- **Intelligent**: RAG + Local LLM으로 학습 품질 향상
- **Privacy**: 모든 데이터는 로컬 저장

---

## 4개 모듈

### 💬 Chat Module (학습 대화)

**역할:** 사용자의 학습 질문에 답변

**기능:**
- 실시간 대화 (WebSocket)
- RAG 검색으로 과거 학습 기록 활용
- Ollama LLM으로 답변 생성
- 세션별 context 유지

**입력:** 사용자 질문 (텍스트)
**출력:** AI 답변 + RAG 검색 결과

---

### 🧠 Structure Module (지식 구조화)

**역할:** 대화를 knowledge block으로 자동 구조화

**기능:**
- 2단계 LLM 파이프라인 (route + metadata)
- Block type 자동 분류
- Topic & Tags 생성
- RAG 인덱싱 준비

**입력:** Chat Module 메시지
**출력:** Knowledge Block (구조화된 학습 기록)

---

### 📝 Draft Module (블로그 초안)

**역할:** Knowledge block을 블로그 초안으로 전환

**기능:**
- Topic 기반 block 그룹핑
- RAG context로 근거 강화
- 고품질 LLM으로 초안 생성
- Markdown 형식 출력

**입력:** Topic 선택 + Block IDs
**출력:** 블로그 초안 (Markdown)

---

### 📊 Record Module (개발 기록)

**역할:** AI Agent 작업 기록 수집 및 조회

**기능:**
- MCP 프로토콜 (stdio)
- Work Session & Checkpoint 저장
- 날짜별 타임라인 조회
- Git context 자동 수집

**입력:** MCP 메시지 (start_work, record_checkpoint, finish_work)
**출력:** 작업 기록 저장 + 웹 UI 조회

---

## 📚 문서 목차

이 서비스의 상세 명세는 `docs/` 디렉토리에 있습니다:

### 1. [요구사항 명세서](./docs/requirements.md)
- 왜 통합 에이전트가 필요한가?
- 사용자는 누구인가?
- 핵심 목표
- 비기능 요구사항

### 2. [기능 명세서](./docs/features.md)
- 4개 모듈 상세 기능
- 각 기능의 입력/출력
- 우선순위
- 제약사항

### 3. [인터페이스 명세서](./docs/interface.md)
- REST API 엔드포인트
- WebSocket 프로토콜
- MCP 프로토콜
- 데이터 스키마
- 에러 처리

### 4. [문서 가이드](./docs/AGENTS.md)
- 각 문서의 역할
- 문서 작성 가이드
- 업데이트 규칙

---

## 🛠 기술 스택

- **프레임워크:** FastAPI (Python)
- **WebSocket:** Socket.IO
- **Database:** MySQL (학습 기록), SQLite (개발 기록)
- **LLM:** Ollama (qwen2.5:3b, gpt-oss-20b)
- **Vector DB:** Qdrant (RAG)
- **MCP:** Model Context Protocol (stdio)

---

## 🚀 실행 방법

```bash
# 개발 모드
cd packages/agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Docker
docker compose up agent
```

**웹 UI 접속:** http://localhost:8787

---

## 📡 주요 API

### Chat

```http
POST /api/chat/message
WebSocket /ws/chat
```

### Structure

```http
POST /api/structure/build
GET /api/structure/blocks
```

### Draft

```http
POST /api/draft/generate
GET /api/draft/list
```

### Record

```http
POST /api/record/session
GET /api/record/timeline
```

---

## 🔄 데이터 흐름

```
사용자 질문
    ↓
Chat Module (RAG 검색 + LLM)
    ↓
자동 트리거 ↓
    ↓
Structure Module (Knowledge Block 생성)
    ↓
RAG 인덱싱 (Qdrant)
    ↓
사용자 Topic 선택
    ↓
Draft Module (블로그 초안)
    ↓
사용자 검토
    ↓
Tistory MCP (발행)
```

---

## 🎯 다음 단계

1. ✅ 요구사항 명세서 작성
2. ✅ 기능 명세서 작성
3. ✅ 인터페이스 명세서 작성
4. ⏳ 상세 설계 (내부 아키텍처)
5. ⏳ 구현 시작

---

**작성일:** 2026-07-24
**작성자:** Warruru with Claude Code
