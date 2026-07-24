# AGENTS.md - WarruruLab AI Agent Guide

## 프로젝트 개요

**WarruruLab**은 Local-First AI 학습 에이전트 시스템입니다.

### 핵심 철학

- **문서 우선 (Documentation-First)**: 코드보다 명세서를 먼저 작성
- **모듈화 (Modular)**: 각 서비스는 독립적으로 동작
- **로컬 우선 (Local-First)**: 모든 처리를 로컬에서 실행
- **크로스 플랫폼 (Cross-Platform)**: Windows ↔ Mac 작업 동기화

---

## 📁 프로젝트 구조

```
warruru-lab/
├── packages/                # 핵심 패키지
│   ├── agent/              # 통합 에이전트
│   ├── web-ui/             # 웹 UI
│   └── local-record/       # 개발 기록 시스템
├── services/               # 보조 서비스
│   ├── ollama/            # LLM 서버
│   ├── qdrant/            # Vector DB
│   ├── sync/              # 크로스 플랫폼 동기화
│   └── tistory-mcp/       # Tistory 연동
├── docs/                   # 전역 문서
│   ├── architecture/      # 아키텍처 설계
│   ├── api/              # API 스펙
│   └── guides/           # 사용 가이드
├── blog/                   # 최종 블로그 글
└── .archive/              # 기존 코드 (참고용)
```

---

## 📦 Packages (핵심 패키지)

### 1. packages/agent/

**통합 AI 에이전트 - 학습의 중심**

4개 모듈로 구성된 통합 에이전트:
- 💬 Chat Module: 학습 대화 + RAG 검색
- 🧠 Structure Module: 지식 구조화
- 📝 Draft Module: 블로그 초안 생성
- 📊 Record Module: 개발 기록 관리

**문서:**
- [`packages/agent/AGENTS.md`](./packages/agent/AGENTS.md) - 서비스 개요
- [`packages/agent/docs/requirements.md`](./packages/agent/docs/requirements.md) - 요구사항 명세서
- [`packages/agent/docs/features.md`](./packages/agent/docs/features.md) - 기능 명세서
- [`packages/agent/docs/interface.md`](./packages/agent/docs/interface.md) - 인터페이스 명세서
- [`packages/agent/docs/AGENTS.md`](./packages/agent/docs/AGENTS.md) - 문서 가이드

---

### 2. packages/web-ui/

**통합 웹 UI - 사용자 인터페이스**

모든 기능에 접근할 수 있는 단일 웹 UI:
- 학습 대화 화면
- 지식 블록 조회
- 블로그 초안 편집
- 개발 기록 타임라인

**문서:**
- [`packages/web-ui/AGENTS.md`](./packages/web-ui/AGENTS.md) - 서비스 개요
- [`packages/web-ui/docs/requirements.md`](./packages/web-ui/docs/requirements.md) - 요구사항 명세서
- [`packages/web-ui/docs/features.md`](./packages/web-ui/docs/features.md) - 기능 명세서
- [`packages/web-ui/docs/interface.md`](./packages/web-ui/docs/interface.md) - 인터페이스 명세서
- [`packages/web-ui/docs/AGENTS.md`](./packages/web-ui/docs/AGENTS.md) - 문서 가이드

---

### 3. packages/local-record/

**개발 기록 시스템 - MCP 기반**

AI Agent (Codex/Claude Code)의 작업 기록:
- MCP 프로토콜 (stdio 통신)
- SQLite 로컬 저장
- 날짜별 조회
- 오프라인 spool 메커니즘

**문서:**
- [`packages/local-record/AGENTS.md`](./packages/local-record/AGENTS.md) - 서비스 개요
- [`packages/local-record/docs/requirements.md`](./packages/local-record/docs/requirements.md) - 요구사항 명세서
- [`packages/local-record/docs/features.md`](./packages/local-record/docs/features.md) - 기능 명세서
- [`packages/local-record/docs/interface.md`](./packages/local-record/docs/interface.md) - 인터페이스 명세서
- [`packages/local-record/docs/AGENTS.md`](./packages/local-record/docs/AGENTS.md) - 문서 가이드

---

## 🛠 Services (보조 서비스)

### 1. services/ollama/

**Local LLM 서버**

로컬 GPU 기반 LLM 추론:
- qwen2.5:3b (빠른 응답)
- gpt-oss-20b (고품질 글 생성)
- nomic-embed-text (Embedding)

**문서:**
- [`services/ollama/AGENTS.md`](./services/ollama/AGENTS.md) - 서비스 개요
- [`services/ollama/docs/requirements.md`](./services/ollama/docs/requirements.md) - 요구사항 명세서
- [`services/ollama/docs/features.md`](./services/ollama/docs/features.md) - 기능 명세서
- [`services/ollama/docs/interface.md`](./services/ollama/docs/interface.md) - 인터페이스 명세서
- [`services/ollama/docs/AGENTS.md`](./services/ollama/docs/AGENTS.md) - 문서 가이드

---

### 2. services/qdrant/

**Vector Database - RAG 검색**

지식 베이스 검색:
- Embedding 저장
- 유사도 검색
- Metadata 필터링

**문서:**
- [`services/qdrant/AGENTS.md`](./services/qdrant/AGENTS.md) - 서비스 개요
- [`services/qdrant/docs/requirements.md`](./services/qdrant/docs/requirements.md) - 요구사항 명세서
- [`services/qdrant/docs/features.md`](./services/qdrant/docs/features.md) - 기능 명세서
- [`services/qdrant/docs/interface.md`](./services/qdrant/docs/interface.md) - 인터페이스 명세서
- [`services/qdrant/docs/AGENTS.md`](./services/qdrant/docs/AGENTS.md) - 문서 가이드

---

### 3. services/sync/

**크로스 플랫폼 동기화 - Windows ↔ Mac**

여러 기기 간 작업물 동기화:
- 암호화 백업
- 자동 병합
- 충돌 해결

**문서:**
- [`services/sync/AGENTS.md`](./services/sync/AGENTS.md) - 서비스 개요
- [`services/sync/docs/requirements.md`](./services/sync/docs/requirements.md) - 요구사항 명세서
- [`services/sync/docs/features.md`](./services/sync/docs/features.md) - 기능 명세서
- [`services/sync/docs/interface.md`](./services/sync/docs/interface.md) - 인터페이스 명세서
- [`services/sync/docs/AGENTS.md`](./services/sync/docs/AGENTS.md) - 문서 가이드

---

### 4. services/tistory-mcp/

**Tistory 블로그 연동 - MCP**

Tistory API를 통한 자동 발행:
- OAuth 인증
- 초안 → 발행
- 카테고리/태그 설정

**문서:**
- [`services/tistory-mcp/AGENTS.md`](./services/tistory-mcp/AGENTS.md) - 서비스 개요
- [`services/tistory-mcp/docs/requirements.md`](./services/tistory-mcp/docs/requirements.md) - 요구사항 명세서
- [`services/tistory-mcp/docs/features.md`](./services/tistory-mcp/docs/features.md) - 기능 명세서
- [`services/tistory-mcp/docs/interface.md`](./services/tistory-mcp/docs/interface.md) - 인터페이스 명세서
- [`services/tistory-mcp/docs/AGENTS.md`](./services/tistory-mcp/docs/AGENTS.md) - 문서 가이드

---

## 📚 전역 문서 (docs/)

### Architecture (아키텍처)

시스템 전체 설계 문서:
- [`docs/architecture/system-overview.md`](./docs/architecture/system-overview.md) - 전체 시스템 개요
- [`docs/architecture/local-first-strategy.md`](./docs/architecture/local-first-strategy.md) - Local-First 전략
- [`docs/architecture/cross-platform-sync.md`](./docs/architecture/cross-platform-sync.md) - 크로스 플랫폼 동기화
- [`docs/architecture/data-flow.md`](./docs/architecture/data-flow.md) - 데이터 흐름

### API (API 스펙)

서비스 간 통신 인터페이스:
- [`docs/api/agent-api.md`](./docs/api/agent-api.md) - 통합 에이전트 API
- [`docs/api/rag-api.md`](./docs/api/rag-api.md) - RAG 검색 API
- [`docs/api/sync-api.md`](./docs/api/sync-api.md) - 동기화 API
- [`docs/api/tistory-mcp-api.md`](./docs/api/tistory-mcp-api.md) - Tistory MCP API

### Guides (사용 가이드)

개발 및 운영 가이드:
- [`docs/guides/getting-started.md`](./docs/guides/getting-started.md) - 시작하기
- [`docs/guides/local-development.md`](./docs/guides/local-development.md) - 로컬 개발
- [`docs/guides/deployment.md`](./docs/guides/deployment.md) - 배포 가이드
- [`docs/guides/troubleshooting.md`](./docs/guides/troubleshooting.md) - 문제 해결

---

## 🤖 AI Agent 작업 가이드

### 문서 우선 원칙

**코드를 작성하기 전에 반드시 다음 순서로 문서를 작성합니다:**

1. **요구사항 명세서 (requirements.md)**
   - 왜 이 서비스가 필요한가?
   - 누가 사용하는가?
   - 핵심 목표는 무엇인가?

2. **기능 명세서 (features.md)**
   - 무엇을 할 수 있는가?
   - 각 기능의 입력/출력은?
   - 우선순위는?

3. **인터페이스 명세서 (interface.md)**
   - API 엔드포인트
   - 데이터 스키마
   - 통신 프로토콜

4. **아키텍처 설계**
   - 내부 구조
   - 모듈 구성
   - 의존성

5. **구현 (코드 작성)**
   - 명세서에 따라 구현
   - 테스트 작성
   - 문서 업데이트

### 새 서비스 추가 시

```bash
# 1. 디렉토리 생성
mkdir -p packages/new-service/docs

# 2. AGENTS.md 작성 (서비스 개요)
# 3. docs/requirements.md 작성
# 4. docs/features.md 작성
# 5. docs/interface.md 작성
# 6. docs/AGENTS.md 작성 (문서 가이드)
# 7. 이 파일(루트 AGENTS.md)에 추가
```

### 문서 작성 규칙

- **Markdown 형식** 사용
- **명확한 제목** 계층 구조
- **예시 포함** (코드, API 호출 등)
- **다이어그램** 활용 (Mermaid, ASCII art)
- **업데이트 날짜** 명시

---

## 🔄 작업 흐름

### 학습 대화 → 블로그 발행

```
1. 사용자 질문 입력 (Web UI)
   ↓
2. Chat Module (RAG 검색 + LLM 응답)
   ↓
3. Structure Module (자동 지식 구조화)
   ↓
4. RAG 인덱싱 (Qdrant)
   ↓
5. Draft Module (블로그 초안 생성)
   ↓
6. 사용자 검토 & 수정
   ↓
7. Tistory MCP (자동 발행)
   ↓
8. blog/ 디렉토리 저장 (Git)
```

### 크로스 플랫폼 작업

```
Windows에서 작업
   ↓
Sync Service (자동 백업)
   ↓
서버 (S3/중앙 저장소)
   ↓
Sync Service (Mac)
   ↓
Mac에서 작업 재개
   ↓
자동 병합 & 충돌 해결
```

---

## 📖 추가 자료

- [README.md](./README.md) - 프로젝트 소개
- [warruru-architecture-v2.html](./warruru-architecture-v2.html) - 아키텍처 시각화
- [.archive/](./archive/) - 기존 코드 (참고용)

---

## 🎯 다음 단계

1. 각 서비스의 **요구사항 명세서** 작성
2. 각 서비스의 **기능 명세서** 작성
3. 각 서비스의 **인터페이스 명세서** 작성
4. **아키텍처 상세 설계** 작성
5. **API 스펙** 확정
6. **구현 시작** (명세서 기반)

---

**Last Updated:** 2026-07-24
**Author:** Warruru with Claude Code
