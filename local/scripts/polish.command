#!/bin/sh
# 초안 다듬기 — 초안 화면이 준 한 줄을 **구독 요금제**의 에이전트로 돌린다.
#
#   ./polish.command "polish topic=db-index draft=drf_01ABC..."
#   ./polish.command db-index drf_01ABC...
#
# **API 키를 쓰지 않는다.** Codex 는 `codex login status` 가
# "Logged in using ChatGPT" 면 ChatGPT 구독 한도로 돌고, Claude Code 는
# `claude -p` 가 Claude 구독으로 돈다. 토큰당 과금이 붙는 경로가 아니다.
#
# **데몬은 이 파일을 모른다.** 데몬 안의 LLM 호출은 0 이라는 이번 MVP 의
# 경계를 그대로 둔다(AGENTS.md §8). `warruru.command` 와 같은 성격이다 —
# 사람이 누르는 버튼이지 서비스가 아니고, 스스로 아무 판단도 하지 않는다.
#
# **에이전트에게 파일 쓰기 권한을 주지 않는다.** 재료는 `get_topic_records`
# 로 읽고 결과는 `save_draft` 로 되돌려 보내므로 디스크에 손댈 일이 없다.
# 초안이 앉는 `~/.warruru/drafts/` 는 저장소 바깥이라, 쓰기를 열어 두면
# 그 경계를 지키는 것이 어댑터 하나뿐이 된다. 그래서 read-only 로 돈다.

set -eu

# ── 어느 에이전트로 돌릴까 ───────────────────────────────────────────────
# 둘 다 구독으로 돈다. 기본은 Codex 다.
AGENT="${WARRURU_AGENT:-codex}"

# ── 자기 위치 찾기 (바탕화면 심볼릭 링크를 따라간다) ─────────────────────
SELF="$0"
while [ -L "$SELF" ]; do
    LINK=$(readlink "$SELF")
    case "$LINK" in
        /*) SELF="$LINK" ;;
        *)  SELF="$(dirname "$SELF")/$LINK" ;;
    esac
done
REPO="$(cd "$(dirname "$SELF")/.." && pwd)"

# ── 프롬프트 만들기 ──────────────────────────────────────────────────────
if [ "$#" -eq 0 ]; then
    cat >&2 <<'USAGE'
사용법:
  polish.command "polish topic=<슬러그> draft=<초안id>"
  polish.command <슬러그> <초안id>

그 한 줄은 초안 화면(http://127.0.0.1:8787/drafts/{id})이 그대로 준다.
복사해서 붙이면 된다.

환경변수:
  WARRURU_AGENT=claude   Claude Code 로 돌린다 (기본은 codex)
USAGE
    exit 2
fi

case "$1" in
    polish*) PROMPT="$*" ;;
    *)
        if [ "$#" -lt 2 ]; then
            echo "초안 id 가 없다. 슬러그와 초안 id 를 둘 다 적어라." >&2
            exit 2
        fi
        PROMPT="polish topic=$1 draft=$2"
        ;;
esac

# ── 데몬이 떠 있어야 한다 ────────────────────────────────────────────────
# 꺼져 있으면 `save_draft` 가 spool 로 새고, 다듬은 글은 다음 기동까지
# 어디에도 안 보인다. 여기서 멈추는 편이 낫다 — 성공한 줄 알고 브라우저를
# 열었다가 옛 초안을 보는 것이 가장 나쁘다.
if ! curl -fsS -m 3 "http://127.0.0.1:8787/v1/health" >/dev/null 2>&1; then
    echo "데몬이 꺼져 있다. warruru.command 를 먼저 눌러라." >&2
    exit 1
fi

echo "→ $AGENT 로 다듬는다: $PROMPT"
echo

case "$AGENT" in
    codex)
        # -s read-only  : 셸로 파일을 못 고친다. MCP 툴만 쓴다
        # -C "$REPO"    : 기록 규칙(AGENTS.md)이 보이는 자리에서 돈다
        exec codex exec -C "$REPO" -s read-only "$PROMPT"
        ;;
    claude)
        exec claude -p "$PROMPT"
        ;;
    *)
        echo "모르는 에이전트: $AGENT (codex 또는 claude)" >&2
        exit 2
        ;;
esac
