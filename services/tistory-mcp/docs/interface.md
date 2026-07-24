# 인터페이스 명세서 - Tistory MCP

**작성일:** 2026-07-24

## MCP Tools

### publish_draft

**Input:**
```json
{
  "tool": "publish_draft",
  "params": {
    "draftId": "draft-999",
    "category": "기술",
    "tags": ["JPA", "Spring Boot"],
    "visibility": "public"
  }
}
```

**Output:**
```json
{
  "success": true,
  "postId": "12345",
  "url": "https://warruru.tistory.com/12345",
  "savedTo": "blog/cs/2026-07-24-jpa-n-plus-one.md"
}
```

---

## Tistory API

### POST /post/write
```json
{
  "access_token": "...",
  "blogName": "warruru",
  "title": "JPA N+1 문제 해결",
  "content": "...",
  "category": "0",
  "tag": "JPA,Spring Boot",
  "visibility": "3"
}
```

**상태:** ✅ 계획 확정
