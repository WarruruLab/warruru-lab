"""파일 시스템 레이아웃. 플랫폼에 하드코딩하지 않는다."""

from __future__ import annotations

import os
from pathlib import Path

_SUBDIRS = ("config", "spool", "spool/absorbed", "logs", "run")


def warruru_home() -> Path:
    override = os.environ.get("WARRURU_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".warruru"


def ensure_layout(home: Path) -> None:
    """필요한 디렉터리만 만든다. 후속 단계용 디렉터리는 만들지 않는다."""
    for sub in _SUBDIRS:
        (home / sub).mkdir(parents=True, exist_ok=True)


def db_path(home: Path) -> Path:
    return home / "warruru.db"


def config_dir(home: Path) -> Path:
    return home / "config"


def spool_dir(home: Path) -> Path:
    return home / "spool"


def absorbed_dir(home: Path) -> Path:
    return home / "spool" / "absorbed"


def dead_letter_dir(home: Path) -> Path:
    """몇 번을 다시 시도해도 반영되지 않는 봉투를 치워 두는 곳.

    미리 만들지 않는다. 비어 있는 채로 보이면 사용자가 무언가 잃었다고
    오해한다. 실제로 봉투를 치울 때만 생긴다.
    """
    return home / "spool" / "dead-letter"


def drafts_dir(home: Path) -> Path:
    """초안이 앉는 자리. **저장소 바깥이다.**

    origin 이 public 저장소이고 `blog/` 는 이미 추적 중이라, 저장소 안에
    초안을 떨구면 `git add -A` 한 번으로 미완성 사고 과정이 인터넷에 올라간다.
    `.gitignore` 한 줄은 `git add -f` · 새 클론 · 다른 도구 한 번이면 뚫린다.
    """
    return home / "drafts"


def career_dir(home: Path) -> Path:
    """회사별 준비 노트가 앉는 자리. **저장소 바깥이다.**

    초안(`drafts_dir`)과 같은 이유이고, 이유가 하나 더 있다 — 여기에는
    자소서에 쓸 경험과 회사 조사가 섞여 들어온다. 초안보다 더 개인적인
    내용이라 public 저장소 근처에 두면 안 된다.

    `ensure_layout` 이 미리 만들지 않는다. `career-prep` 스킬이 첫 파일을
    쓸 때 생긴다 — 빈 디렉터리가 먼저 보이면 뭔가 잃었다고 오해한다.
    """
    return home / "career"


def cert_dir(home: Path) -> Path:
    """자격증 노트. 회사 노트와 **같은 자리에 섞지 않는다** —
    `career/*.md` 는 회사 하나를 뜻하므로, 자격증이 그 자리에 들어오면
    회사 목록에 자격증이 선다.
    """
    return career_dir(home) / "certs"


def topic_note_dir(home: Path) -> Path:
    """주제별 참고 노트. **기록이 아니다** — 읽을 거리와 확인할 질문이다.

    `learning_record` 에 넣지 않는 이유는 성격이 다르기 때문이다. 기록은
    *내가 한 일* 이고 이쪽은 *남이 정리해 둔 것* 이다. 섞으면 주제 화면의
    건수가 "내가 남긴 것" 을 뜻하지 않게 된다.
    """
    return career_dir(home) / "topics"


def group_note_dir(home: Path) -> Path:
    """묶음(자료구조 · 알고리즘 …)마다 한 장. **면접 문서다.**

    주제 노트가 주제 하나를 다루는 자리라면 이쪽은 그 묶음을 왜 이 순서로
    보는지, 무엇이 자주 같이 나오는지를 적는 자리다.
    """
    return career_dir(home) / "groups"


def logs_dir(home: Path) -> Path:
    return home / "logs"


def run_dir(home: Path) -> Path:
    return home / "run"
