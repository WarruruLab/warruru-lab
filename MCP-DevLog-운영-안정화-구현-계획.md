# MCP-DevLog 운영 안정화 구현 계획

## 목표

MCP 실시간 ingest 중 `CREATE_BLOCK`가 중복으로 들어와도 전체 요청이 실패하지 않도록 한다.

현재 실패 흐름은 다음과 같다.

```text
MCP가 CREATE_BLOCK 전송
-> DevLog에 같은 sessionId + mcpBlockId 블록이 이미 있음
-> DevLog가 block already exists 로 400 반환
-> MCP가 502 반환
-> 메시지 ingest 실패
```

목표 흐름은 다음과 같다.

```text
MCP가 CREATE_BLOCK 전송
-> DevLog에 같은 sessionId + mcpBlockId 블록이 이미 있음
-> 같은 messageId가 이미 연결되어 있으면 성공으로 무시
-> messageId가 아직 없고 기존 블록이 ACTIVE면 기존 블록에 연결
-> 진짜 데이터 충돌만 실패 처리
```

## 최종 결정

1. DevLog가 최종 방어선을 가진다.
   - DB를 가진 쪽이므로 `CREATE_BLOCK` 중복 요청을 실패가 아닌 복구 가능한 요청으로 처리한다.
   - `UNIQUE(session_id, external_block_id)` 제약은 유지한다.

2. MCP는 새 blockId 생성 충돌을 줄인다.
   - 기존 `blk_{sessionId}_{max+1}` 방식은 candidateBlocks가 비거나 오래되면 같은 ID를 다시 만들 수 있다.
   - NEW_BLOCK에는 메시지 기반 결정적 ID를 사용한다.

3. CLOSED 블록은 자동 append하지 않는다.
   - 같은 messageId가 이미 연결된 경우만 성공으로 무시한다.
   - 다른 messageId를 CLOSED 블록에 붙이는 것은 데이터 오염 가능성이 있으므로 별도 정책으로 분리한다.

4. `APPLIED`와 `IGNORED`를 우선 사용한다.
   - 최소 변경을 위해 DevLog 응답 status는 기존 계열을 유지한다.
   - 관측성이 필요하면 이후 `RECOVERED`를 추가한다.

## 담당 분리

### Agent A: DevLog 중복 CREATE 복구

작업 repo:

```text
D:\project_univ\warruru-lab\devlog
```

주요 파일:

```text
backend/src/main/java/com/devlog/devlog/service/analysis/McpBlockEventIngestService.java
backend/src/main/java/com/devlog/devlog/infra/persistence/JdbcSessionBlockRepository.java
backend/src/main/java/com/devlog/devlog/infra/persistence/JdbcSessionBlockMessageRepository.java
backend/src/test/java/com/devlog/devlog/service/analysis/McpBlockEventIngestServiceTest.java
backend/src/main/resources/schema.sql
```

구현 범위:

1. `McpBlockEventIngestService.handleCreateBlock(...)` 수정
   - 기존 블록 발견 시 `IllegalArgumentException("block already exists")`를 던지지 않는다.
   - 기존 블록과 요청 messageId의 매핑 상태를 확인한다.

2. 기존 블록이 있고 같은 messageId가 이미 같은 block에 매핑된 경우
   - block 추가 생성 없음
   - mapping 추가 없음
   - response status: `IGNORED`
   - `mcp_ingest_event` 저장
   - 세션을 `FAILED`로 바꾸지 않음

3. 기존 블록이 있고 messageId가 아직 매핑되지 않은 경우
   - 기존 블록이 `ACTIVE`이면 해당 block에 message mapping 추가
   - `session_message`를 structured 처리
   - block 본문은 덮어쓰지 않는 것을 기본으로 함
   - response status: `APPLIED`
   - `mcp_ingest_event` 저장

4. 같은 messageId가 다른 block에 이미 매핑된 경우
   - 데이터 충돌로 보고 실패 유지
   - 이 경우는 조용히 성공 처리하지 않음

5. insert race 처리
   - 선조회 후 insert 사이에 다른 요청이 같은 block을 생성할 수 있다.
   - `DuplicateKeyException`이 발생하면 다시 `findByExternalBlockId(sessionId, mcpBlockId)`로 조회해 복구 경로를 탄다.
   - 같은 block/message mapping insert race도 no-op 성공으로 처리할 수 있게 한다.

DevLog 케이스별 동작:

| 케이스 | 동작 | 응답 |
|---|---|---|
| 같은 eventId 재전송 | 기존 event 기준 중복 처리 | `IGNORED` |
| 다른 eventId, 같은 mcpBlockId, 같은 messageId가 이미 같은 block에 있음 | no-op 성공 | `IGNORED` |
| 다른 eventId, 같은 mcpBlockId, messageId가 미매핑, block ACTIVE | 기존 block에 message 연결 | `APPLIED` |
| 같은 messageId가 다른 block에 이미 있음 | 데이터 충돌 | 실패 유지 |
| 기존 block CLOSED, 같은 messageId 이미 연결 | no-op 성공 | `IGNORED` |
| 기존 block CLOSED, 다른 messageId | 자동 append 금지 | 실패 또는 별도 정책 |

DevLog 테스트:

1. `ingest_createBlockWithExistingBlockAndSameMappedMessage_returnsIgnored`
2. `ingest_createBlockWithExistingBlockButMessageNotMapped_recoversMapping`
3. `ingest_createBlockWithExistingBlockButMessageMappedToOtherBlock_failsConflict`
4. `ingest_createBlockDuplicateKeyDuringSave_recoversExistingBlock`
5. 기존 `ingest_duplicateEventIdIsIgnored` 유지

완료 기준:

```text
./gradlew test --tests "*McpBlockEventIngestServiceTest*"
```

위 테스트가 통과하고, 중복 CREATE로 세션이 `FAILED`가 되지 않아야 한다.

### Agent B: MCP blockId와 DevLog 복구 응답 처리

작업 repo:

```text
D:\project_univ\warruru-lab\mcp
```

주요 파일:

```text
backend/src/devlog_mcp_server/core/routing.py
backend/src/devlog_mcp_server/services/realtime_ingest_service.py
backend/src/devlog_mcp_server/output/devlog_client.py
backend/src/devlog_mcp_server/models.py
backend/tests/test_devlog_realtime_integration.py
backend/tests/test_realtime_contract.py
```

구현 범위:

1. NEW_BLOCK blockId 정책 변경
   - 기존 순번 기반 `blk_{sessionId}_{max+1}`를 신규 기본값으로 쓰지 않는다.
   - 권장 형식:

```text
blk_{safeSessionId}_{safeMessageId}
```

   - sessionId/messageId가 너무 길거나 안전하지 않은 문자를 포함하면 hash suffix를 사용한다.
   - 같은 messageId 재처리 시 같은 blockId가 나오도록 한다.

2. candidateBlocks 안에서 충돌할 경우
   - 같은 blockId가 이미 candidate에 있으면 짧은 hash suffix를 추가한다.
   - 단, 같은 messageId 재처리의 경우에는 같은 ID가 유지되는 것이 더 중요하므로 테스트에서 의도를 분리한다.

3. DevLog 복구 응답 처리
   - DevLog가 중복 CREATE를 200 `IGNORED` 또는 200 `APPLIED`로 반환하면 기존 성공 처리로 수용한다.
   - 만약 이후 DevLog가 409 + 복구 payload를 쓰기로 하면 `DevLogRequestError`에 response payload를 담아 `_send_event()`에서 성공으로 변환한다.
   - 일반 400/409 validation 오류는 계속 실패 처리한다.

4. `_send_event()` 동작
   - 성공 또는 복구 성공 응답이면 event store를 `DELIVERED`로 마킹한다.
   - DevLog 응답의 `blockId`, `targetBlockId`, `status`를 우선 사용한다.
   - recovery payload 없는 4xx는 기존처럼 `FAILED`, `retriable=false`.

MCP blockId 후보 비교:

| 정책 | 판단 |
|---|---|
| 순번 기반 `blk_{sessionId}_{n}` | stale candidate와 재시작에 취약하므로 비권장 |
| UUID 기반 | 충돌은 적지만 같은 메시지 재처리 때 매번 달라져 복구가 어려움 |
| messageId 기반 | 같은 메시지 재처리에 강하고 추적이 쉬워 권장 |
| DevLog 전체 block 목록 조회 후 순번 생성 | 장기적으로 좋지만 API 추가가 필요하므로 2차 작업 |

MCP 테스트:

1. `test_duplicate_create_recovery_response_marks_event_delivered`
   - FakeDevLogClient가 중복 CREATE 복구 응답을 반환
   - MCP event store가 `DELIVERED`가 되는지 확인

2. `test_duplicate_create_recovery_http_conflict_is_treated_as_success`
   - DevLog가 복구 payload 포함 409를 쓰기로 결정할 경우 추가

3. 기존 `test_devlog_4xx_marks_event_as_non_retriable`
   - recovery payload 없는 4xx는 여전히 실패인지 확인

4. routing 테스트
   - NEW_BLOCK blockId가 messageId 기반으로 생성되는지
   - 같은 request 재처리 시 같은 blockId가 나오는지
   - 특수문자/긴 messageId가 safe id로 정규화되는지

완료 기준:

```text
$env:PYTHONPATH="backend/src"
python -m unittest backend.tests.test_devlog_realtime_integration -v
python -m unittest backend.tests.test_realtime_contract -v
```

위 테스트가 통과해야 한다.

### Agent C: E2E 검증과 롤아웃

작업 repo:

```text
D:\project_univ\warruru-lab\mcp
D:\project_univ\warruru-lab\devlog
```

구현 범위:

1. 단위 테스트 고정
   - DevLog service 테스트
   - MCP integration/contract 테스트

2. Docker 기반 E2E
   - DevLog DB
   - DevLog backend
   - MCP backend
   - Ollama/local LLM

3. 100 message local LLM 테스트
   - 먼저 10개로 smoke
   - 이후 100개 전체 실행

PowerShell 예시:

```powershell
cd D:\project_univ\warruru-lab\mcp

$env:PYTHONPATH="backend/src"
$env:RUN_LOCAL_LLM_TEST="1"
$env:MCP_BASE_URL="http://127.0.0.1:8000"
$env:LOCAL_LLM_SMOKE_COUNT="10"
$env:LOCAL_LLM_REPORT_PATH="artifacts/realtime_stabilization_10_report.json"

python -m unittest backend.tests.test_realtime_dummy_session_local_llm -v
```

100개 실행:

```powershell
$env:LOCAL_LLM_SMOKE_COUNT="100"
$env:LOCAL_LLM_REPORT_PATH="artifacts/realtime_stabilization_100_report.json"

python -m unittest backend.tests.test_realtime_dummy_session_local_llm -v
```

검증 시나리오:

| ID | 목적 | 기대 결과 |
|---|---|---|
| S1 | 정상 CREATE_BLOCK | block 1개 생성, message 1개 매핑 |
| S2 | 같은 eventId 재전송 | `IGNORED`, 중복 없음 |
| S3 | 다른 eventId, 같은 mcpBlockId, 같은 messageId | `IGNORED`, 실패 없음 |
| S4 | 다른 eventId, 같은 mcpBlockId, 다른 messageId, ACTIVE block | 기존 block에 매핑 |
| S5 | 같은 message APPEND 재전송 | `IGNORED`, 중복 없음 |
| S6 | DevLog 5xx | MCP event store `RETRYABLE_FAILED` |
| S7 | 일반 4xx | MCP event store `FAILED`, 재시도 금지 |
| S8 | CLOSED block 다른 message 충돌 | 자동 append 금지 |
| S9 | finalize 후 create | CLOSED 1개 + ACTIVE 1개 |
| S10 | 100 message | coverage 100/100 |

완료 기준:

```text
processedCount = 100
final block coverage = 100/100
appendCount >= 1
newBlockCount >= 1
DevLog structured_message_count = 100
DevLog unstructured_message_count = 0
non-retriable failure = 0
```

관측 지표:

```text
MCP:
- sessionId
- messageId
- eventId
- operation
- targetBlockId
- route action, score, reason
- DevLog response status
- event deliveryState, attemptCount, retriable

DevLog:
- eventId
- operation
- sessionId
- messageId
- blockId
- mcpBlockId
- created/appended/ignored
- session structured/unstructured/block count
```

DB 점검 쿼리:

```sql
SELECT session_id, external_block_id, COUNT(*)
FROM session_block
GROUP BY session_id, external_block_id
HAVING COUNT(*) > 1;

SELECT block_id, message_id, COUNT(*)
FROM session_block_message
GROUP BY block_id, message_id
HAVING COUNT(*) > 1;

SELECT session_id, COUNT(*)
FROM session_block
WHERE status = 'ACTIVE'
GROUP BY session_id
HAVING COUNT(*) > 1;
```

롤아웃 순서:

1. DevLog 단위 테스트 통과
2. MCP 단위/계약 테스트 통과
3. local E2E 10 message
4. local E2E 100 message
5. 장애 주입 테스트
6. shadow rollout
7. 제한 rollout
8. 기본 활성화

## 전체 구현 순서

1. Agent A가 DevLog `CREATE_BLOCK` 중복 복구를 먼저 구현한다.
2. Agent A가 DevLog 테스트를 추가하고 통과시킨다.
3. Agent B가 MCP에서 DevLog 복구 응답을 성공으로 처리한다.
4. Agent B가 MCP NEW_BLOCK blockId를 messageId 기반으로 바꾼다.
5. Agent B가 MCP 테스트를 추가하고 통과시킨다.
6. Agent C가 10 message E2E를 실행한다.
7. Agent C가 100 message E2E를 실행한다.
8. 장애 주입과 DB 중복 점검을 수행한다.

## 구현 중 주의사항

1. 기존 block을 발견했을 때 title, summary, content, status를 무조건 덮어쓰지 않는다.
   - 오래된 CREATE_BLOCK 요청이 FINALIZE 이후 상태를 되돌릴 수 있다.

2. 선조회만 믿지 않는다.
   - DB unique constraint에서 충돌이 터질 수 있으므로 insert 예외도 복구 경로로 처리한다.

3. CLOSED block에 다른 message를 자동 연결하지 않는다.
   - 같은 message가 이미 연결된 경우만 `IGNORED`로 처리한다.

4. 같은 messageId가 다른 block에 이미 매핑된 경우는 실패로 둔다.
   - 자동 복구하면 데이터가 꼬일 수 있다.

5. MCP 4xx 처리를 전부 성공으로 바꾸지 않는다.
   - 복구 payload 또는 DevLog 200 응답으로 명시된 케이스만 성공 처리한다.

## 남는 후속 과제

1. DevLog에 세션 전체 block 조회 API 추가

```text
GET /internal/mcp/sessions/{sessionId}/blocks
```

2. MCP event store 영속화
   - 현재 기본은 in-memory라 재시작 시 전송 상태를 잃는다.

3. reconciliation job 연결
   - core 함수는 있으나 운영 job/endpoint는 아직 부족하다.

4. ACTIVE block 2개 이상 정책 결정
   - 현재 finalize 없이 create가 가능하면 세션에 ACTIVE가 여러 개 생길 수 있다.

