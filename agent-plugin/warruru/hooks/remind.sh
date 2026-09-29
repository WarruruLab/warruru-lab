#!/bin/sh
# 매 턴 앞에 기록 규칙 네 줄을 끼워 넣는다.
#
# 왜 훅인가 — 스킬은 모델이 "관련 있다" 고 판단할 때 로드된다. 다른 프로젝트를
# 만지는 긴 대화에서는 그 판단이 매번 서지 않아서, 기록할 순간을 지나친다.
# 실제로 그랬다(2026-09-02 확인: spool 0건 · dead-letter 0건 — 유실이 아니라
# 애초에 안 불렀다).
#
# **판단은 여전히 모델이 한다.** 이 훅은 규칙을 눈앞에 두기만 하고 아무것도
# 강제하지 않는다. 훅이 실패해도 stdout 이 비어 대화는 그대로 흘러간다.
LOG="$HOME/.warruru/logs/hook.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null
printf '%s UserPromptSubmit\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG" 2>/dev/null

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"[warruru] 기록할 순간이면 그 자리에서 record_learning 을 부른다. 물어보지 말고. 넷 중 하나면 해당한다 — 수치가 달라졌다(EXPERIMENT, 전후 값 둘 다) · 고장났다 고쳤다(TROUBLESHOOTING, 증상·원인·조치) · 여러 후보 중 골랐다(TECH_CHOICE, 버린 것과 이유) · CS 개념을 이해했다(CONCEPT). topic 은 영문 슬러그로, rationale/limitation 은 모르면 비우고 그 자리에서 되묻는다."}}
JSON
