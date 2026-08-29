#!/bin/sh
# 워루루 켜기 — 바탕화면에서 두 번 눌러 데몬을 띄운다.
#
# **이것은 새 프로세스가 아니라 기존 데몬의 시동 버튼이다**(AGENTS.md §3).
# 스케줄러도 서비스도 아니다. 하는 일은 셋뿐이다 — 데몬이 떠 있는지 보고,
# 없으면 띄우고, 무슨 일이 벌어졌는지 알려 준다.
#
# 밀린 날 마감은 이 파일이 하지 않는다. **데몬이 뜰 때 스스로 한다**
# (daemon/app.py 의 lifespan). 그래서 이 버튼은 "동기화" 가 아니라
# "켜기" 다 — 누르는 걸 잊어도 다음 대화에서 어댑터가 같은 일을 한다.
#
# macOS 는 확장자가 `.command` 일 때만 두 번 눌러 실행한다. `.sh` 는
# 편집기로 열린다. 실행 권한(`chmod +x`)도 있어야 한다.
#
# 이 파일은 로그인 셸이 아니라서 `~/.zshrc` 의 환경변수가 보이지 않는다.
# `WARRURU_PUBLISH_REPO` 같은 것이 필요하면 아래 '선택 설정' 에 적는다.

set -u

# ── 선택 설정 ────────────────────────────────────────────────────────────
# 초안을 비공개 저장소로 밀어 넣으려면 주석을 풀고 클론 경로를 적는다.
# 공개 저장소를 적으면 어댑터가 NotPrivateError 로 거절한다.
# export WARRURU_PUBLISH_REPO="$HOME/notes"

# ── 자기 위치 찾기 ───────────────────────────────────────────────────────
# 바탕화면에 심볼릭 링크로 두므로 링크를 끝까지 따라가야 한다.
SELF="$0"
while [ -L "$SELF" ]; do
    LINK=$(readlink "$SELF")
    case "$LINK" in
        /*) SELF="$LINK" ;;
        *)  SELF="$(dirname "$SELF")/$LINK" ;;
    esac
done
LOCAL_DIR="$(cd "$(dirname "$SELF")/.." && pwd -P)"

HOST="${WARRURU_DAEMON_HOST:-127.0.0.1}"
PORT="${WARRURU_DAEMON_PORT:-8787}"
WHOME="${WARRURU_HOME:-$HOME/.warruru}"
BASE="http://$HOST:$PORT"
VENV="$LOCAL_DIR/.venv"
DAEMON="$VENV/bin/warruru-daemon"
LOG="$WHOME/logs/launcher.log"

echo ""
echo "  워루루"
echo "  ─────────────────────────────────────────"

if [ ! -x "$DAEMON" ]; then
    echo "  가상환경을 찾지 못했다:"
    echo "    $DAEMON"
    echo ""
    echo "  고치려면 — cd $LOCAL_DIR && python3 -m venv .venv"
    echo "             && .venv/bin/pip install -e ."
    echo ""
    exit 1
fi

alive() { curl -fsS -m 2 "$BASE/v1/health" >/dev/null 2>&1; }

if alive; then
    echo "  데몬은 이미 떠 있다."
else
    echo "  데몬을 띄운다..."
    mkdir -p "$WHOME/logs"
    # nohup 이 SIGHUP 을 막는다. 이 창을 닫아도 데몬은 산다.
    nohup "$DAEMON" >>"$LOG" 2>&1 &
    i=0
    while [ "$i" -lt 40 ]; do
        alive && break
        sleep 0.5
        i=$((i + 1))
    done
    if alive; then
        echo "  떴다. (PID $(pgrep -f warruru-daemon | head -1))"
    else
        echo "  20초 안에 뜨지 않았다. 로그를 보라:"
        echo "    tail -30 $LOG"
        echo ""
        exit 1
    fi
fi

# ── 무슨 일이 벌어졌나 ───────────────────────────────────────────────────
# 데몬은 뜨면서 밀린 날을 마감한다. 그 결과가 표식에 적혀 있다.
"$VENV/bin/python" - "$WHOME" <<'PY'
import json, pathlib, sys

home = pathlib.Path(sys.argv[1])

marker = home / "run" / "nightly.json"
try:
    made = json.loads(marker.read_text(encoding="utf-8"))
except (OSError, ValueError):
    made = {}

drafted = made.get("drafted") or []
span = (made.get("from"), made.get("to"))
if drafted:
    구간 = f"{span[0]}~{span[1]}" if span[0] else made.get("date", "")
    print(f"  마감: {구간} — 초안 {len(drafted)}편")
    for slug in drafted:
        print(f"        · {slug}")
elif made.get("date"):
    print(f"  마감: {made['date']} 까지 끝났다. 새로 만든 초안은 없다.")

# 아직 DB 에 안 들어간 기록. 이 수가 줄지 않으면 데몬이 계속 못 뜨고 있다.
남은봉투 = sum(
    1
    for path in (home / "spool").glob("*.jsonl")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line.strip()
)
if 남은봉투:
    print(f"  아직 반영 안 된 기록 {남은봉투}건 — 곧 흡수된다.")

죽은편지 = list((home / "spool" / "dead-letter").glob("*.jsonl"))
if 죽은편지:
    print(f"  격리된 봉투 {len(죽은편지)}개 — 사람이 봐야 한다.")

초안 = list((home / "drafts").rglob("*.md"))
남은할일 = sum(
    path.read_text(encoding="utf-8", errors="replace").count("TODO:") for path in 초안
)
print(f"  초안 {len(초안)}편 · 남은 TODO {남은할일}개")
PY

echo "  ─────────────────────────────────────────"
echo "  브라우저를 연다 — $BASE/t"
echo ""
open "$BASE/t" 2>/dev/null || echo "  직접 열어라: $BASE/t"
