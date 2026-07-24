# 인터페이스 명세서 - 통합 AI 에이전트

**작성일:** 2026-07-24
**최종 업데이트:** 2026-07-24
**버전:** 1.0.0
**Base URL:** `http://localhost:8000`

---

## 1. REST API

### 1.1 Chat Module

#### POST /api/chat/message

채팅 메시지 전송

**Request:**
```http
POST /api/chat/message
Content-Type: application/json

{
  "sessionId": "session-123",
  "message": "JPA N+1 문제 해결 방법은?",
  "userId": "pswaa"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "messageId": "msg-456",
  "content": "N+1 문제는 지연 로딩 시 발생합니다...",
  "ragResults": [
    {
      "blockId": "block-789",
      "topic": "JPA",
      "summary": "fetch join 사용법",
      "score": 0.92
    }
  ],
  "timestamp": "2026-07-24T10:30:00Z"
}
```

**Error:**
```http
HTTP/1.1 500 Internal Server Error

{
  "error": "LLM_TIMEOUT",
  "message": "LLM 응답 시간 초과 (30초)"
}
```

---

#### GET /api/chat/sessions

세션 목록 조회

**Request:**
```http
GET /api/chat/sessions?userId=pswaa&limit=20&offset=0
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "sessions": [
    {
      "sessionId": "session-123",
      "topic": "JPA 학습",
      "messageCount": 15,
      "createdAt": "2026-07-24T09:00:00Z",
      "updatedAt": "2026-07-24T10:30:00Z"
    }
  ],
  "total": 50,
  "hasMore": true
}
```

---

#### GET /api/chat/messages

세션 메시지 조회

**Request:**
```http
GET /api/chat/messages?sessionId=session-123&limit=50
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "messages": [
    {
      "messageId": "msg-456",
      "role": "user",
      "content": "JPA N+1 문제 해결 방법은?",
      "timestamp": "2026-07-24T10:30:00Z"
    },
    {
      "messageId": "msg-457",
      "role": "assistant",
      "content": "N+1 문제는...",
      "timestamp": "2026-07-24T10:30:05Z"
    }
  ]
}
```

---

### 1.2 Structure Module

#### POST /api/structure/build

Knowledge Block 수동 생성

**Request:**
```http
POST /api/structure/build
Content-Type: application/json

{
  "sessionId": "session-123",
  "messageIds": ["msg-456", "msg-457", "msg-458"]
}
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "blockId": "block-789",
  "blockType": "concept",
  "topic": "JPA",
  "summary": "N+1 문제 해결 - fetch join",
  "tags": ["JPA", "N+1", "fetch-join"],
  "status": "success",
  "messages": ["msg-456", "msg-457", "msg-458"],
  "createdAt": "2026-07-24T10:35:00Z"
}
```

---

#### GET /api/structure/blocks

Knowledge Block 조회

**Request:**
```http
GET /api/structure/blocks?topic=JPA&blockType=concept&limit=10
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "blocks": [
    {
      "blockId": "block-789",
      "blockType": "concept",
      "topic": "JPA",
      "summary": "N+1 문제 해결",
      "tags": ["JPA", "N+1"],
      "messageCount": 3,
      "createdAt": "2026-07-24T10:35:00Z"
    }
  ],
  "total": 25
}
```

---

#### GET /api/structure/blocks/{blockId}

Block 상세 조회

**Response:**
```http
HTTP/1.1 200 OK

{
  "blockId": "block-789",
  "blockType": "concept",
  "topic": "JPA",
  "summary": "N+1 문제 해결 - fetch join",
  "tags": ["JPA", "N+1", "fetch-join"],
  "status": "success",
  "messages": [
    {
      "messageId": "msg-456",
      "role": "user",
      "content": "...",
      "timestamp": "2026-07-24T10:30:00Z"
    }
  ],
  "ragMetadata": {
    "vectorId": "vec-123",
    "indexed": true
  }
}
```

---

### 1.3 Draft Module

#### POST /api/draft/generate

블로그 초안 생성

**Request:**
```http
POST /api/draft/generate
Content-Type: application/json

{
  "topic": "JPA N+1 문제 해결",
  "blockIds": ["block-789", "block-790"],
  "style": "technical",
  "ragContext": true,
  "userId": "pswaa"
}
```

**Response:**
```http
HTTP/1.1 202 Accepted

{
  "draftId": "draft-999",
  "status": "generating",
  "estimatedTime": 20
}
```

**비동기 완료 확인:**
```http
GET /api/draft/{draftId}

{
  "draftId": "draft-999",
  "status": "completed",
  "title": "JPA N+1 문제, fetch join으로 해결하기",
  "content": "# JPA N+1 문제, fetch join으로 해결하기\n\n## 배경...",
  "wordCount": 1500,
  "createdAt": "2026-07-24T10:40:00Z"
}
```

---

#### GET /api/draft/list

초안 목록 조회

**Request:**
```http
GET /api/draft/list?userId=pswaa&status=completed&limit=10
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "drafts": [
    {
      "draftId": "draft-999",
      "title": "JPA N+1 문제 해결",
      "status": "completed",
      "wordCount": 1500,
      "createdAt": "2026-07-24T10:40:00Z"
    }
  ],
  "total": 15
}
```

---

### 1.4 Record Module

#### POST /api/record/session

작업 세션 생성/업데이트

**Request:**
```http
POST /api/record/session
Content-Type: application/json

{
  "sessionId": "work-session-123",
  "tool": "claude-code",
  "machineId": "mac-m1",
  "action": "start",  // start, checkpoint, finish
  "gitBranch": "feature/new-api",
  "gitCommit": "abc123",
  "description": "API 설계 완료"
}
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "sessionId": "work-session-123",
  "status": "active",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

---

#### GET /api/record/timeline

작업 타임라인 조회

**Request:**
```http
GET /api/record/timeline?date=2026-07-24&tool=claude-code
```

**Response:**
```http
HTTP/1.1 200 OK

{
  "date": "2026-07-24",
  "sessions": [
    {
      "sessionId": "work-session-123",
      "tool": "claude-code",
      "startedAt": "2026-07-24T09:00:00Z",
      "finishedAt": "2026-07-24T12:00:00Z",
      "checkpoints": [
        {
          "timestamp": "2026-07-24T10:00:00Z",
          "description": "API 설계 완료"
        }
      ]
    }
  ]
}
```

---

## 2. WebSocket

### 2.1 연결

**Endpoint:** `ws://localhost:8000/ws`

**Protocol:** Socket.IO

**Connection:**
```javascript
const socket = io('http://localhost:8000', {
  auth: {
    userId: 'pswaa'
  }
});
```

---

### 2.2 Chat Streaming

**Event:** `chat:stream`

**Client → Server:**
```javascript
socket.emit('chat:message', {
  sessionId: 'session-123',
  message: 'JPA N+1 문제 해결 방법은?'
});
```

**Server → Client:**
```javascript
// 스트리밍 시작
socket.on('chat:stream:start', (data) => {
  console.log('Message ID:', data.messageId);
});

// 청크 수신
socket.on('chat:stream:chunk', (data) => {
  console.log('Chunk:', data.chunk);
  // data.chunk: "N+1", " 문제는", " 지연", " 로딩", ...
});

// 스트리밍 완료
socket.on('chat:stream:end', (data) => {
  console.log('Complete message:', data.content);
  console.log('RAG results:', data.ragResults);
});

// 에러
socket.on('chat:stream:error', (error) => {
  console.error('Error:', error.message);
});
```

---

### 2.3 Draft Streaming

**Event:** `draft:stream`

**Client → Server:**
```javascript
socket.emit('draft:generate', {
  topic: 'JPA N+1 문제 해결',
  blockIds: ['block-789']
});
```

**Server → Client:**
```javascript
socket.on('draft:stream:chunk', (data) => {
  console.log('Draft chunk:', data.chunk);
});

socket.on('draft:stream:end', (data) => {
  console.log('Draft ID:', data.draftId);
  console.log('Full content:', data.content);
});
```

---

## 3. MCP Protocol (stdio)

### 3.1 프로토콜 개요

**통신 방식:** stdio (JSON Lines)

**메시지 형식:**
```json
{"tool": "start_work", "params": {...}}
{"tool": "record_checkpoint", "params": {...}}
{"tool": "finish_work", "params": {...}}
```

---

### 3.2 start_work

**목적:** 작업 시작 기록

**Input:**
```json
{
  "tool": "start_work",
  "params": {
    "sessionId": "work-session-123",
    "toolName": "claude-code",
    "machineId": "mac-m1",
    "gitBranch": "feature/new-api",
    "gitCommit": "abc123",
    "description": "새 API 설계"
  }
}
```

**Output:**
```json
{
  "success": true,
  "sessionId": "work-session-123",
  "timestamp": "2026-07-24T09:00:00Z"
}
```

---

### 3.3 record_checkpoint

**목적:** 중요 시점 기록

**Input:**
```json
{
  "tool": "record_checkpoint",
  "params": {
    "sessionId": "work-session-123",
    "description": "API 설계 완료",
    "context": {
      "files": ["api/routes.py"],
      "changes": "POST /api/users 엔드포인트 추가"
    }
  }
}
```

**Output:**
```json
{
  "success": true,
  "checkpointId": "checkpoint-456"
}
```

---

### 3.4 finish_work

**목적:** 작업 완료 기록

**Input:**
```json
{
  "tool": "finish_work",
  "params": {
    "sessionId": "work-session-123",
    "status": "success",  // success, partial, failed
    "summary": "API 설계 및 구현 완료"
  }
}
```

**Output:**
```json
{
  "success": true,
  "sessionId": "work-session-123",
  "duration": 10800,  // seconds
  "checkpointCount": 5
}
```

---

## 4. 데이터 스키마

### 4.1 Message

```typescript
interface Message {
  messageId: string;
  sessionId: string;
  userId: string;
  role: 'user' | 'assistant';
  content: string;
  ragResults?: RAGResult[];
  timestamp: string;  // ISO 8601
}
```

---

### 4.2 Knowledge Block

```typescript
interface KnowledgeBlock {
  blockId: string;
  sessionId: string;
  userId: string;
  blockType: 'concept' | 'comparison' | 'example' | 'misunderstanding' | 'summary' | 'blog_candidate';
  topic: string;
  summary: string;
  tags: string[];
  status: 'open' | 'neutral' | 'failed' | 'success';
  messages: string[];  // messageIds
  ragMetadata?: {
    vectorId: string;
    indexed: boolean;
  };
  createdAt: string;
  updatedAt: string;
}
```

---

### 4.3 Draft

```typescript
interface Draft {
  draftId: string;
  userId: string;
  topic: string;
  title: string;
  content: string;  // Markdown
  blockIds: string[];
  style: 'technical' | 'casual' | 'tutorial';
  status: 'generating' | 'completed' | 'failed';
  wordCount: number;
  createdAt: string;
  publishedAt?: string;
}
```

---

### 4.4 Work Session

```typescript
interface WorkSession {
  sessionId: string;
  toolName: string;
  machineId: string;
  gitBranch?: string;
  gitCommit?: string;
  startedAt: string;
  finishedAt?: string;
  status: 'active' | 'completed' | 'failed';
  checkpoints: Checkpoint[];
}

interface Checkpoint {
  checkpointId: string;
  timestamp: string;
  description: string;
  context?: Record<string, any>;
}
```

---

## 5. 에러 코드

| 코드 | 메시지 | HTTP Status |
|------|--------|-------------|
| `INVALID_REQUEST` | 잘못된 요청 | 400 |
| `UNAUTHORIZED` | 인증 실패 | 401 |
| `NOT_FOUND` | 리소스 없음 | 404 |
| `LLM_TIMEOUT` | LLM 타임아웃 (30초) | 500 |
| `DB_ERROR` | DB 오류 | 500 |
| `RAG_SEARCH_FAILED` | RAG 검색 실패 | 500 |

---

## 6. Rate Limiting

개인 사용이므로 **Rate Limiting 없음**

---

## 7. 인증/권한

**현재:** 인증 없음 (로컬 전용)

**향후:** (서버 배포 시)
- JWT 토큰
- API Key

---

## 8. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-07-24 | 1.0.0 | 초안 작성 |

---

**상태:** ✅ 확정
**다음 단계:** 구현 시작
