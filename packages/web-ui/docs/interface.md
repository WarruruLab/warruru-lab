# 인터페이스 명세서 - 통합 웹 UI

**작성일:** 2026-07-24
**버전:** 1.0.0

---

## 1. 컴포넌트 구조

```
App
├── Layout
│   ├── Sidebar (네비게이션)
│   └── Main
│       ├── ChatPage
│       ├── KnowledgePage
│       ├── DraftPage
│       └── TimelinePage
└── Providers
    ├── WebSocketProvider
    ├── ThemeProvider
    └── ToastProvider
```

---

## 2. API 클라이언트

### 2.1 HTTP Client

```typescript
// lib/api.ts
class AgentAPI {
  baseUrl = 'http://localhost:8000';

  async chat(sessionId: string, message: string) {
    return fetch(`${this.baseUrl}/api/chat/message`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sessionId, message})
    });
  }
}
```

---

## 3. WebSocket 클라이언트

```typescript
// lib/socket.ts
import io from 'socket.io-client';

const socket = io('http://localhost:8000', {
  autoConnect: false
});

// Chat 스트리밍
socket.on('chat:stream:chunk', (data) => {
  // UI 업데이트
});
```

---

## 4. 상태 관리 (Zustand)

```typescript
// stores/chat.ts
interface ChatStore {
  sessions: Session[];
  currentSession: Session | null;
  messages: Message[];

  sendMessage: (message: string) => Promise<void>;
  loadSessions: () => Promise<void>;
}

export const useChatStore = create<ChatStore>((set) => ({
  // ...
}));
```

---

## 5. 주요 컴포넌트

### 5.1 ChatPage

```tsx
export function ChatPage() {
  const { messages, sendMessage } = useChatStore();
  const [input, setInput] = useState('');

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} />
      <ChatInput
        value={input}
        onSend={sendMessage}
      />
    </div>
  );
}
```

### 5.2 DraftEditor

```tsx
export function DraftEditor({ draftId }: Props) {
  const [content, setContent] = useState('');

  return (
    <div className="grid grid-cols-2 gap-4">
      <MonacoEditor
        value={content}
        onChange={setContent}
        language="markdown"
      />
      <MarkdownPreview content={content} />
    </div>
  );
}
```

---

## 6. 라우팅

```typescript
// App.tsx
<BrowserRouter>
  <Routes>
    <Route path="/" element={<Layout />}>
      <Route index element={<Navigate to="/chat" />} />
      <Route path="chat" element={<ChatPage />} />
      <Route path="knowledge" element={<KnowledgePage />} />
      <Route path="draft" element={<DraftPage />} />
      <Route path="timeline" element={<TimelinePage />} />
    </Route>
  </Routes>
</BrowserRouter>
```

---

## 7. 키보드 단축키

| 키 | 동작 |
|----|------|
| `Cmd/Ctrl + 1` | Chat 화면 |
| `Cmd/Ctrl + 2` | Knowledge 화면 |
| `Cmd/Ctrl + 3` | Draft 화면 |
| `Cmd/Ctrl + 4` | Timeline 화면 |
| `Cmd/Ctrl + K` | 검색 |
| `Cmd/Ctrl + N` | 새 대화 |

---

**상태:** ✅ 확정
