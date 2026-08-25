# 커밋 컨벤션

## 형식

```
<type>(<scope>) : <제목>

<본문 — 선택>

<꼬리말 — 선택>
```

예시:

```
feat(webview) : 코스 상세 화면 신뢰도 배지 추가
fix(backend) : REQUIRED 조건이 점수 계산 전에 필터링되지 않던 문제 수정
docs(planning) : 태그전략 정본 표기 추가
chore(repo) : 모노레포 폴더 골격 추가
```

> `type`과 `:` 사이에 **공백을 넣는다** (`feat(webview) : ...`).
> 기존 히스토리(`ci : discord pr알림 ci 설정`)와 맞춘 팀 규칙이다.
> 참고로 Conventional Commits 표준은 공백이 없는 `feat(webview): ...`이므로,
> 나중에 commitlint·semantic-release 같은 도구를 붙이면 파서 설정을 조정해야 한다.

---

## 제목 규칙

**제목은 한글로 쓴다.** 단, **기술 용어까지 억지로 번역하지 않는다.**

| | |
|---|---|
| ✅ | `feat(api-client) : 페이지네이션 cursor 파라미터 지원` |
| ✅ | `refactor(contracts) : 배럴에서 export * 제거` |
| ✅ | `fix(webview) : zustand store 초기화 시점 오류 수정` |
| ❌ | `feat(api-client) : add cursor pagination support` — 제목 전체가 영어 |
| ❌ | `refactor(contracts) : 통짜내보내기 제거` — 용어를 억지 번역 |

그대로 쓰는 용어: `OpenAPI` · `codegen` · `barrel` · `store` · `hook` · `Node`/`Edge` ·
`REQUIRED`/`PREFERRED`/`EXCLUDED` · 코드 식별자(`rankCourses`, `PurposeId`) · 파일/패키지명.

기타:

- 마침표로 끝내지 않는다
- 명사형 종결(`~ 추가`, `~ 수정`, `~ 제거`)을 기본으로 한다
- 50자 내외로 유지한다
- **무엇을** 바꿨는지 쓴다. **왜**는 본문에 쓴다

---

## type

| type | 쓰임 |
|---|---|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변화 없는 구조 개선 |
| `perf` | 성능 개선 |
| `docs` | 문서만 변경 |
| `style` | 포맷·세미콜론 등 동작 무관 변경 |
| `test` | 테스트 추가·수정 |
| `build` | 빌드 설정·의존성 (pnpm, Gradle, Vite) |
| `ci` | CI 워크플로 |
| `chore` | 그 외 잡무 (폴더 정리, gitignore 등) |

---

## scope

바꾼 곳을 가리킨다. 여러 곳이면 **가장 핵심인 하나**를 쓰고, 전역이면 `repo`를 쓴다.

| scope | 대상 |
|---|---|
| `webview` `admin` `native-shell` | `frontend/*` |
| `contracts` `api-client` `tags` `tokens` `utils` `native-bridge` `config` | `packages/*` |
| `backend` | Spring Boot |
| `api-spec` | OpenAPI 스펙 |
| `planning` | `docs/planning/` 기획 정본 |
| `docs` | 그 외 문서 (`monorepo-strategy`, 이 문서 등) |
| `infra` | docker-compose · 배포 |
| `ci` | `.github/workflows` (type이 `ci`면 scope 생략 가능) |
| `harness` | `../AGENTS.md` · `../CLAUDE.md` |
| `repo` | 루트 설정 · 여러 영역 동시 변경 |

---

## 본문

**왜** 바꿨는지, 그리고 리뷰어가 놓칠 만한 맥락을 쓴다. 사소한 변경은 생략해도 된다.

```
fix(backend) : problem 태그가 EXCLUDED 필터를 통과하던 문제 수정

problem은 점수가 아니라 구조화된 상태값이라 기존 필터가
숫자 비교로만 처리해 항상 통과하고 있었다.
태그전략 §1.4에 따라 상태값 분기를 추가한다.
```

## 꼬리말

```
BREAKING CHANGE: contracts 배럴에서 Course 재수출 경로 변경
Closes #12
```

공유 패키지의 **공개 타입 변경**은 두 앱을 동시에 깨뜨릴 수 있으므로
`BREAKING CHANGE`를 반드시 표기한다.

---

## 커밋 단위

- **하나의 커밋은 하나의 관심사.** 리팩터링과 기능 추가를 섞지 않는다
- Backend DTO를 바꾼 커밋은 `api-spec/openapi.yaml` 재생성까지 **같은 커밋에 포함**한다.
  프론트 codegen 명령과 생성 타입은 프론트가 소유하며 검토된 YAML을 입력으로 사용한다.
- 새 결정이 나온 커밋은 `../AGENTS.md`의 「확정된 결정」/「열린 영역」도 **같이** 갱신한다

## 브랜치

```
feat/<간단한-설명>      기능
fix/<간단한-설명>       수정
chore/<간단한-설명>     잡무
docs/<간단한-설명>      문서
```

브랜치명은 영문 소문자 + 하이픈을 쓴다. `main`에 직접 커밋하지 않고 PR로 병합한다.
