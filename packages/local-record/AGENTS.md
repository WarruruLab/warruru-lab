# packages/local-record - 개발 기록 시스템

## 서비스 개요

**개발 기록 시스템**은 AI Agent (Codex/Claude Code)의 작업을 로컬에 기록하는 MCP 기반 서비스입니다.

> **Note:** 실제 코드는 `local/` 디렉토리에 있습니다. 이 디렉토리는 명세서만 포함합니다.

### 핵심 가치

- **Zero Loss**: 성공 응답을 받은 기록은 절대 사라지지 않음
- **Offline-First**: 데몬에 연결 실패 시 spool에 저장
- **Cross-Machine**: Windows/Mac 모두 지원
- **MCP Protocol**: stdio 통신

---

## 아키텍처

```
AI Agent (Codex/Claude Code)
    │ stdio (MCP)
    ▼
warruru-mcp (어댑터)
    │ HTTP
    ▼
warruru-daemon
    │ SQLite
    ▼
~/.warruru/warruru.db
    │
    ▼
웹 UI (http://localhost:8787/record)
```

---

## 주요 기능

### 📝 MCP 프로토콜 지원

**메시지:**
- `start_work`: 작업 시작
- `record_checkpoint`: 중요 시점 기록
- `finish_work`: 작업 완료

### 💾 오프라인 Spool

데몬에 연결 실패 시:
1. `~/.warruru/spool/`에 임시 저장
2. 데몬 재시작 시 자동 흡수
3. `absorbed/`로 이동

### 🔍 날짜별 조회

- 웹 UI에서 타임라인 조회
- Tool 필터링 (codex, claude-code, antigravity)
- Git context 표시

---

## 📚 문서 목차

### 1. [요구사항 명세서](./docs/requirements.md)
- MCP 기반 기록의 필요성
- 오프라인 보장 목표

### 2. [기능 명세서](./docs/features.md)
- MCP 프로토콜 상세
- Spool 메커니즘
- 웹 UI 기능

### 3. [인터페이스 명세서](./docs/interface.md)
- MCP 메시지 포맷
- HTTP API
- 데이터 스키마

### 4. [문서 가이드](./docs/AGENTS.md)

---

## 🛠 기술 스택

- **MCP 서버:** Python (stdio)
- **Daemon:** FastAPI
- **DB:** SQLite
- **웹 UI:** Jinja2 Templates

---

## 🚀 실행 방법

```bash
cd local
python -m pip install -e .
```

**MCP 설정 (Claude Code):**
```json
{
  "mcpServers": {
    "warruru": {
      "command": "warruru-mcp",
      "env": {"WARRURU_TOOL": "claude-code"}
    }
  }
}
```

**웹 UI:** http://localhost:8787/record

---

**작성일:** 2026-07-24
**실제 코드:** `local/`
