# 인터페이스 명세서 - Qdrant

**작성일:** 2026-07-24

## API

### POST /collections/{name}/points
```json
{
  "points": [{
    "id": "block-123",
    "vector": [...],
    "payload": {"topic": "JPA", "tags": [...]}
  }]
}
```

### POST /collections/{name}/points/search
```json
{
  "vector": [...],
  "limit": 5,
  "filter": {"must": [{"key": "topic", "match": {"value": "JPA"}}]}
}
```

**상태:** ✅ 확정
