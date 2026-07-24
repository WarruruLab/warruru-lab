# DevTalk를 Gemini API에서 Local LLM으로 전환하며 배운 것

> 외부 API를 호출하는 채팅 앱에서, 직접 모델을 운영하고 개선하는 개발 기록 도구로 바꾸는 과정

DevTalk는 개발 중 발생하는 이슈, 판단, 해결 과정을 대화 형태로 남기기 위해 만든 서비스다.

처음에는 Gemini API를 붙여 AI 응답을 생성했다.  
외부 API를 사용하면 빠르게 기능을 만들 수 있고, 모델 품질도 안정적이다.

하지만 프로젝트를 계속 진행하다 보니 단순히 "AI 채팅 기능을 붙였다"에서 멈추고 싶지 않았다.

DevTalk의 목적은 개발 중 생기는 기록을 쌓고, 그 기록을 다시 개발 지식으로 활용하는 것이다.  
그렇다면 LLM 호출도 외부 API에만 맡기기보다는 직접 실행 환경을 만들고, 모델을 바꾸고, 컨텍스트를 조정하며 개선하는 쪽이 프로젝트 방향에 더 맞았다.

그래서 DevTalk의 LLM 실행 경로를 Gemini API 중심에서 Ollama 기반 Local LLM 중심으로 전환했다.

---

## 1. 왜 Gemini API에서 Local LLM으로 바꿨나

가장 현실적인 이유는 비용이다.

Gemini API는 편리하지만 사용량이 늘어나면 과금이 발생한다.  
DevTalk는 한두 번 질문하고 끝나는 기능이 아니다.

개발 중 계속 열어두고, 세션을 만들고, 메시지를 쌓고, 같은 주제에 대해 여러 번 이어서 대화하는 구조다.  
이런 서비스에서는 외부 API 사용량이 자연스럽게 늘어난다.

하지만 비용만이 이유는 아니었다.

더 큰 이유는 Local LLM의 성능을 직접 끌어올리는 과정을 경험하고 싶었기 때문이다.

Gemini API를 사용할 때 내가 직접 조정할 수 있는 것은 제한적이었다.

```text
prompt
temperature
max tokens
context 구성 방식
timeout
```

반면 Local LLM은 훨씬 더 많은 부분을 직접 다뤄야 한다.

```text
어떤 모델을 사용할 것인가
CPU로 돌릴 것인가 GPU로 돌릴 것인가
Docker 컨테이너가 GPU를 제대로 인식하는가
context를 얼마나 넣을 것인가
응답 속도와 품질 중 어디에 무게를 둘 것인가
stream 응답을 어떻게 처리할 것인가
이후 RAG나 fine tuning을 어떻게 붙일 것인가
```

즉, 이번 전환의 목적은 단순한 비용 절감이 아니었다.

외부 API를 소비하는 구조에서 벗어나, LLM 실행 환경 자체를 직접 운영하고 개선해보는 것이 핵심이었다.

---

## 2. 기존 DevTalk 구조

DevTalk는 처음부터 LLM provider를 어느 정도 분리해두었다.

서비스 계층은 Gemini를 직접 알지 않는다.  
대신 `LlmClient`, `LlmStreamClient` 같은 인터페이스를 통해 LLM을 호출한다.

기존 흐름은 대략 다음과 같았다.

```text
사용자 메시지 입력
-> DevTalk backend
-> LlmClient 또는 LlmStreamClient
-> Gemini API 호출
-> 응답 저장
-> frontend에서 렌더링
```

이 구조 덕분에 Local LLM으로 전환할 때 전체 서비스 계층을 갈아엎을 필요는 없었다.

핵심은 Gemini 구현체 옆에 Ollama 구현체를 추가하고, 설정값으로 어떤 provider를 사용할지 선택하게 만드는 것이었다.

```env
LLM_MODE=ollama
```

이 값 하나로 `mock`, `gemini`, `ollama`를 전환할 수 있게 만드는 것이 목표였다.

---

## 3. 실제로 바꾼 것

전환 과정에서 핵심적으로 추가한 것은 Ollama 전용 client다.

일반 응답은 `OllamaHttpClient`가 처리하고, 스트리밍 응답은 `OllamaStreamClient`가 처리하도록 구성했다.

Ollama는 `/api/chat` 엔드포인트를 사용했다.

```text
POST /api/chat
```

요청에는 모델명, 메시지 목록, stream 여부, generation option을 담는다.

DevTalk에서는 env를 통해 Ollama 설정을 관리하도록 했다.

```env
LLM_MODE=ollama
LLM_OLLAMA_BASE_URL=http://ollama:11434
LLM_OLLAMA_MODEL=qwen2.5:3b
LLM_OLLAMA_CONNECT_TIMEOUT_MS=3000
LLM_OLLAMA_READ_TIMEOUT_MS=60000
LLM_OLLAMA_STREAM_RESPONSE_TIMEOUT_MS=120000
```

여기서 중요한 점은 `LLM_OLLAMA_BASE_URL`이다.

DevTalk backend는 Docker 컨테이너 안에서 실행된다.  
따라서 Ollama도 같은 Docker network에 있다면 `localhost`가 아니라 컨테이너 이름을 써야 한다.

```env
LLM_OLLAMA_BASE_URL=http://ollama:11434
```

브라우저에서 접근하는 API 경로와 컨테이너 내부 통신 주소를 구분하는 것도 중요했다.

브라우저 기준 API 경로는 상대 경로를 유지했다.

```env
VITE_API_BASE_URL=/devtalk/api/devtalk
```

프론트 nginx는 이 요청을 내부 백엔드로 proxy한다.

```text
브라우저
-> https://warurulab.site/devtalk/api/devtalk/...
-> devtalk-frontend nginx
-> http://devtalk-backend:8080
```

CORS는 Docker service name이 아니라 브라우저 Origin 기준으로 설정해야 했다.

```env
CORS_ALLOWED_ORIGINS=https://warurulab.site
```

이 부분을 정리하면서 값의 기준을 명확히 나누게 되었다.

| 구분 | 사용해야 하는 값 |
| --- | --- |
| 브라우저 Origin | `https://warurulab.site` |
| 프론트 API base URL | `/devtalk/api/devtalk` |
| 프론트 nginx -> 백엔드 | `http://devtalk-backend:8080` |
| 백엔드 -> Ollama | `http://ollama:11434` |
| 백엔드 -> MySQL | `jdbc:mysql://devtalk-db:3306/devtalk` |

이 구분이 흐려지면 CORS, 403, 500, DB 연결 실패가 한꺼번에 섞여 보인다.

---

## 4. 모델 테스트 중 가장 먼저 만난 문제

Local LLM 전환 후 여러 모델을 테스트했다.

처음에는 큰 모델을 쓰면 답변 품질이 좋아질 것이라고 기대했다.  
하지만 실제 서버에서 돌려보니 응답이 너무 느렸다.

처음에는 단순히 모델 선택 문제라고 생각했다.

하지만 원인을 확인해보니 더 근본적인 문제가 있었다.

Ollama 컨테이너가 GPU를 사용하지 못하고 있었다.

즉, 모델은 Docker 컨테이너 안에서 실행되고 있었지만 실제 추론은 CPU only로 돌고 있었다.

문제 흐름을 정리하면 다음과 같다.

```text
Ollama 컨테이너 실행
-> 모델 요청
-> GPU 미사용
-> CPU only 추론
-> 응답 지연 증가
-> DevTalk 사용성 저하
```

Local LLM에서 GPU 사용 여부는 체감 성능에 큰 영향을 준다.

컨테이너가 GPU를 제대로 인식하도록 설정을 점검한 뒤, 응답 속도가 개선되는 것을 확인했다.

이번 경험을 통해 Local LLM 운영은 모델만 고르는 일이 아니라는 것을 배웠다.

```text
모델 선택
Docker 실행 환경
GPU runtime
컨테이너 네트워크
timeout
stream 처리
context 크기
```

이 요소들이 모두 같이 맞아야 실제 서비스에서 사용할 수 있다.

---

## 5. 왜 qwen2.5:3b를 선택했나

최종적으로 DevTalk에는 `qwen2.5:3b`를 선택했다.

이유는 빠른 응답이 더 중요했기 때문이다.

DevTalk는 긴 보고서를 생성하는 서비스가 아니다.  
개발 중 생기는 생각과 문제를 빠르게 기록하고, 이어서 대화하는 도구에 가깝다.

사용자가 질문을 입력했는데 매번 수십 초씩 기다려야 한다면 흐름이 끊긴다.

그래서 모델 선택 기준을 다음처럼 잡았다.

```text
응답이 빠를 것
stream 출력이 자연스러울 것
반복 호출 부담이 적을 것
서버 자원 안에서 안정적으로 돌 것
```

큰 모델은 더 좋은 답변을 줄 가능성이 있다.  
하지만 현재 DevTalk의 목적에서는 빠른 응답성과 안정성이 더 중요했다.

그래서 우선은 가볍고 빠른 모델을 선택했다.

```env
LLM_OLLAMA_MODEL=qwen2.5:3b
```

물론 이것이 최종 답은 아니다.

서버 자원이 충분해지거나 DevTalk의 사용 방식이 바뀌면 더 큰 모델을 다시 테스트할 수 있다.  
Local LLM의 장점은 이처럼 모델을 바꿔가며 직접 비교할 수 있다는 점이다.

---

## 6. 컨텍스트 유지도 직접 조정해야 했다

Local LLM으로 바꾸면서 컨텍스트 전략도 다시 봐야 했다.

외부 API를 사용할 때는 큰 context window와 안정적인 추론 성능에 기대는 부분이 있었다.  
하지만 Local LLM에서는 무작정 많은 메시지를 넣으면 응답이 느려지고 품질도 흔들릴 수 있다.

DevTalk에서는 최근 메시지 tail과 요약 정보를 조합해 직접 컨텍스트를 구성하는 방향을 사용했다.

이 값들도 운영 중 조정할 수 있도록 env로 분리했다.

```env
LLM_CONTEXT_TAIL_MAX_MESSAGES=20
LLM_CONTEXT_TAIL_MAX_CHARS=16000
LLM_CONTEXT_SUMMARY_PROMPT_MAX_CHARS=3000
LLM_CONTEXT_SUMMARY_HARD_MAX_CHARS=4000
LLM_CONTEXT_SUMMARY_KEEP_TAIL_MESSAGES=16
LLM_CONTINUE_MAX_ROUNDS=2
LLM_CONTINUE_ANCHOR_CHARS=300
```

처음에는 더 보수적인 값으로 시작했다.

하지만 실제 대화 흐름을 유지하려면 6000자 정도는 짧다고 판단했다.  
DevTalk의 목적이 대화 맥락을 유지하며 개발 기록을 쌓는 것이기 때문에, 최근 흐름은 어느 정도 넉넉히 유지해야 한다.

다만 이 값에도 정답은 없다.

서버가 버거우면 줄여야 하고, 대화 맥락이 부족하면 늘려야 한다.  
Local LLM 운영은 이런 값을 계속 조정하는 과정에 가깝다.

---

## 7. 전환하면서 겪은 운영 이슈

Local LLM 전환 과정에서 LLM 자체보다 주변 설정에서 더 많은 문제가 생겼다.

대표적으로 CORS와 DB 연결 문제가 있었다.

처음에는 운영 도메인에서 세션 생성 요청이 403으로 실패했다.

```text
POST https://warurulab.site/devtalk/api/devtalk/sessions
-> 403 Forbidden
```

원인은 CORS였다.

서버의 허용 Origin이 `localhost`로 되어 있었고, 실제 브라우저 Origin인 `https://warurulab.site`가 허용되어 있지 않았다.

해결은 단순했다.

```env
CORS_ALLOWED_ORIGINS=https://warurulab.site
```

그 다음에는 500 오류가 발생했다.

로그를 확인해보니 DB 계정 인증 문제였다.

```text
Access denied for user 'devtalk_app'@'172.24.0.3'
```

원인은 MySQL Docker volume과 env 값의 불일치였다.

MySQL 공식 이미지는 `MYSQL_USER`, `MYSQL_PASSWORD`를 최초 볼륨 생성 시점에만 적용한다.  
이미 생성된 volume이 있으면 `.env` 값을 바꿔도 기존 DB 계정 비밀번호는 자동으로 바뀌지 않는다.

즉, 현재 `.env`의 비밀번호와 기존 MySQL volume 안에 저장된 비밀번호가 달라진 것이다.

이 문제는 두 가지 방식으로 해결할 수 있다.

데이터를 날려도 되는 개발 환경이라면 volume을 삭제하고 다시 초기화한다.

```bash
docker compose down
docker volume rm devtalk_devtalk_db_data
docker compose up -d --build
```

데이터를 유지해야 한다면 MySQL에 root로 접속해 계정 비밀번호를 맞춘다.

```sql
ALTER USER 'devtalk_app'@'%' IDENTIFIED BY '현재_env의_MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON devtalk.* TO 'devtalk_app'@'%';
FLUSH PRIVILEGES;
```

이 경험을 통해 Docker 기반 서비스에서는 `.env`만 보는 것으로 충분하지 않다는 것을 다시 확인했다.

컨테이너 env, DB volume, 네트워크, 실제 런타임 상태를 같이 봐야 한다.

---

## 8. 이번 전환에서 배운 점

이번 작업에서 가장 크게 느낀 점은 Local LLM 전환이 단순한 provider 교체가 아니라는 것이다.

코드만 보면 Gemini client 옆에 Ollama client를 추가하면 끝나는 것처럼 보인다.

하지만 실제 운영에서는 더 많은 요소가 같이 움직인다.

```text
LLM provider 선택
모델 크기 선택
GPU 연결 여부
Docker network 이름
CORS Origin
DB 계정과 volume 상태
stream timeout
context window
프론트 API 경로
```

특히 다음 구분이 중요했다.

| 상황 | 값의 기준 |
| --- | --- |
| 브라우저가 접근하는 주소 | 도메인 또는 상대 경로 |
| 컨테이너가 컨테이너를 호출하는 주소 | Docker service name |
| CORS 허용 Origin | 브라우저 Origin |
| MySQL 계정 정보 | 최초 volume 생성 시점의 값 |

Local LLM은 외부 API보다 더 많은 책임을 가져온다.

하지만 그만큼 직접 개선할 수 있는 영역도 넓어진다.

---

## 9. 앞으로 무엇을 할 것인가

Local LLM으로 전환했다고 끝난 것은 아니다.  
오히려 이제부터가 시작이다.

앞으로는 Local LLM의 성능을 끌어올리는 방법을 더 공부하고 프로젝트에 적용해볼 생각이다.

우선 가장 관심 있는 방향은 RAG다.

DevTalk에는 앞으로 다음과 같은 기록이 쌓인다.

```text
개발 중 발생한 이슈
해결 과정
실패 로그
ADR
troubleshooting 문서
코드 변경 이유
CS 개념 정리
프레임워크 사용 경험
```

이 자료들을 vector store에 넣고, 질문 시 관련 기록을 검색해 Local LLM context로 넣으면 DevTalk는 단순한 채팅 앱이 아니라 개발 지식 저장소에 가까워진다.

Fine tuning도 언젠가는 실험해보고 싶다.  
다만 지금 단계에서는 RAG가 더 현실적이라고 본다.

이미 프로젝트 안에는 기록이 쌓이고 있고, 그 기록을 검색해 다시 활용하는 방식이 DevTalk의 목적과 더 잘 맞기 때문이다.

---

## 10. DevTalk의 방향

요즘 실제 개발을 할 때 웹 AI를 직접 켜서 긴 대화를 이어가는 경우는 줄었다.

코드 작업 자체는 Claude Code, Codex 같은 도구를 더 자주 사용한다.  
그렇다면 DevTalk가 단순히 웹 AI 채팅 앱이 되는 것은 큰 의미가 없다.

DevTalk의 방향은 조금 다르게 잡고 있다.

DevTalk는 AI에게 바로 정답을 받는 도구라기보다, 내가 개발하면서 겪은 문제와 해결 과정을 기록하고, 그 기록을 다시 지식으로 바꾸는 도구가 되어야 한다.

목표 흐름은 다음과 같다.

```text
개발 중 발생하는 이슈 기록
-> 해결 과정 기록
-> DevLog와 MCP를 통해 구조화
-> CS, 프레임워크, 프로젝트 지식으로 축적
-> RAG로 다시 검색하고 활용
```

이렇게 보면 Local LLM 전환은 단순한 비용 절감이 아니다.

내가 만든 개발 기록을 내가 운영하는 모델과 검색 구조로 다시 활용하기 위한 첫 단계다.

---

## 마무리

Gemini API에서 Local LLM으로 바꾸는 과정은 생각보다 많은 것을 건드렸다.

처음에는 API provider만 바꾸면 될 것 같았다.

하지만 실제로는 Docker network, CORS, DB env, GPU 연결, 모델 선택, context 관리까지 모두 함께 봐야 했다.

이번 전환으로 DevTalk는 외부 API에만 의존하는 구조에서 조금 벗어났다.

아직 모델 품질과 응답 속도는 계속 개선해야 한다.  
하지만 적어도 직접 실험하고 개선할 수 있는 구조가 생겼다.

다음 목표는 이 Local LLM을 더 똑똑하게 만드는 것이다.

RAG를 붙이고, 기록을 검색 가능하게 만들고, 개발 중 쌓인 이슈를 다시 학습 자료처럼 활용하는 방향으로 DevTalk를 발전시켜볼 생각이다.

