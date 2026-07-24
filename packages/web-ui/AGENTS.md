# packages/web-ui - 통합 웹 UI

## 서비스 개요

**통합 웹 UI**는 WarruruLab의 모든 기능에 접근할 수 있는 단일 사용자 인터페이스입니다.

### 핵심 가치

- **All-In-One**: 하나의 웹 앱으로 모든 기능 접근
- **Real-time**: WebSocket으로 실시간 스트리밍
- **Responsive**: 모바일/태블릿/데스크톱 지원
- **Local**: localhost:8787에서 실행

---

## 주요 화면

### 💬 Chat (학습 대화)

**경로:** `/chat`

**기능:**
- 실시간 대화 (WebSocket 스트리밍)
- 세션 목록 (사이드바)
- RAG 검색 결과 표시
- Markdown 렌더링

---

### 🧠 Knowledge (지식 블록)

**경로:** `/knowledge`

**기능:**
- Topic별 블록 조회
- Block Type 필터링
- 블록 상세 보기
- 블록 검색

---

### 📝 Draft (블로그 초안)

**경로:** `/draft`

**기능:**
- 초안 생성 (Topic 선택 + Block 선택)
- 초안 편집 (Markdown 에디터)
- 미리보기
- Tistory 발행

---

### 📊 Timeline (개발 기록)

**경로:** `/timeline`

**기능:**
- 날짜별 작업 기록
- Tool 필터링
- Checkpoint 타임라인
- Git context 표시

---

## 📚 문서 목차

### 1. [요구사항 명세서](./docs/requirements.md)
- 왜 통합 웹 UI가 필요한가?
- 사용자 경험 목표
- 성능 요구사항

### 2. [기능 명세서](./docs/features.md)
- 4개 주요 화면
- 공통 컴포넌트
- 네비게이션

### 3. [인터페이스 명세서](./docs/interface.md)
- API 호출 패턴
- WebSocket 연결
- 컴포넌트 구조

### 4. [문서 가이드](./docs/AGENTS.md)
- 문서 작성 가이드

---

## 🛠 기술 스택

- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **UI Library:** Shadcn/ui + Tailwind CSS
- **State Management:** Zustand
- **Routing:** React Router v6
- **WebSocket:** Socket.IO Client
- **Markdown:** react-markdown + remark-gfm
- **Editor:** Monaco Editor (Draft 편집)

---

## 🚀 실행 방법

```bash
cd packages/web-ui
npm install
npm run dev
```

**접속:** http://localhost:8787

---

## 🎯 다음 단계

1. ✅ 요구사항 명세서 작성
2. ✅ 기능 명세서 작성
3. ✅ 인터페이스 명세서 작성
4. ⏳ UI/UX 설계 (Figma)
5. ⏳ 구현 시작

---

**작성일:** 2026-07-24
**작성자:** Warruru with Claude Code
