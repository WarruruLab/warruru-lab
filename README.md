# 🦀 WarruruLab

**Local-First AI Learning Agent**

개인 학습을 위한 통합 AI 에이전트 시스템. 모든 학습 대화, 지식 구조화, 블로그 작성, 개발 기록을 로컬에서 실행하며, 완전한 프라이버시와 비용 절감을 제공합니다.

## 🎯 핵심 전략

- **Local-First**: 모든 처리를 로컬에서 (비용 96% 절감)
- **All-In-One Agent**: 통합 에이전트로 단순화
- **Cross-Platform**: Windows ↔ Mac 작업물 자동 동기화
- **Privacy**: 개인 학습 기록은 로컬 전용
- **무료 GPU**: 로컬 GPU로 무제한 LLM 사용

## 📊 시스템 아키텍처

```
💻 Local Environment
├─ WarruruLab Agent (통합 에이전트)
│   ├─ 💬 Chat Module (학습 대화 + RAG)
│   ├─ 🧠 Structure Module (지식 구조화)
│   ├─ 📝 Draft Module (블로그 초안)
│   └─ 📊 Record Module (개발 기록)
├─ 🤖 Ollama (Local LLM)
├─ 🔍 RAG Engine (Qdrant)
└─ 🎨 Unified Web UI (localhost:8787)

☁️ Server Environment (선택)
├─ 🌐 Portfolio Site (GitHub Pages)
├─ 💾 Backup Service (자동 백업)
├─ 📈 Analytics Dashboard (학습 통계)
├─ 🔗 Share API (선택적 공유)
└─ 📱 Tistory MCP (블로그 발행)
```

## 🗂 모노레포 구조

```
warruru-lab/
├── packages/
│   ├── agent/          # 통합 에이전트 (FastAPI)
│   │   ├── chat/       # Chat Module
│   │   ├── structure/  # Structure Module
│   │   ├── draft/      # Draft Module
│   │   └── record/     # Record Module
│   ├── web-ui/         # 통합 웹 UI (React + Vite)
│   ├── local-record/   # 개발 기록 시스템 (MCP)
│   └── shared/         # 공통 라이브러리
├── services/
│   ├── ollama/         # LLM 서버 (Docker)
│   ├── qdrant/         # Vector DB (Docker)
│   └── sync/           # Windows ↔ Mac 동기화 서비스
├── docs/               # 문서
│   ├── architecture/   # 아키텍처 설계
│   ├── api/            # API 스펙
│   └── guides/         # 사용 가이드
├── blog/               # 최종 블로그 글 (Markdown)
│   ├── cs/             # CS 기초
│   ├── frameworks/     # 프레임워크
│   ├── warruru-lab/    # 프로젝트 개발기
│   └── lessons/        # 학습 교훈
├── .archive/           # 기존 분산 서비스 (참고용)
│   ├── devtalk/
│   ├── devlog/
│   └── AI/
├── docker-compose.yml  # 전체 스택 실행
├── .gitignore
└── README.md
```

## 🚀 빠른 시작

### 1. 로컬 환경 설정

```bash
# 저장소 클론
git clone https://github.com/WarruruLab/warruru-lab.git
cd warruru-lab

# Docker Compose로 전체 스택 실행
docker compose up -d

# 웹 UI 접속
open http://localhost:8787
```

### 2. 크로스 플랫폼 동기화 (Windows ↔ Mac)

```bash
# Sync Service 실행 (자동 백업 & 동기화)
cd services/sync
python sync_daemon.py --platform windows  # Windows
python sync_daemon.py --platform mac      # Mac

# 같은 날 같은 작업물 자동 병합
# - 타임스탬프 기반 중복 제거
# - 내용 유사도 기반 머지
```

## 💡 주요 기능

### 💬 학습 대화 (Chat Module)

```bash
# 웹 UI에서 질문
# → RAG 검색 (과거 학습 기록)
# → Ollama LLM 응답
# → 자동 구조화 (Structure Module)
```

### 🧠 지식 구조화 (Structure Module)

```bash
# 대화 → Knowledge Block 자동 생성
# - Block Type: concept, comparison, example, summary
# - Metadata: topic, tags, status
# - RAG 인덱싱 자동 실행
```

### 📝 블로그 초안 (Draft Module)

```bash
# Topic 선택 → Block 조회 → RAG Context
# → 고품질 LLM (gpt-oss-20b)
# → 블로그 초안 생성 (Markdown)
```

### 📊 개발 기록 (Record Module)

```bash
# AI Agent (Codex/Claude Code) 작업 기록
# - MCP 프로토콜 (stdio)
# - 날짜별 조회
# - Git context 저장
```

### 📱 Tistory 발행 (계획)

```bash
# 블로그 초안 검토 완료 후
# → Tistory MCP로 자동 발행
# → 카테고리, 태그 자동 설정
# → 공개 범위 제어
```

## 🛠 기술 스택

### Backend
- **FastAPI** (Python) - 통합 에이전트 API
- **Spring Boot** (Java) - 레거시 서비스 (마이그레이션 예정)

### Frontend
- **React** + **Vite** - 통합 웹 UI
- **WebSocket** - 실시간 LLM 스트리밍

### AI & LLM
- **Ollama** - Local LLM 서버
  - qwen2.5:3b (빠른 응답)
  - gpt-oss-20b (고품질 글 생성)
  - nomic-embed-text (Embedding)

### Database & Storage
- **SQLite** - 로컬 개발 기록
- **MySQL** - 학습 대화, Knowledge Block
- **Qdrant** - Vector Database (RAG)

### DevOps
- **Docker** + **Docker Compose**
- **GitHub Actions** (CI/CD)

## 💰 비용 절감 효과

| 항목 | 기존 (분산 서버) | 신규 (로컬) | 절감 |
|------|----------------|------------|------|
| **월 운영비** | 13만원 | 5천원 | **-96%** |
| **GPU 서버** | 월 10만원 | 전기세 | **-100%** |
| **응답 속도** | 500ms | 50ms | **10배** |
| **관리 복잡도** | 5개 서비스 | 1개 통합 | **-80%** |

## 🔒 프라이버시

- ✅ 모든 학습 대화는 로컬 저장
- ✅ LLM 추론은 개인 GPU 사용
- ✅ 외부 API 호출 없음
- ✅ 선택적으로만 서버 백업

## 🌐 크로스 플랫폼 동기화

### Windows ↔ Mac 작업 흐름

1. **Windows에서 작업**
   ```bash
   # 학습 대화 → Knowledge Block 생성
   # Sync Service가 자동 백업 (암호화)
   ```

2. **Mac에서 작업 재개**
   ```bash
   # Sync Service가 자동 동기화
   # 같은 날 작업물 자동 병합
   # 중복 제거 & 타임스탬프 정렬
   ```

3. **자동 병합 규칙**
   - 같은 날 (KST 기준)
   - 같은 sessionId 또는 topic
   - 내용 유사도 > 90% → 중복 제거
   - 타임스탬프 순 정렬

## 📱 Tistory MCP 통합 (계획)

```python
# Tistory MCP 사용 예시
from warruru.integrations import TistoryMCP

# 블로그 초안 → Tistory 발행
tistory = TistoryMCP(access_token="...")
tistory.publish_draft(
    draft_id="draft-123",
    category="기술",
    tags=["Spring Boot", "JPA"],
    visibility="public"
)
```

## 📖 문서

- [아키텍처 설계](./docs/architecture/)
- [API 스펙](./docs/api/)
- [로컬 개발 가이드](./docs/guides/local-development.md)
- [크로스 플랫폼 동기화](./docs/guides/cross-platform-sync.md)

## 🤝 기여

개인 학습 프로젝트이지만 피드백과 제안은 환영합니다!

## 📄 라이선스

MIT License

---

**Built with 🦀 by Warruru**
