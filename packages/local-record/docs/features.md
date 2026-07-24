# 기능 명세서 - 개발 기록 시스템

**작성일:** 2026-07-24
**버전:** 1.0.0

---

## 1. MCP 프로토콜

### 1.1 start_work
작업 시작 기록

### 1.2 record_checkpoint
중요 시점 기록

### 1.3 finish_work
작업 완료 기록

---

## 2. Offline Spool

### 2.1 저장
- `~/.warruru/spool/`에 JSON 저장

### 2.2 흡수
- 데몬 재시작 시 자동 처리
- `absorbed/`로 이동

---

## 3. 웹 UI

### 3.1 타임라인
- 날짜별 조회
- Tool 필터링

### 3.2 작업 상세
- Checkpoint 목록
- Git context

---

**상태:** ✅ 확정
