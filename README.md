# 와르르랩(WarruruLab)
![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Purpose](https://img.shields.io/badge/purpose-learning%20%26%20portfolio-blueviolet)

> 문제를 해결하는 프로젝트가 아니라,  
> **문제를 해결한 판단 과정을 자산으로 남기는 프로젝트**

AI와의 디버깅 대화는 빠르게 쌓이지만, 시간이 지나면 어떤 문제가 있었는지, 어떤 시도가 왜 실패했는지, 최종 해결의 근거는 무엇이었는지가 쉽게 사라집니다. WarruruLab은 이 판단 과정을 구조화해 기록하고, 기술 블로그 자산으로 남기기 위한 프로젝트입니다.

---

## 핵심 개념

- **문제 하나 = 세션 하나** — 로그인 세션이 아닌, 하나의 문제 해결 단위
- 해결 여부는 자동이 아닌 **본인이 직접 확정 (`Resolved`)**
- 성공한 해결뿐 아니라 **실패한 시도와 그 원인까지 모두 기록**
- 판단의 근거가 가장 중요한 가치

---

## 프로젝트 구성

WarruruLab은 세 개의 서비스로 구성됩니다.

### 개발톡 (DevTalk)
실제 개발 과정에서 사용하는 AI 채팅 기반 문제 해결 기록 웹입니다.

- Gemini API를 직접 연동해 채팅 서비스 구현
- 질문, 응답, 코드, 에러 로그, 실패한 시도를 백엔드에 저장
- 문제가 실제로 해결되었을 때만 사용자가 직접 `Resolved` 처리

→ 문제 해결 과정의 **원본 기록 저장소**

### MCP Server
DevTalk 메시지를 DevLog에서 사용할 수 있는 블록 구조로 재구성하는 분석 서버입니다.

- DevLog가 메시지 목록을 보내면, 의미상 이어지는 메시지들을 하나의 블록으로 묶어 반환
- 각 블록에 `CONTEXT · PROBLEM · TRIAL · SOLUTION · INSIGHT` 태그와 코드 조각을 붙여 구조화
- 블록 경계 결정은 시간 간격·단어 겹침 비율 기반 규칙으로 먼저 판단하고, 애매한 경우만 로컬 LLM(Ollama)에 위임
- Python · FastAPI로 구현 — 설계는 직접, 코드 작성은 AI에게 위임하는 방식으로 개발

→ 대화 로그를 **DevLog가 활용할 수 있는 구조**로 변환하는 서비스

### 개발로그 (DevLog)
DevTalk에 쌓인 로그를 분석해 문제 해결의 전체 사고 흐름을 정리합니다.

- 어떤 문제가 있었는지, 어떤 시도를 했고 왜 실패했는지, 해결 방법과 그 근거를 정리
- 트러블슈팅 블로그 초안을 두 가지 유형으로 작성
  - **Resolved 기반 트러블슈팅 글**: 최종 해결이 명확한 문제
  - **의미 있는 실패 분석 글**: 해결에 이르지 못했으나 학습 가치가 있는 문제
- 로그를 블로그 초안으로 작성할지는 사람이 직접 판단

→ 흩어진 로그를 **검증된 개발 자산**으로 전환하는 서비스

---

## 전체 흐름

```
1. 개발 중 문제 발생 → DevTalk에서 AI에게 질문
2. 질문 / 응답 / 코드 / 에러 로그 자동 기록
3. 해결책 직접 적용
4. 실제로 해결되면 Resolved 버튼으로 확정
5. DevLog가 DevTalk에서 메시지를 가져와 MCP Server에 전달해 블록 구조로 분석
6. 블록 기반으로 트러블슈팅 블로그 초안 생성
```

- DevTalk: 기록 + 해결 확정
- MCP Server: 메시지 → 블록 구조 변환
- DevLog: 분석 + 자산화

---

## 기술 스택

![Java](https://img.shields.io/badge/Java-21-orange)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-4.0.1-brightgreen)
![React](https://img.shields.io/badge/React-19.2.1-blue)
![MySQL](https://img.shields.io/badge/MySQL-8.4.7-blue)
![Docker](https://img.shields.io/badge/Docker-29.x-blue)

| 기술 | 선택 이유 |
|:---|:---|
| Java 21 | 클래스와 메서드의 책임을 분리하며 유지보수 가능한 구조를 직접 설계하기 위해 선택 |
| React 19.2.1 | 사용성을 확인하기 위한 프론트엔드 도구, UI 초안은 AI를 활용해 빠르게 구성 |
| Spring Boot 4.0.1 | Controller · Service · Domain · Infra 계층으로 나눠 요청 흐름을 구조적으로 관리하기 위해 선택 |
| MCP | 단순 API 호출이 아니라 대화 맥락을 세션 단위로 이어가며 구조화 데이터로 전환하는 데 적합하다고 판단 |
| MySQL 8.4.7 | 세션·메시지·분석 결과처럼 서로 연결되는 데이터를 관계형 구조로 설계하기 위해 선택 |
| Docker · Nginx | 자동화 도구 없이 컨테이너 구성과 리버스 프록시 설정을 직접 구성하며 배포 흐름을 이해하기 위해 선택 |
| Git / GitHub | 코드 저장소를 넘어 변경 이력·문서·결정 근거를 함께 관리하는 도구로 활용 |

**ORM 전략**: 초기에는 JDBC로 SQL을 직접 작성해 트랜잭션 흐름을 이해한 뒤, 이후 JPA로 전환해 두 방식을 직접 비교할 예정입니다.

---

## 이 프로젝트를 통해 보여주고 싶은 것

- 문제를 마주했을 때의 사고 과정
- AI를 보조 도구로 활용하되, 설계 판단과 결과 검증은 직접 수행하는 태도
- 기록을 통해 스스로를 개선하는 개발 방식
- 실제 운영을 고려한 구조와 판단

백엔드 개발자로서 이 프로젝트의 핵심은 서버 구조와 기록 설계입니다. 프론트엔드는 사용성을 확인하기 위한 도구로, UI 초안은 AI를 활용해 빠르게 구성하고 실제 사용 과정에서 필요한 부분만 직접 수정했습니다.

---

## Links

- **기술 블로그**: https://woo-dang-dang-tang-study.tistory.com/90
- **개발톡 Repository**: https://github.com/WarruruLab/DevTalk
- **개발로그 Repository**: https://github.com/WarruruLab/DevLog
- **MCP Server Repository**: https://github.com/WarruruLab/MCPServer
