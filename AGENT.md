# AGENT

## 2026-04-19 MCP LLM 구조화 최신 상태

### 현재까지 확인된 사실

- 100개 더미 메시지 테스트에서 한동안 `appendCount=0`, `newBlockCount=100`, `reason=fallback_conservative_new_block`가 반복됐다.
- 초기 원인은 두 가지였다.
  - 프롬프트 파일이 실제 컨테이너에 적용되지 않던 구간이 있었다.
  - 그 이후에는 실제 narrative routing prompt + candidate/recent payload + schema 조합이 `qwen2.5:3b`에서 timeout 되며 fallback으로 떨어졌다.
- 즉 "1 message = 1 block" 현상은 단순 프롬프트 문구 문제라기보다 timeout과 fallback 경로 문제였다.

### 반영한 구조 변경

- MCP 라우팅 경로는 one-shot 구조에서 2단계 구조로 바꿨다.
  - 1단계: `qwen` route-only
    - `action`
    - `targetBlockId`
    - `score`
    - `reason`
  - 2단계: `gpt` metadata-only
    - `blockType`
    - `status`
    - `topic`
    - `summary`
    - `tags`
- 저장은 끝까지 MCP 코드가 담당한다.
- `RealtimeIngestService.handle_message()`는 현재 `route -> metadata -> final decision -> apply_routing_decision()` 순서로 동작한다.

### 현재 설정 구조

- route/model metadata 분리용 env 키를 추가했다.
  - `OLLAMA_ROUTE_MODEL`
  - `OLLAMA_ROUTE_TIMEOUT_SECONDS`
  - `OLLAMA_METADATA_MODEL`
  - `OLLAMA_METADATA_TIMEOUT_SECONDS`
  - `MCP_ROUTE_PROMPT_FILE`
  - `MCP_ROUTE_PROMPT_TEMPLATE`
  - `MCP_METADATA_PROMPT_FILE`
  - `MCP_METADATA_PROMPT_TEMPLATE`
- prompt 샘플 파일도 분리했다.
  - `infra/prompts/route_router.example.txt`
  - `infra/prompts/metadata_builder.example.txt`

### 현재 운영상 문제

- `gpt-oss-20b`를 metadata 모델로 붙이면 구조는 맞지만 너무 느리다.
- 현재 병목은 "모든 메시지마다 2번 호출"이라는 점이다.
  - `qwen` route 1번
  - `gpt-oss-20b` metadata 1번
- 100개 메시지 연속 처리에서는 누적 시간이 매우 커진다.

### 현재 판단

- 구조 방향 자체는 맞다.
  - `qwen = 분류기`
  - `gpt = 구조화기`
  - `MCP 코드 = 저장기`
- 하지만 운영 관점에서는 모든 메시지에 대해 2단계 호출을 하는 구조가 너무 무겁다.

### 지금 기준 권장 다음 선택

우선순위는 아래 순서다.

1. metadata 모델도 `qwen2.5:3b`로 맞춰 속도를 먼저 확인
2. 그래도 느리면 `APPEND`에서는 metadata LLM 호출을 생략
   - 기존 candidate metadata 재사용
   - `NEW_BLOCK`일 때만 metadata LLM 또는 heuristic 사용
3. 그래도 느리면 metadata를 전부 heuristic으로 내리고 route-only만 LLM 사용

### 문서 상태

- ADR은 현재 구조에 맞게 갱신했다.
  - `ADR-003-MCP-routing을-qwen-route와-gpt-metadata-2단계로-분리.md`
- 이 섹션은 이후 실제 서버 테스트 결과와 운영 판단을 누적 기록하는 최신 요약이다.

## 현재 상태

현재 `devtalk`, `devlog`, `mcp`, `ollama`를 한 서버에서 Docker 기반으로 올리고, `warurulab.site` 도메인 뒤에서 리버스 프록시하는 방향으로 정리 중이다.

완료된 항목:
- `warruru-shared` 공용 Docker 네트워크 기준으로 서비스 간 통신 구조 정리
- `warurulab.site` DNS 연결 및 HTTPS 인증서 발급
- `devtalk`, `devlog`, `mcp` 컨테이너 빌드 및 기동 경로 정리
- `mcp -> ollama` 연결 확인
- `devtalk`, `devlog` 프론트 하위 경로 배포(`/devtalk`, `/devlog`) 방향 정리
- `devlog` 공개 API 경로를 `devtalk` 스타일처럼 namespaced path로 변경
- `devtalk/infra/.env.example`, `devlog/infra/.env.example`의 `MYSQL_PASSWORD` 중복 제거

아직 남은 항목:
- 실제 서버 `.env` 중복 제거 및 값 정리
- 메인 Nginx 설정 최종 검증
- `devtalk`, `devlog` UI 기능 최종 검증
- 100개 더미 데이터 기반 `MCP -> DevLog` 통합 검증
- MCP 분류 프롬프트 품질 조정

## 서비스별 공개 경로 계약

### Devtalk

- UI: `/devtalk/`
- API: `/devtalk/api/devtalk/...`
- backend 내부 controller path: `/api/devtalk/...`

주의:
- 프론트 `VITE_API_BASE_URL`은 `/devtalk/api/devtalk`
- SSE는 `replyTo` 파라미터 기준

### Devlog

- UI: `/devlog/`
- API: `/devlog/api/devlog/...`
- backend 내부 controller path: `/api/devlog/...`

주의:
- 프론트 `VITE_API_BASE_URL`은 `/devlog/api/devlog`
- 프론트 API 호출은 `API_BASE + /sessions`, `API_BASE + /analysis/...`, `API_BASE + /drafts` 패턴으로 맞춤

### MCP

- HTTP API: `/v1/session-blocks:build`
- HTTP API: `/v1/session-blocks:ingest-message`
- DevLog internal API 호출 전제
- Ollama URL: `http://ollama:11434`

## 서버 배포 원칙

### 1. 공용 Docker 네트워크 사용

각 저장소를 분리해서 띄우더라도 모두 `warruru-shared` external network에 붙인다.

서비스 간 주소:
- `DEVTALK_BASE_URL=http://devtalk-backend:8080`
- `DEVLOG_BASE_URL=http://devlog-backend:8081`
- `OLLAMA_BASE_URL=http://ollama:11434`

### 2. 프론트 env는 빌드 타임 반영

`VITE_API_BASE_URL`은 런타임이 아니라 프론트 이미지 빌드 시점에 반영된다.

즉 `.env`를 바꾸면 반드시 다시:

```bash
docker compose up -d --build
```

를 해야 한다.

### 3. 실제 `.env`에서는 `MYSQL_PASSWORD`를 한 번만 선언

예시:

```env
MYSQL_USER=devlog_app
MYSQL_PASSWORD=실제비밀번호
MYSQL_ROOT_PASSWORD=루트비밀번호
MYSQL_URL=jdbc:mysql://devlog-db:3306/devlog?serverTimezone=Asia/Seoul&characterEncoding=UTF-8
MYSQL_USERNAME=devlog_app
```

동일 키가 두 번 나오면 마지막 값이 적용되어 혼선이 생긴다.

## 메인 Nginx 원칙

프론트 컨테이너 내부 nginx가 `/devtalk/...`, `/devlog/...` prefix를 직접 처리하므로, 메인 nginx는 prefix를 strip하지 않고 그대로 넘겨야 한다.

즉 `proxy_pass` 뒤에 슬래시를 붙이지 않는다.

예:

```nginx
location /devtalk/ {
    proxy_pass http://127.0.0.1:8080;
}

location /devlog/ {
    proxy_pass http://127.0.0.1:8081;
}
```

## 100개 더미 데이터 통합 테스트 상태

목표:
- local LLM이 실제로 block 분류
- MCP가 DevLog로 event 반영
- DevLog에서 구조화 결과 조회

중요:
- `tests/test_realtime_dummy_session_local_llm.py`는 단순 LLM 테스트가 아니라 `MCP -> DevLog` 통합 테스트다.
- 그래서 DevLog에 `logical_session`, `session_message`가 먼저 존재해야 한다.

현재 반영:
- 테스트 시작 전에 `devlog-db`에 session/message를 seed하도록 테스트 코드 수정

현재 남은 확인:
- 실제 서버 `.env` 정리 후 seed + ingest가 끝까지 성공하는지 확인
- DevLog에서 block 결과가 실제로 조회되는지 확인

## MCP 분류 프롬프트 상태

현재 `mcp/src/devlog_mcp_server/llm/client.py`의 narrative classification 프롬프트는 다음 방향으로 조정되어 있다.

### 블록 기준

- 한 메시지당 한 블록이 아니라, 나중에 블로그 글을 쓸 때 챕터가 될 핵심 서사 단위로 묶는다.
- 하나의 블록은 한 문제, 한 조사 흐름, 한 설계 결정, 한 구현 묶음, 한 배포 이슈, 한 테스트 인사이트처럼 의미 있는 story unit이어야 한다.

### blockType 판단 기준

- `problem`: 문제 인식, 에러, 증상, 장애 설명
- `proposal`: 가설, 제안, 옵션, 계획
- `trial`: 실제 시도, 변경, 테스트, 확인, 로그 점검
- `result`: 시도 후 결과, 성공/실패/부분 개선
- `insight`: 원인 규명, 교훈, 설계 결론, 일반화된 규칙

### status 판단 기준

- `open`: 아직 해결되지 않은 문제
- `neutral`: 진행 중인 탐색, 제안, 시도
- `failed`: 시도 결과 실패 또는 문제 지속
- `success`: 해결 또는 기대 결과 달성

### tags 판단 기준

- `problem`: `problem`, `symptom`, `component`, `error_code`
- `proposal`: `hypothesis`, `candidates`, `target`, `component`
- `trial`: `method`, `command`, `file`, `endpoint`, `component`
- `result`: `method`, `result`, `effect`, `status_change`
- `insight`: `root_cause`, `lesson`, `rule`, `architecture`

### 현재 관찰된 이슈

프롬프트 조정 과정에서 두 극단이 모두 관찰됐다.

1. 모든 메시지가 첫 블록 하나로 과도하게 몰리는 현상
- 원인 후보: `append` 편향 프롬프트, 낮은 threshold, append 중심 fallback

2. 반대로 한 메시지당 한 블록으로 과세분화되는 현상
- 원인 후보: `NEW_BLOCK`를 너무 쉽게 선택하게 만든 과보정

현재 프롬프트는 이를 완화하기 위해:
- 같은 서브태스크의 연속 메시지는 `APPEND`
- 진짜 다른 story unit이 시작될 때만 `NEW_BLOCK`
- 블로그 글 섹션으로 남길 수 있는 핵심 단위로 구조화

방향으로 맞춰져 있다.

## 지금 바로 확인할 것

### 브라우저 / 프론트

- Devtalk 요청이 `/devtalk/api/devtalk/...`로 나가는지
- Devlog 요청이 `/devlog/api/devlog/...`로 나가는지
- 정적 자산이 `/devtalk/assets/...`, `/devlog/assets/...`로 나가는지

### 백엔드 직접 확인

```bash
curl -i http://127.0.0.1:18080/api/devtalk/sessions
curl -i http://127.0.0.1:18081/api/devlog/sessions
```

### MCP / Ollama

```bash
curl http://127.0.0.1:8000/openapi.json
curl http://127.0.0.1:11434/api/tags
```

## 체크포인트

- 실제 서버 `.env` 중복 제거 및 비밀번호 정합성 확인
- Devtalk / Devlog UI 기능 최종 검증
- 메인 Nginx 경로 전달 최종 검증
- 100개 더미 데이터 기반 MCP 통합 테스트 성공
- DevLog에서 구조화 결과 조회 성공
- MCP 프롬프트 기준으로 block granularity, blockType, status, tags 품질 재검증
## 2026-04-19 MCP Routing Debug Summary

- 100개 더미 데이터 테스트에서 `appendCount=0`, `newBlockCount=100`, `reason=fallback_conservative_new_block`가 확인됐다.
- 처음에는 프롬프트 품질 문제처럼 보였지만, 실제 원인은 fallback 경로였다.
- `/prompts/narrative_router.txt`가 컨테이너 안에서 실제로 읽히는 것도 확인했다.
- `candidateBlocks`도 정상적으로 누적됐다. 즉 candidate 입력 부재 문제는 아니었다.

직접 확인한 사실:
- Ollama direct call: 성공
- 짧은 prompt + JSON 출력: 성공
- 짧은 prompt + schema(format): 성공
- 실제 `_build_narrative_prompt(...)` 결과 + schema(format) + candidate/recent payload: timeout 발생

결론:
- 현재 "1 message = 1 block"의 직접 원인은 프롬프트 미적용이 아니라, 실제 narrative routing prompt + payload + schema 조합이 `qwen2.5:3b`에서 timeout / parse failure를 일으키는 점이다.
- `classify_narrative_block(...)`는 이 예외를 잡고 `_fallback_narrative_classification(...)`로 내려간다.
- 현재 fallback은 보수적으로 항상 `NEW_BLOCK`을 반환하므로 결과적으로 메시지 1개당 블록 1개가 된다.

권장 변경 방향:
1. 1단계는 routing 전용으로 축소
- 출력: `action`, `targetBlockId`, `score`, `reason`
- 목표: append / new 판단만 빠르고 안정적으로 수행

2. 2단계에서 metadata 생성
- `blockType`, `status`, `topic`, `summary`, `tags`
- 규칙 기반 또는 더 짧은 별도 prompt 사용

추가 권장:
- `candidateBlocks`, `recentMessages` 입력 크기를 더 줄일 것
- fallback 직전 raw LLM response / timeout 원인을 로그로 남길 것
