# 기능 명세서 - 통합 웹 UI

**작성일:** 2026-07-24
**버전:** 1.0.0

---

## 1. Chat (학습 대화)

### 1.1 실시간 대화
- WebSocket 스트리밍
- Markdown 렌더링
- 코드 하이라이팅

### 1.2 세션 관리
- 사이드바: 세션 목록
- 세션 생성/삭제
- 세션 검색

### 1.3 RAG 결과 표시
- 검색된 블록 카드
- 유사도 점수
- 클릭 시 블록 상세

---

## 2. Knowledge (지식 블록)

### 2.1 블록 조회
- Topic 필터
- Block Type 필터
- 날짜 범위

### 2.2 블록 상세
- 메시지 원문
- Metadata (tags, status)
- 관련 블록

---

## 3. Draft (블로그 초안)

### 3.1 초안 생성
- Topic 선택
- Block 선택 (체크박스)
- Style 선택 (technical/casual/tutorial)

### 3.2 편집
- Monaco Editor (Markdown)
- 실시간 미리보기
- 저장/취소

### 3.3 발행
- Tistory 카테고리/태그 설정
- 공개 범위
- 발행 후 local blog/ 저장

---

## 4. Timeline (개발 기록)

### 4.1 날짜별 타임라인
- 캘린더 뷰
- 일별 요약

### 4.2 작업 상세
- Checkpoint 타임라인
- Git context
- Tool 필터

---

## 5. 공통 기능

### 5.1 네비게이션
- 좌측 사이드바 (고정)
- 키보드 단축키 (Cmd/Ctrl + 1-4)

### 5.2 알림
- Toast 메시지 (성공/오류)
- WebSocket 연결 상태

### 5.3 설정
- LLM 모델 선택
- RAG Top-K
- 테마 (Dark/Light)

---

**우선순위:** P0 (모든 기능 MVP)

**상태:** ✅ 확정
