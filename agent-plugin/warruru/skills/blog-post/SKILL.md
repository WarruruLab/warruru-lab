---
name: blog-post
description: Turn Warruru learning records into a publishable blog post — polish an assembled draft, fill what is missing by asking rather than inventing, and get it to the publish step. Use when the user says 블로그 글 써줘, 초안 다듬어줘, polish topic=… draft=…, 글로 만들자, 발행하자, or asks about the draft's TODO sections.
---

# 블로그 글

**초안은 이미 만들어져 있다.** 6단 마크다운(문제 → 선택 → 구현 → 측정 →
결과 → 한계)은 데몬이 기록에서 결정적으로 조립한다. **LLM 호출은 0 이다.**

그러니 이 스킬이 하는 일은 글을 쓰는 것이 아니라 **다듬는 것**이다.
재료가 없으면 만들지 말고 `warruru-recording` 으로 돌아가 기록을 보강한다.

## 다듬는 절차

초안 화면(`http://127.0.0.1:8787/drafts/{id}`)이 한 줄을 준다.

```
polish topic=db-index draft=drf_01ABC...
```

1. `get_topic_records` 로 그 주제의 기록을 **전부** 읽는다.
2. 여섯 절을 채운 글을 만든다.
3. `save_draft` 로 **같은 `draft_id` 에 덮어쓴다.** 새로 만들지 않는다.
4. 응답의 `missing_summary` 를 읽는다. 비어 있는 필드를 알려 준다.

터미널에서 구독 요금제로 한 번에 돌릴 수도 있다:

```
local/scripts/polish.command db-index drf_01ABC...
```

## 지어내지 않는 것이 이 스킬의 전부다

초안의 `TODO:` 는 **면접에서 대답 못 할 자리**를 정확히 가리킨다.
그럴듯한 문장으로 덮으면 그 자리가 사라지고, 사라진 채로 면접장에 간다.

- `limitation` 과 `rationale` 은 사용자 머릿속에만 있다. **되물어라** —
  "풀 크기를 30 이상으로 못 올린 이유가 무엇이었나요?"
- 답을 받으면 `record_learning` 에 **응답에 실려 온 `record_id` 를 넘겨**
  기록을 먼저 채우고, 초안을 다시 만든다. 글에만 적으면 다음 글에서 또 없다.
- 수치는 기록에 있는 값만 쓴다. "약 3배" 를 "320ms → 90ms" 로 바꾸지 않는다.

## 착지점

초안은 `~/.warruru/drafts/YYYY/MM/` 에 앉는다. **저장소 바깥이다.**
저장소 안 경로를 넘기면 쓰기 어댑터가 예외를 던진다 — 취향이 아니라
사고 방지 장치다. origin 이 public 일 수 있다.

발행 경로는 셋이다. `MarkdownFileTarget` · `TistoryClipboardTarget` ·
`GitPrivateRepoTarget`.

**티스토리 자동 발행은 접었다(2026-08-28).** 약관 때문이 아니라 캡차 때문이다 —
`DKAPTCHA` 가 발행마다 떠서 사람이 푸는 편이 붙여넣기보다 느리다.
**우회하지 마라.** 클립보드용 HTML 을 만들어 주고 게시는 사람이 한다.

## 하지 않는 것

- 기록이 없는 주제로 글을 만들지 않는다. 그건 글이 아니라 창작이다.
- `blog/` 디렉터리는 사람이 "공개해도 된다" 고 판단한 글만 들어간다.
  에이전트가 거기 쓰지 않는다.
- 기록을 남기는 규칙은 `warruru-recording` 이 정한다. 여기서 다시 정하지 않는다.
