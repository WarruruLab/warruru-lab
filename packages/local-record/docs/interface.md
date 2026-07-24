# 인터페이스 명세서 - 개발 기록 시스템

**작성일:** 2026-07-24
**버전:** 1.0.0

---

## 1. MCP Protocol (stdio)

### start_work
```json
{
  "tool": "start_work",
  "params": {
    "sessionId": "work-123",
    "toolName": "claude-code",
    "description": "API 설계"
  }
}
```

### record_checkpoint
```json
{
  "tool": "record_checkpoint",
  "params": {
    "sessionId": "work-123",
    "description": "설계 완료"
  }
}
```

### finish_work
```json
{
  "tool": "finish_work",
  "params": {
    "sessionId": "work-123",
    "status": "success"
  }
}
```

---

## 2. HTTP API

### GET /api/timeline
```http
GET /api/timeline?date=2026-07-24
```

---

**상태:** ✅ 확정
