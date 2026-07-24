# 인터페이스 명세서 - Ollama

**작성일:** 2026-07-24

## API

### POST /api/generate
```json
{
  "model": "qwen2.5:3b",
  "prompt": "질문",
  "stream": true
}
```

### POST /api/embeddings
```json
{
  "model": "nomic-embed-text",
  "prompt": "텍스트"
}
```

**상태:** ✅ 확정
