# 인터페이스 명세서 - Sync Service

**작성일:** 2026-07-24

## API

### POST /api/sync/backup
```json
{
  "machineId": "mac-m1",
  "data": {...},
  "encrypted": true
}
```

### GET /api/sync/download
```json
{
  "machineId": "windows-desktop",
  "since": "2026-07-24T00:00:00Z"
}
```

**상태:** ✅ 계획 확정
