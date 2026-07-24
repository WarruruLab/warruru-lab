# [와르르랩] MCP 개발로그: 프롬프트 문제가 아니었다

DevTalk 메시지를 DevLog에서 사용할 **narrative block**으로 구조화하는 테스트를 진행하던 중, 이상한 패턴이 반복됐다.

```text
appendCount = 0
newBlockCount = 100
finalBlockCount = 100
```

메시지 100개를 입력하면 블록도 100개가 생성됐다.  
즉, 여러 메시지를 하나의 개발 흐름으로 묶는 것이 아니라 **모든 메시지가 각각 독립 블록으로 분리**되고 있었다.

처음에는 프롬프트 문제라고 판단했다.  
하지만 실제 원인은 프롬프트 문장 자체가 아니라, **프롬프트 로딩 경로, 모델 호출 timeout, CPU only 실행 환경, fallback 정책**이 겹친 구조적인 문제였다.

---

## 문제 상황

MCP의 narrative routing은 DevTalk 메시지를 DevLog에서 사용할 수 있는 단위로 묶는 역할을 한다.

예를 들어 하나의 로그인 오류를 추적하는 과정이라면 다음 메시지들은 하나의 흐름으로 묶이는 것이 자연스럽다.

```text
문제 발견
원인 가설
mapper 확인
null 방어 추가
DB row 확인
가입 로직 수정
정상 동작 확인
```

이 흐름은 각각 별개의 글감이라기보다, 하나의 이슈가 해결되어 가는 과정이다.  
따라서 기대한 동작은 기존 블록에 메시지를 이어 붙이는 `APPEND`였다.

하지만 실제 결과는 항상 `NEW_BLOCK`이었다.

```text
APPEND    0
NEW_BLOCK 100
```

---

## 첫 번째 가설: 프롬프트가 약한가?

처음에는 모델이 `APPEND`를 선택하도록 충분히 유도하지 못했다고 생각했다.

그래서 프롬프트를 여러 방식으로 수정했다.

- 같은 이슈 흐름은 하나의 블록으로 묶으라는 규칙 추가
- `APPEND` 우선 전략 추가
- `If uncertain, choose APPEND` 문장 추가
- qwen2.5:3b용으로 짧고 단순한 프롬프트 작성
- 예시를 줄이고 판단 기준을 단순화

하지만 결과는 바뀌지 않았다.

프롬프트를 바꿔도 결과 패턴이 지나치게 동일했다.  
이 시점부터 문제를 다르게 보기 시작했다.

> 프롬프트가 나쁜 것이 아니라, 애초에 수정한 프롬프트가 적용되고 있지 않은 것은 아닐까?

---

## 원인 1: 프롬프트 파일이 실제로 적용되지 않았다

Docker 환경에서 MCP는 프롬프트를 환경변수로 주입받도록 되어 있었다.

프롬프트 로딩 우선순위는 다음과 같았다.

```text
1. MCP_NARRATIVE_PROMPT_FILE
2. MCP_NARRATIVE_PROMPT_TEMPLATE
3. 코드 기본 프롬프트
```

컨테이너 내부를 확인해보니 환경변수는 다음 경로를 가리키고 있었다.

```text
/prompts/narrative_router.txt
```

하지만 실제 mount된 파일은 다음 파일뿐이었다.

```text
narrative_router.example.txt
```

정리하면 다음 상태였다.

```text
환경변수 설정      O
Docker mount      O
파일명 일치        X
프롬프트 로딩      X
기본 프롬프트 사용 O
```

즉, 한동안은 프롬프트를 수정했다고 생각했지만 실제 실행 환경에서는 수정한 프롬프트가 사용되지 않았다.

파일명을 맞추고 컨테이너 내부에서 프롬프트 내용까지 확인한 뒤에야, 프롬프트 반영 여부를 신뢰할 수 있었다.

---

## 원인 2: 프롬프트 적용 후에도 fallback이 실행되고 있었다

프롬프트 파일 경로를 수정한 뒤에도 결과는 여전히 같았다.

```text
appendCount = 0
reason = fallback_conservative_new_block
```

여기서 중요한 단서가 나왔다.

문제는 모델이 `APPEND` 대신 `NEW_BLOCK`을 선택한 것이 아니었다.  
**모델 호출이 실패했고, 예외 처리로 fallback 로직이 실행되고 있었다.**

현재 fallback 정책은 보수적으로 동작한다.

```text
classification 실패 -> fallback 실행 -> NEW_BLOCK 반환
```

따라서 겉으로는 모델이 계속 `NEW_BLOCK`을 선택하는 것처럼 보였지만, 실제로는 모델 판단 결과가 아니라 fallback 결과였다.

---

## 원인 3: narrative routing 요청이 너무 무거웠다

MCP 컨테이너 내부에서 Ollama direct call을 테스트해보니 차이가 명확했다.

```text
짧은 prompt + JSON 출력
-> 성공

짧은 prompt + schema(format)
-> 성공

실제 narrative routing prompt + candidateBlocks + recentMessages + schema
-> timeout
```

qwen2.5:3b가 JSON 출력 자체를 못 하는 것은 아니었다.  
문제는 실제 narrative routing 요청이 너무 많은 일을 한 번에 요구한다는 점이었다.

당시 라우팅 단계는 다음 정보를 한 번에 생성하려고 했다.

```text
APPEND / NEW_BLOCK 판단
targetBlockId 선택
blockType 생성
status 생성
topic 생성
summary 생성
tags 생성
```

이 요청은 단순한 라우팅이 아니라, 라우팅과 메타데이터 생성을 동시에 수행하는 작업에 가까웠다.

작은 로컬 모델 입장에서는 입력도 길고 출력 요구사항도 많았다.  
그 결과 실제 호출이 timeout으로 이어졌다.

---

## 원인 4: GPU가 아니라 CPU only로 실행되고 있었다

성능 문제도 있었다.

블록 구조화가 지나치게 느렸고, 확인해보니 모델이 GPU가 아니라 **CPU only**로 실행되고 있었다.

즉 실제 실행 조건은 다음과 같았다.

```text
긴 narrative routing prompt
많은 candidateBlocks
recentMessages 포함
schema 강제 출력
여러 메타데이터 동시 생성
CPU only 추론
```

이 조합에서는 응답 시간이 길어질 수밖에 없다.

결국 긴 요청이 CPU에서 느리게 처리되다가 timeout이 발생했고, timeout 이후 fallback이 실행되면서 항상 `NEW_BLOCK`이 반환됐다.

최종 흐름은 다음과 같다.

```text
메시지 입력
-> narrative routing 호출
-> 요청이 너무 무거움
-> CPU only 환경에서 처리 지연
-> timeout
-> fallback 실행
-> NEW_BLOCK 반환
-> 1 message = 1 block
```

---

## 최종 원인 정리

이번 문제는 단일 원인이라기보다 여러 조건이 겹친 결과였다.

| 구분 | 내용 | 결과 |
| --- | --- | --- |
| 프롬프트 로딩 | 파일명이 달라 수정한 프롬프트가 적용되지 않음 | 기본 프롬프트로 실행 |
| 모델 호출 | 실제 routing prompt가 너무 무거움 | timeout 발생 |
| 실행 환경 | GPU가 아닌 CPU only 추론 | 응답 지연 증가 |
| fallback 정책 | 실패 시 보수적으로 `NEW_BLOCK` 반환 | 모든 메시지가 새 블록으로 생성 |

따라서 문제를 한 문장으로 정리하면 다음과 같다.

> 프롬프트가 약해서 `APPEND`를 못 고른 것이 아니라, 무거운 routing 호출이 CPU only 환경에서 timeout되고 fallback이 `NEW_BLOCK`을 반환하고 있었다.

---

## 개선 방향

해결 방향은 프롬프트를 더 길게 쓰는 것이 아니다.  
작은 로컬 모델이 안정적으로 처리할 수 있도록 작업을 분리해야 한다.

### 1단계: 라우팅 전용

첫 번째 단계에서는 오직 라우팅만 판단한다.

```json
{
  "action": "APPEND",
  "targetBlockId": "block-123",
  "score": 0.82,
  "reason": "same issue flow"
}
```

이 단계에서 필요한 것은 다음 네 가지뿐이다.

- `APPEND` 또는 `NEW_BLOCK`
- `targetBlockId`
- `score`
- `reason`

즉, "붙일지 새로 만들지"만 판단한다.

### 2단계: 메타데이터 생성

라우팅이 끝난 뒤 별도 단계에서 메타데이터를 생성한다.

```text
blockType
status
topic
summary
tags
```

이 값들은 규칙 기반으로 생성할 수도 있고, 필요하다면 더 짧은 별도 프롬프트로 분리할 수도 있다.

핵심은 하나다.

> 라우팅 판단과 메타데이터 생성을 한 번에 처리하지 않는다.

---

## 마무리

이번 디버깅에서 얻은 결론은 명확하다.

프롬프트 품질 문제처럼 보이는 현상도 실제로는 호출 구조, 실행 환경, fallback 정책의 문제일 수 있다.

특히 작은 로컬 모델을 사용할 때는 다음 기준이 중요하다.

- 한 번에 너무 많은 판단을 시키지 않는다.
- routing과 metadata 생성을 분리한다.
- timeout과 fallback 로그를 반드시 확인한다.
- GPU 사용 여부를 먼저 확인한다.
- fallback 결과를 모델 판단 결과로 착각하지 않는다.

다음 단계에서는 MCP의 narrative routing을 더 가볍게 만들기 위해, **라우팅 전용 1단계 구조**로 분리하는 작업을 진행할 예정이다.
