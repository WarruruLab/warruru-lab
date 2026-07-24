# Warruru Local 1단계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여러 AI 에이전트가 MCP로 남긴 개발 기록을 개인 머신의 SQLite에 유실 없이 저장하고, 날짜별 화면으로 되돌아볼 수 있게 한다.

**Architecture:** 프로세스는 둘이다. 에이전트마다 뜨는 얇은 MCP stdio 어댑터(`warruru-mcp`)와, 머신당 하나 상주하며 SQLite에 쓰는 유일한 writer인 FastAPI 데몬(`warruru-daemon`). 어댑터는 식별자를 만들고 데몬에 HTTP로 넘기기만 하며, 데몬에 닿지 못하면 JSONL spool 파일로 폴백한다. 데몬은 기동 시와 주기적으로 spool을 흡수하고, 세션 귀속·자동 마감·Git 스냅샷·화면 서빙을 담당한다.

**Tech Stack:** Python 3.11+, mcp (공식 SDK, stdio), FastAPI, uvicorn, pydantic v2, httpx, Jinja2, SQLite(WAL), pytest

**명세서:** 이 계획은 아래 세 문서를 구현한다. 충돌하면 명세서가 이긴다.
- `warrurulab/warruru-lab/docs/local/specs/2026-07-22-요구사항-명세서.md`
- `warrurulab/warruru-lab/docs/local/specs/2026-07-22-기능-명세서.md`
- `warrurulab/warruru-lab/docs/local/specs/2026-07-22-인터페이스-명세서.md`

## Global Constraints

모든 태스크의 요구사항에 아래가 암묵적으로 포함된다.

**언어·런타임**
- Python `>=3.11`. 개발 머신은 3.13.3.
- 의존성은 다음으로 제한한다: `mcp`, `fastapi`, `uvicorn`, `pydantic`, `httpx`, `jinja2`. 개발 의존성은 `pytest`뿐이다. ULID는 외부 패키지를 쓰지 않고 내부 헬퍼로 구현한다.
- 코드 위치는 `D:/project_univ/warruru-lab/local/`. 독립 git 저장소다. `AI/`와 섞지 않는다.

**절대 원칙**
- 기록 요청은 실패로 끝나지 않는다. MCP 툴은 어떤 내부 오류에도 예외를 밖으로 던지지 않는다.
- Git 수집 실패는 기록을 실패시키지 않는다.
- 데몬은 SQLite의 유일한 writer다. 어댑터는 DB에 직접 접근하지 않는다.
- 어댑터에 비즈니스 로직을 두지 않는다. 세션 귀속·마감·Git 판단은 전부 데몬에 있다.

**식별자** — 어댑터가 생성한다. `machine_id`만 데몬이 만든다.

| 종류 | 형식 |
| --- | --- |
| Work Session | `wrk_` + ULID(26자) |
| Checkpoint | `ckp_` + ULID(26자) |
| Client Instance | `cli_` + ULID(26자) |
| Spool 이벤트 | `evt_` + ULID(26자) |
| Machine | `mch_` + ULID(26자) |

**시각**
- 표기: RFC 3339, UTC, 밀리초 3자리, `Z` 접미. 예 `2026-07-22T08:31:07.482Z`
- 저장: 위 문자열 그대로 TEXT
- 표시: 데몬 머신의 로컬 시간대
- 날짜 파라미터: `YYYY-MM-DD` (로컬 시간대 기준 하루)
- 시각 생성은 반드시 주입 가능한 `Clock`을 거친다. `datetime.now()`를 직접 부르지 않는다.

**열거값**

```text
checkpoint.type      PROBLEM ATTEMPT FAILED_ATTEMPT ERROR TEST_RESULT
                     DECISION RESULT LIMITATION NOTE
work_session.status  ACTIVE FINISHED AUTO_CLOSED
ended_reason         USER_FINISH IDLE_TIMEOUT CLIENT_EXIT
origin               EXPLICIT INFERRED
title_origin         USER DERIVED
checkpoint.source    MCP SPOOL
attached_by          REQUEST CLIENT_INSTANCE REPO_WINDOW NEW
tool storage         DAEMON SPOOL NONE
```

**문자열 상한** — 넘으면 자르고 잘림 표시를 남긴다. 요청을 거절하지 않는다.

| 필드 | 상한 |
| --- | --- |
| `title` | 200자 |
| `body` | 64 KB (65536) |
| `error_excerpt` | 8 KB (8192) |
| `goal`, `result`, `limitations`, `next_steps` | 4 KB (4096) |
| `files` 개수 | 50 |
| `tags` 개수 | 20 |

**설정 기본값**

| 환경변수 | 기본값 |
| --- | --- |
| `WARRURU_HOME` | `~/.warruru` |
| `WARRURU_DAEMON_HOST` | `127.0.0.1` |
| `WARRURU_DAEMON_PORT` | `8787` |
| `WARRURU_TOOL` | 없음 |
| `WARRURU_HTTP_TIMEOUT_SECONDS` | `3` |
| `WARRURU_AUTOSTART_DAEMON` | `true` |
| `WARRURU_ATTACH_WINDOW_MINUTES` | `90` |
| `WARRURU_IDLE_TIMEOUT_HOURS` | `4` |
| `WARRURU_SWEEP_INTERVAL_SECONDS` | `300` |
| `WARRURU_GIT_TIMEOUT_SECONDS` | `2` |
| `WARRURU_GIT_CACHE_TTL_SECONDS` | `5` |
| `WARRURU_GIT_DIRTY_FILE_CAP` | `500` |
| `WARRURU_SPOOL_QUIET_SECONDS` | `10` |
| `WARRURU_LOG_LEVEL` | `INFO` |

**커밋 규칙** — 태스크마다 최소 1회 커밋한다. 메시지는 `feat:` `test:` `chore:` 접두사를 쓴다.

---

## 파일 구조

```text
local/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/plans/                          이 문서
├── src/warruru_local/
│   ├── __init__.py
│   ├── ids.py                ULID 생성, 접두사 식별자          [T1]
│   ├── clock.py              Clock 프로토콜, ISO 변환          [T1]
│   ├── paths.py              WARRURU_HOME 해석, 디렉터리 보장  [T2]
│   ├── limits.py             문자열 상한, 줄바꿈 정규화        [T2]
│   ├── config.py             설정 로딩, 토큰/머신 파일         [T2]
│   ├── logging_setup.py      회전 파일 로그                    [T2]
│   ├── store/
│   │   ├── __init__.py
│   │   ├── db.py             연결, PRAGMA                      [T3]
│   │   ├── migrations.py     스키마 버전과 DDL                 [T3]
│   │   └── repository.py     모든 SQL                          [T4~T7]
│   ├── gitinfo.py            Git 스냅샷 수집과 캐시            [T8]
│   ├── session.py            귀속 규칙, 자동 마감              [T9,T10]
│   ├── spool.py              JSONL 쓰기/읽기                   [T14]
│   ├── daemon/
│   │   ├── __init__.py
│   │   ├── lock.py           단일 인스턴스 잠금                [T11]
│   │   ├── auth.py           토큰 검증                         [T11]
│   │   ├── app.py            FastAPI 조립, lifespan, main      [T11]
│   │   ├── models.py         요청/응답 스키마                  [T12]
│   │   ├── routes_api.py     /v1/*                             [T12,T13]
│   │   ├── context.py        요약 마크다운 생성                [T13]
│   │   ├── absorb.py         spool 흡수                        [T14]
│   │   ├── sweeper.py        주기 작업                         [T14]
│   │   ├── routes_web.py     화면과 삭제/복구                  [T17,T18]
│   │   └── templates/
│   │       ├── base.html                                       [T17]
│   │       ├── day.html                                        [T17]
│   │       └── deleted.html                                    [T18]
│   └── mcp/
│       ├── __init__.py
│       ├── client.py         데몬 HTTP + 자동기동 + 폴백       [T15]
│       └── server.py         FastMCP 툴 4개                    [T16]
└── tests/
    ├── conftest.py
    ├── test_ids.py           test_clock.py       test_paths.py
    ├── test_limits.py        test_config.py
    ├── test_migrations.py    test_repository_*.py
    ├── test_gitinfo.py       test_session_attach.py
    ├── test_session_close.py test_api_*.py
    ├── test_spool.py         test_absorb.py
    ├── test_mcp_client.py    test_mcp_tools.py
    ├── test_web.py
    └── test_acceptance.py    AC-01 ~ AC-11
```

**책임 경계 원칙**
- `store/repository.py`가 SQL을 독점한다. 다른 모듈은 SQL 문자열을 쓰지 않는다.
- `session.py`는 순수 규칙이다. HTTP와 파일 시스템을 모르며, 리포지토리와 `Clock`만 받는다.
- `gitinfo.py`는 subprocess를 독점한다.
- `daemon/routes_*.py`는 얇다. 판단을 `session.py`와 리포지토리에 위임한다.

---

## Task 1: 프로젝트 스캐폴드와 식별자·시각 유틸

**Files:**
- Create: `local/.gitignore`, `local/pyproject.toml`
- Create: `local/src/warruru_local/__init__.py`, `local/src/warruru_local/ids.py`, `local/src/warruru_local/clock.py`
- Test: `local/tests/test_ids.py`, `local/tests/test_clock.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `ids.ulid(now_ms: int | None = None, randomness: bytes | None = None) -> str` — 26자
  - `ids.new_id(prefix: str, now_ms: int | None = None, randomness: bytes | None = None) -> str` — `"{prefix}_{ulid}"`
  - `clock.Clock` (Protocol, `now() -> datetime`)
  - `clock.SystemClock()`, `clock.FixedClock(current: datetime)` — `FixedClock.advance(seconds: float) -> None`
  - `clock.to_iso(dt: datetime) -> str`
  - `clock.parse_iso(text: str) -> datetime`

- [ ] **Step 1: 저장소와 디렉터리를 만든다**

```bash
cd D:/project_univ/warruru-lab
mkdir -p local/src/warruru_local local/tests local/docs/plans
cd local
git init -b main
```

- [ ] **Step 2: `.gitignore`를 쓴다**

`local/.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
dist/
build/
.warruru-test/
```

- [ ] **Step 3: `pyproject.toml`을 쓴다**

`local/pyproject.toml`:

```toml
[project]
name = "warruru-local"
version = "0.1.0"
description = "여러 AI 에이전트의 개발 기록을 개인 머신에 남기는 로컬 우선 기록 계층"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.16.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.11.0",
    "httpx>=0.28.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[project.scripts]
warruru-mcp = "warruru_local.mcp.server:main"
warruru-daemon = "warruru_local.daemon.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/warruru_local"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 4: 실패하는 테스트를 쓴다**

`local/tests/test_ids.py`:

```python
from warruru_local.ids import new_id, ulid


def test_ulid_는_26자다():
    assert len(ulid()) == 26


def test_ulid_는_크록포드_base32_만_쓴다():
    allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert set(ulid()) <= allowed


def test_시각이_커지면_사전순도_커진다():
    early = ulid(now_ms=1_700_000_000_000, randomness=b"\xff" * 10)
    later = ulid(now_ms=1_700_000_000_001, randomness=b"\x00" * 10)
    assert early < later


def test_같은_시각이면_무작위부가_다르다():
    a = ulid(now_ms=1_700_000_000_000)
    b = ulid(now_ms=1_700_000_000_000)
    assert a != b


def test_new_id_는_접두사를_붙인다():
    value = new_id("wrk")
    assert value.startswith("wrk_")
    assert len(value) == 30
```

`local/tests/test_clock.py`:

```python
from datetime import datetime, timedelta, timezone

from warruru_local.clock import FixedClock, SystemClock, parse_iso, to_iso


def test_to_iso_는_밀리초_3자리와_Z_로_끝난다():
    dt = datetime(2026, 7, 22, 8, 31, 7, 482_137, tzinfo=timezone.utc)
    assert to_iso(dt) == "2026-07-22T08:31:07.482Z"


def test_to_iso_는_다른_시간대를_UTC_로_바꾼다():
    kst = timezone(timedelta(hours=9))
    dt = datetime(2026, 7, 22, 17, 31, 7, 0, tzinfo=kst)
    assert to_iso(dt) == "2026-07-22T08:31:07.000Z"


def test_iso_문자열은_사전순_정렬이_시간순과_같다():
    a = to_iso(datetime(2026, 7, 22, 8, 31, 7, 482_000, tzinfo=timezone.utc))
    b = to_iso(datetime(2026, 7, 22, 8, 31, 7, 483_000, tzinfo=timezone.utc))
    assert a < b


def test_parse_iso_는_to_iso_를_되돌린다():
    dt = datetime(2026, 7, 22, 8, 31, 7, 482_000, tzinfo=timezone.utc)
    assert parse_iso(to_iso(dt)) == dt


def test_system_clock_은_UTC_를_준다():
    assert SystemClock().now().tzinfo is timezone.utc


def test_fixed_clock_은_전진시킬_수_있다():
    start = datetime(2026, 7, 22, 0, 0, 0, tzinfo=timezone.utc)
    clock = FixedClock(start)
    clock.advance(90)
    assert clock.now() == start + timedelta(seconds=90)
```

- [ ] **Step 5: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_ids.py tests/test_clock.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.ids'`

- [ ] **Step 6: 최소 구현을 쓴다**

`local/src/warruru_local/__init__.py`:

```python
__version__ = "0.1.0"
```

`local/src/warruru_local/ids.py`:

```python
"""ULID 기반 식별자. 외부 의존성 없이 구현한다.

시간순 정렬이 가능하면서 머신 간 충돌이 없다. 후속 단계에서 두 머신의
기록을 서버에서 합칠 때 그대로 쓴다.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_CHARS = 10
_RANDOM_CHARS = 16
_RANDOM_BYTES = 10


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def ulid(now_ms: int | None = None, randomness: bytes | None = None) -> str:
    """26자 ULID를 만든다. 앞 10자가 밀리초 타임스탬프, 뒤 16자가 무작위다."""
    milliseconds = int(time.time() * 1000) if now_ms is None else now_ms
    entropy = os.urandom(_RANDOM_BYTES) if randomness is None else randomness
    return _encode(milliseconds, _TIME_CHARS) + _encode(
        int.from_bytes(entropy, "big"), _RANDOM_CHARS
    )


def new_id(
    prefix: str, now_ms: int | None = None, randomness: bytes | None = None
) -> str:
    """`wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D` 형태의 접두사 식별자를 만든다."""
    return f"{prefix}_{ulid(now_ms=now_ms, randomness=randomness)}"
```

`local/src/warruru_local/clock.py`:

```python
"""시각. 테스트에서 주입할 수 있도록 프로토콜로 둔다.

`datetime.now()`를 코드 곳곳에서 부르면 귀속 규칙과 자동 마감을 신뢰성
있게 검증할 수 없다. 시각은 반드시 이 모듈을 거친다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """테스트용. 시각을 고정하고 원할 때만 전진시킨다."""

    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current = self._current + timedelta(seconds=seconds)


def to_iso(value: datetime) -> str:
    """RFC 3339 UTC, 밀리초 3자리, Z 접미. 사전순 정렬이 시간순과 같다."""
    utc = value.astimezone(timezone.utc)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // 1000:03d}Z"


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, ISO_FORMAT).replace(tzinfo=timezone.utc)
```

- [ ] **Step 7: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_ids.py tests/test_clock.py -v
```

Expected: PASS — 11 passed

- [ ] **Step 8: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add .gitignore pyproject.toml src/warruru_local/__init__.py src/warruru_local/ids.py src/warruru_local/clock.py tests/test_ids.py tests/test_clock.py
git commit -m "feat: 프로젝트 스캐폴드와 ULID·Clock 유틸"
```

---

## Task 2: 경로·상한·설정·로깅

**Files:**
- Create: `local/src/warruru_local/paths.py`, `local/src/warruru_local/limits.py`, `local/src/warruru_local/config.py`, `local/src/warruru_local/logging_setup.py`
- Test: `local/tests/test_paths.py`, `local/tests/test_limits.py`, `local/tests/test_config.py`
- Create: `local/tests/conftest.py`

**Interfaces:**
- Consumes: `ids.new_id`
- Produces:
  - `paths.warruru_home() -> Path`
  - `paths.ensure_layout(home: Path) -> None`
  - `paths.db_path(home) -> Path`, `paths.spool_dir(home) -> Path`, `paths.absorbed_dir(home) -> Path`, `paths.config_dir(home) -> Path`, `paths.logs_dir(home) -> Path`, `paths.run_dir(home) -> Path`
  - `limits.TITLE_MAX/BODY_MAX/ERROR_EXCERPT_MAX/TEXT_MAX/FILES_MAX/TAGS_MAX` (int)
  - `limits.normalize_newlines(text: str) -> str`
  - `limits.clamp_text(text: str | None, limit: int) -> tuple[str | None, bool]` — 두 번째 값이 잘림 여부
  - `limits.clamp_list(values: list[str] | None, limit: int) -> list[str]`
  - `config.Settings` (dataclass) + `config.load_settings(home: Path | None = None) -> Settings`
  - `config.load_or_create_daemon_config(home: Path) -> tuple[str, int]` — (token, port)
  - `config.load_or_create_machine(home: Path) -> dict` — `machine_id` / `hostname` / `os` / `created_at`
  - `logging_setup.setup_logging(home: Path, name: str, level: str) -> Logger`

- [ ] **Step 1: 공용 픽스처를 쓴다**

`local/tests/conftest.py`:

```python
from datetime import datetime, timezone

import pytest

from warruru_local.clock import FixedClock

FIXED_START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """테스트마다 격리된 WARRURU_HOME 을 준다."""
    root = tmp_path / ".warruru"
    monkeypatch.setenv("WARRURU_HOME", str(root))
    return root


@pytest.fixture
def clock():
    return FixedClock(FIXED_START)
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`local/tests/test_paths.py`:

```python
from pathlib import Path

from warruru_local import paths


def test_환경변수가_있으면_그_경로를_쓴다(home):
    assert paths.warruru_home() == home


def test_환경변수가_없으면_홈의_점warruru_를_쓴다(monkeypatch):
    monkeypatch.delenv("WARRURU_HOME", raising=False)
    assert paths.warruru_home() == Path.home() / ".warruru"


def test_레이아웃을_보장하면_필요한_디렉터리가_생긴다(home):
    paths.ensure_layout(home)
    for sub in ("config", "spool", "spool/absorbed", "logs", "run"):
        assert (home / sub).is_dir()


def test_레이아웃_보장은_두_번_불러도_안전하다(home):
    paths.ensure_layout(home)
    paths.ensure_layout(home)
    assert (home / "config").is_dir()


def test_후속_단계용_디렉터리는_만들지_않는다(home):
    paths.ensure_layout(home)
    for sub in ("records", "evidence", "drafts"):
        assert not (home / sub).exists()
```

`local/tests/test_limits.py`:

```python
from warruru_local import limits


def test_줄바꿈을_LF_로_정규화한다():
    assert limits.normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_상한_이하면_그대로_두고_잘리지_않았다고_한다():
    text, truncated = limits.clamp_text("짧다", limits.TITLE_MAX)
    assert text == "짧다"
    assert truncated is False


def test_상한을_넘으면_자르고_잘렸다고_한다():
    text, truncated = limits.clamp_text("가" * 300, limits.TITLE_MAX)
    assert len(text) == limits.TITLE_MAX
    assert truncated is True


def test_None_은_그대로_None_이다():
    text, truncated = limits.clamp_text(None, limits.BODY_MAX)
    assert text is None
    assert truncated is False


def test_목록도_개수_상한으로_자른다():
    assert len(limits.clamp_list(["f"] * 80, limits.FILES_MAX)) == limits.FILES_MAX


def test_목록의_None_은_빈_목록이다():
    assert limits.clamp_list(None, limits.TAGS_MAX) == []


def test_상한값은_명세서와_같다():
    assert limits.TITLE_MAX == 200
    assert limits.BODY_MAX == 65536
    assert limits.ERROR_EXCERPT_MAX == 8192
    assert limits.TEXT_MAX == 4096
    assert limits.FILES_MAX == 50
    assert limits.TAGS_MAX == 20
```

`local/tests/test_config.py`:

```python
import json

from warruru_local import config, paths


def test_기본값은_명세서와_같다(home):
    settings = config.load_settings(home)
    assert settings.host == "127.0.0.1"
    assert settings.port == 8787
    assert settings.attach_window_minutes == 90
    assert settings.idle_timeout_hours == 4
    assert settings.sweep_interval_seconds == 300
    assert settings.git_timeout_seconds == 2.0
    assert settings.git_cache_ttl_seconds == 5.0
    assert settings.git_dirty_file_cap == 500
    assert settings.spool_quiet_seconds == 10
    assert settings.http_timeout_seconds == 3.0
    assert settings.autostart_daemon is True


def test_환경변수가_기본값을_이긴다(home, monkeypatch):
    monkeypatch.setenv("WARRURU_IDLE_TIMEOUT_HOURS", "9")
    monkeypatch.setenv("WARRURU_AUTOSTART_DAEMON", "false")
    settings = config.load_settings(home)
    assert settings.idle_timeout_hours == 9
    assert settings.autostart_daemon is False


def test_데몬_설정이_없으면_토큰을_만들어_저장한다(home):
    paths.ensure_layout(home)
    token, port = config.load_or_create_daemon_config(home)
    assert len(token) >= 32
    assert port == 8787
    saved = json.loads((home / "config" / "daemon.json").read_text(encoding="utf-8"))
    assert saved["token"] == token


def test_데몬_설정은_두_번_불러도_같은_토큰이다(home):
    paths.ensure_layout(home)
    first, _ = config.load_or_create_daemon_config(home)
    second, _ = config.load_or_create_daemon_config(home)
    assert first == second


def test_머신_식별자는_한_번_만들어지면_바뀌지_않는다(home):
    paths.ensure_layout(home)
    first = config.load_or_create_machine(home)
    second = config.load_or_create_machine(home)
    assert first["machine_id"] == second["machine_id"]
    assert first["machine_id"].startswith("mch_")


def test_환경변수_토큰이_파일보다_우선한다(home, monkeypatch):
    paths.ensure_layout(home)
    config.load_or_create_daemon_config(home)
    monkeypatch.setenv("WARRURU_TOKEN", "override-token")
    settings = config.load_settings(home)
    assert settings.token == "override-token"
```

- [ ] **Step 3: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_paths.py tests/test_limits.py tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.paths'`

- [ ] **Step 4: `paths.py`를 쓴다**

```python
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


def logs_dir(home: Path) -> Path:
    return home / "logs"


def run_dir(home: Path) -> Path:
    return home / "run"
```

- [ ] **Step 5: `limits.py`를 쓴다**

```python
"""문자열 상한. 넘으면 자르고 표시할 뿐, 요청을 거절하지 않는다."""

from __future__ import annotations

TITLE_MAX = 200
BODY_MAX = 65536
ERROR_EXCERPT_MAX = 8192
TEXT_MAX = 4096
FILES_MAX = 50
TAGS_MAX = 20


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def clamp_text(text: str | None, limit: int) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    normalized = normalize_newlines(text)
    if len(normalized) <= limit:
        return normalized, False
    return normalized[:limit], True


def clamp_list(values: list[str] | None, limit: int) -> list[str]:
    if not values:
        return []
    return list(values[:limit])
```

- [ ] **Step 6: `config.py`를 쓴다**

```python
"""설정. 우선순위는 환경변수 > config/daemon.json > 기본값이다."""

from __future__ import annotations

import json
import os
import platform
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from warruru_local import paths
from warruru_local.clock import to_iso
from warruru_local.ids import new_id

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


@dataclass(frozen=True)
class Settings:
    home: Path
    host: str
    port: int
    token: str
    tool: str | None
    http_timeout_seconds: float
    autostart_daemon: bool
    attach_window_minutes: int
    idle_timeout_hours: int
    sweep_interval_seconds: int
    git_timeout_seconds: float
    git_cache_ttl_seconds: float
    git_dirty_file_cap: int
    spool_quiet_seconds: int
    log_level: str


def _env_int(key: str, fallback: int) -> int:
    raw = os.environ.get(key)
    return int(raw) if raw else fallback


def _env_float(key: str, fallback: float) -> float:
    raw = os.environ.get(key)
    return float(raw) if raw else fallback


def _env_bool(key: str, fallback: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_or_create_daemon_config(home: Path) -> tuple[str, int]:
    """토큰과 포트를 읽고, 없으면 만들어 저장한다."""
    target = paths.config_dir(home) / "daemon.json"
    if target.exists():
        saved = json.loads(target.read_text(encoding="utf-8"))
        return saved["token"], int(saved.get("port", DEFAULT_PORT))

    token = secrets.token_hex(24)
    port = DEFAULT_PORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"token": token, "port": port}, indent=2), encoding="utf-8"
    )
    try:
        os.chmod(target, 0o600)
    except (NotImplementedError, PermissionError, OSError):
        pass  # 권한 설정을 지원하지 않는 플랫폼에서는 넘어간다
    return token, port


def load_or_create_machine(home: Path) -> dict:
    """머신 식별자를 읽고, 없으면 만들어 고정한다. 데몬만 부른다."""
    target = paths.config_dir(home) / "machine.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))

    record = {
        "machine_id": new_id("mch"),
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "created_at": to_iso(datetime.now(timezone.utc)),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def load_settings(home: Path | None = None) -> Settings:
    resolved = home if home is not None else paths.warruru_home()
    paths.ensure_layout(resolved)
    file_token, file_port = load_or_create_daemon_config(resolved)

    return Settings(
        home=resolved,
        host=os.environ.get("WARRURU_DAEMON_HOST", DEFAULT_HOST),
        port=_env_int("WARRURU_DAEMON_PORT", file_port),
        token=os.environ.get("WARRURU_TOKEN") or file_token,
        tool=os.environ.get("WARRURU_TOOL") or None,
        http_timeout_seconds=_env_float("WARRURU_HTTP_TIMEOUT_SECONDS", 3.0),
        autostart_daemon=_env_bool("WARRURU_AUTOSTART_DAEMON", True),
        attach_window_minutes=_env_int("WARRURU_ATTACH_WINDOW_MINUTES", 90),
        idle_timeout_hours=_env_int("WARRURU_IDLE_TIMEOUT_HOURS", 4),
        sweep_interval_seconds=_env_int("WARRURU_SWEEP_INTERVAL_SECONDS", 300),
        git_timeout_seconds=_env_float("WARRURU_GIT_TIMEOUT_SECONDS", 2.0),
        git_cache_ttl_seconds=_env_float("WARRURU_GIT_CACHE_TTL_SECONDS", 5.0),
        git_dirty_file_cap=_env_int("WARRURU_GIT_DIRTY_FILE_CAP", 500),
        spool_quiet_seconds=_env_int("WARRURU_SPOOL_QUIET_SECONDS", 10),
        log_level=os.environ.get("WARRURU_LOG_LEVEL", "INFO"),
    )
```

- [ ] **Step 7: `logging_setup.py`를 쓴다**

```python
"""회전 파일 로그. 기록이 안 될 때 사용자가 원인을 찾을 수 있어야 한다."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from warruru_local import paths

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def setup_logging(home: Path, name: str, level: str = "INFO") -> logging.Logger:
    """`name` 은 'daemon' 또는 'mcp'. 파일은 logs/{name}.log 다."""
    logger = logging.getLogger(f"warruru.{name}")
    if logger.handlers:
        return logger

    paths.logs_dir(home).mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        paths.logs_dir(home) / f"{name}.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger
```

- [ ] **Step 8: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_paths.py tests/test_limits.py tests/test_config.py -v
```

Expected: PASS — 20 passed

- [ ] **Step 9: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/paths.py src/warruru_local/limits.py src/warruru_local/config.py src/warruru_local/logging_setup.py tests/conftest.py tests/test_paths.py tests/test_limits.py tests/test_config.py
git commit -m "feat: 경로 해석·문자열 상한·설정 로딩·회전 로그"
```

---

## Task 3: DB 연결과 스키마 마이그레이션

**Files:**
- Create: `local/src/warruru_local/store/__init__.py`, `local/src/warruru_local/store/db.py`, `local/src/warruru_local/store/migrations.py`
- Test: `local/tests/test_migrations.py`

**Interfaces:**
- Consumes: `paths.db_path`
- Produces:
  - `db.connect(path: Path) -> sqlite3.Connection` — WAL, `busy_timeout=5000`, `foreign_keys=ON`, `row_factory=sqlite3.Row`
  - `migrations.CURRENT_VERSION: int` (= 1)
  - `migrations.migrate(conn: sqlite3.Connection, now_iso: str) -> int` — 적용 후 버전 반환. 재실행 무해
  - `migrations.current_version(conn) -> int`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_migrations.py`:

```python
from warruru_local.store import db, migrations

NOW = "2026-07-22T08:00:00.000Z"

EXPECTED_TABLES = {
    "schema_migrations",
    "machine",
    "client_instance",
    "work_session",
    "checkpoint",
}


def _tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


def test_빈_DB_에_마이그레이션하면_현재_버전이_된다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    assert migrations.migrate(conn, NOW) == migrations.CURRENT_VERSION


def test_필요한_테이블이_모두_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    assert EXPECTED_TABLES <= _tables(conn)


def test_두_번_마이그레이션해도_안전하다(tmp_path):
    path = tmp_path / "warruru.db"
    conn = db.connect(path)
    migrations.migrate(conn, NOW)
    migrations.migrate(conn, NOW)
    assert migrations.current_version(conn) == migrations.CURRENT_VERSION
    assert EXPECTED_TABLES <= _tables(conn)


def test_WAL_모드가_켜진다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_외래키가_켜진다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_행을_이름으로_읽을_수_있다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    row = conn.execute("SELECT version FROM schema_migrations").fetchone()
    assert row["version"] == migrations.CURRENT_VERSION


def test_체크포인트_인덱스가_생긴다(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert "ix_ckp_work" in names
    assert "ix_work_by_client" in names
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_migrations.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.store'`

- [ ] **Step 3: `store/__init__.py`와 `store/db.py`를 쓴다**

`local/src/warruru_local/store/__init__.py`:

```python
```

(빈 파일이다.)

`local/src/warruru_local/store/db.py`:

```python
"""SQLite 연결. 데몬만 이 함수를 부른다."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

- [ ] **Step 4: `store/migrations.py`를 쓴다**

명세서 IF-4의 DDL을 그대로 옮긴다.

```python
"""스키마 버전과 DDL. 데몬이 기동 시 순차 적용한다. 되돌리기는 없다."""

from __future__ import annotations

import sqlite3

CURRENT_VERSION = 1

_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine (
    machine_id TEXT PRIMARY KEY,
    hostname   TEXT NOT NULL,
    os         TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_instance (
    client_instance_id TEXT PRIMARY KEY,
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,
    client_name        TEXT,
    client_version     TEXT,
    cwd                TEXT,
    started_at         TEXT NOT NULL,
    closed_at          TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_session (
    work_id            TEXT PRIMARY KEY,
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    client_instance_id TEXT REFERENCES client_instance(client_instance_id),
    tool               TEXT NOT NULL,

    title              TEXT,
    title_origin       TEXT,
    goal               TEXT,

    status             TEXT NOT NULL,
    origin             TEXT NOT NULL,
    ended_reason       TEXT,

    started_at         TEXT NOT NULL,
    last_activity_at   TEXT NOT NULL,
    ended_at           TEXT,

    result             TEXT,
    limitations        TEXT,
    next_steps         TEXT,

    start_repo_path    TEXT,
    start_repo_name    TEXT,
    start_branch       TEXT,
    start_commit       TEXT,
    last_repo_path     TEXT,
    end_repo_path      TEXT,
    end_branch         TEXT,
    end_commit         TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_work_started
    ON work_session (started_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_by_client
    ON work_session (client_instance_id, status, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_by_repo
    ON work_session (machine_id, tool, last_repo_path, status, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS ix_work_active_sweep
    ON work_session (status, last_activity_at);

CREATE TABLE IF NOT EXISTS checkpoint (
    checkpoint_id      TEXT PRIMARY KEY,
    work_id            TEXT NOT NULL REFERENCES work_session(work_id),
    machine_id         TEXT NOT NULL REFERENCES machine(machine_id),
    tool               TEXT NOT NULL,

    type               TEXT NOT NULL,
    title              TEXT NOT NULL,
    body               TEXT,
    body_truncated     INTEGER NOT NULL DEFAULT 0,

    occurred_at        TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    source             TEXT NOT NULL,

    repo_path          TEXT,
    repo_name          TEXT,
    branch             TEXT,
    commit_sha         TEXT,
    dirty              INTEGER,
    dirty_file_count   INTEGER,
    dirty_count_capped INTEGER NOT NULL DEFAULT 0,

    files_json         TEXT,
    error_excerpt      TEXT,
    tags_json          TEXT,

    deleted_at         TEXT,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ckp_work
    ON checkpoint (work_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_ckp_occurred
    ON checkpoint (occurred_at DESC);
"""

_SCRIPTS = {1: _V1}


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master"
        " WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if row is None:
        return 0
    result = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(result["v"] or 0)


def migrate(conn: sqlite3.Connection, now_iso: str) -> int:
    """미적용 버전을 순서대로 적용한다. 이미 최신이면 아무 일도 하지 않는다."""
    version = current_version(conn)
    for target in sorted(_SCRIPTS):
        if target <= version:
            continue
        conn.executescript(_SCRIPTS[target])
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (version, applied_at)"
            " VALUES (?, ?)",
            (target, now_iso),
        )
        version = target
    return version
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_migrations.py -v
```

Expected: PASS — 7 passed

- [ ] **Step 6: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/store/ tests/test_migrations.py
git commit -m "feat: SQLite 연결과 v1 스키마 마이그레이션"
```

---

## Task 4: 리포지토리 A — machine, client_instance

**Files:**
- Create: `local/src/warruru_local/store/repository.py`
- Test: `local/tests/test_repository_base.py`

**Interfaces:**
- Consumes: `db.connect`, `migrations.migrate`
- Produces:
  - `repository.Repository(conn: sqlite3.Connection)`
  - `Repository.ensure_machine(machine_id: str, hostname: str, os_name: str, now_iso: str) -> dict`
  - `Repository.ensure_client(client_instance_id: str, machine_id: str, tool: str, client_name: str | None, client_version: str | None, cwd: str | None, now_iso: str) -> dict`
  - `Repository.close_client(client_instance_id: str, now_iso: str) -> None`
  - `Repository.get_client(client_instance_id: str) -> dict | None`
  - 모든 반환 `dict`는 `sqlite3.Row`를 `dict()`로 변환한 것이다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_repository_base.py`:

```python
import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
LATER = "2026-07-22T09:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    return Repository(conn)


def test_머신을_만들면_행이_생긴다(repo):
    row = repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    assert row["machine_id"] == MACHINE
    assert row["hostname"] == "DESKTOP-A"


def test_머신을_두_번_만들면_처음_값이_남는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    row = repo.ensure_machine(MACHINE, "DESKTOP-B", "macOS 15", LATER)
    assert row["hostname"] == "DESKTOP-A"
    assert row["created_at"] == NOW


def test_클라이언트를_처음_보면_행이_생긴다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    row = repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/x", NOW)
    assert row["tool"] == "codex"
    assert row["cwd"] == "D:/x"
    assert row["closed_at"] is None


def test_클라이언트를_다시_보면_새로_만들지_않는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/x", NOW)
    row = repo.ensure_client(CLIENT, MACHINE, "codex", "Codex", "1.2.3", "D:/y", LATER)
    assert row["started_at"] == NOW
    assert row["cwd"] == "D:/y"  # 최근 작업 디렉터리는 갱신한다


def test_클라이언트를_닫으면_닫힌_시각이_남는다(repo):
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repo.ensure_client(CLIENT, MACHINE, "codex", None, None, None, NOW)
    repo.close_client(CLIENT, LATER)
    assert repo.get_client(CLIENT)["closed_at"] == LATER


def test_없는_클라이언트를_닫아도_터지지_않는다(repo):
    repo.close_client("cli_없음", LATER)
    assert repo.get_client("cli_없음") is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_base.py -v
```

Expected: FAIL — `ImportError: cannot import name 'Repository'`

- [ ] **Step 3: `store/repository.py`를 만든다**

```python
"""모든 SQL 을 독점한다. 다른 모듈은 SQL 문자열을 쓰지 않는다."""

from __future__ import annotations

import sqlite3


def _as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # machine
    # ------------------------------------------------------------------

    def ensure_machine(
        self, machine_id: str, hostname: str, os_name: str, now_iso: str
    ) -> dict:
        """없으면 만들고, 있으면 처음 값을 그대로 둔다."""
        self._conn.execute(
            "INSERT OR IGNORE INTO machine (machine_id, hostname, os, created_at)"
            " VALUES (?, ?, ?, ?)",
            (machine_id, hostname, os_name, now_iso),
        )
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM machine WHERE machine_id = ?", (machine_id,)
            ).fetchone()
        )

    # ------------------------------------------------------------------
    # client_instance
    # ------------------------------------------------------------------

    def get_client(self, client_instance_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM client_instance WHERE client_instance_id = ?",
                (client_instance_id,),
            ).fetchone()
        )

    def ensure_client(
        self,
        client_instance_id: str,
        machine_id: str,
        tool: str,
        client_name: str | None,
        client_version: str | None,
        cwd: str | None,
        now_iso: str,
    ) -> dict:
        """처음 보는 대화면 만든다. 별도 등록 호출이 필요 없다."""
        self._conn.execute(
            "INSERT OR IGNORE INTO client_instance ("
            " client_instance_id, machine_id, tool, client_name, client_version,"
            " cwd, started_at, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                client_instance_id,
                machine_id,
                tool,
                client_name,
                client_version,
                cwd,
                now_iso,
                now_iso,
            ),
        )
        if cwd is not None:
            self._conn.execute(
                "UPDATE client_instance SET cwd = ? WHERE client_instance_id = ?",
                (cwd, client_instance_id),
            )
        return self.get_client(client_instance_id)

    def close_client(self, client_instance_id: str, now_iso: str) -> None:
        self._conn.execute(
            "UPDATE client_instance SET closed_at = ?"
            " WHERE client_instance_id = ? AND closed_at IS NULL",
            (now_iso, client_instance_id),
        )
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_base.py -v
```

Expected: PASS — 6 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/store/repository.py tests/test_repository_base.py
git commit -m "feat: 리포지토리 machine·client_instance"
```

---

## Task 5: 리포지토리 B — work_session

**Files:**
- Modify: `local/src/warruru_local/store/repository.py` (클래스에 메서드 추가)
- Test: `local/tests/test_repository_work.py`

**Interfaces:**
- Consumes: Task 4의 `Repository`
- Produces: `Repository`에 다음 메서드
  - `get_work(work_id: str) -> dict | None`
  - `insert_work(*, work_id, machine_id, client_instance_id, tool, title, title_origin, goal, origin, started_at, repo_path, repo_name, branch, commit_sha, now_iso) -> tuple[dict, bool]` — 두 번째 값이 `duplicate`
  - `touch_work(work_id: str, now_iso: str, repo_path: str | None) -> None`
  - `set_work_title(work_id: str, title: str) -> None` — `title_origin`을 `DERIVED`로 둔다
  - `find_active_by_client(client_instance_id: str) -> dict | None`
  - `find_active_by_repo(machine_id: str, tool: str, repo_path: str, since_iso: str) -> dict | None`
  - `finish_work(*, work_id, result, limitations, next_steps, ended_at, repo_path, branch, commit_sha, now_iso) -> dict`
  - `auto_close_work(work_id: str, ended_reason: str, ended_at: str, now_iso: str) -> dict`
  - `find_stale_active(before_iso: str) -> list[dict]`
  - `find_active_by_client_ids(client_instance_id: str) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_repository_work.py`:

```python
import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
OTHER_CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF5"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    repository.ensure_client(OTHER_CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    return repository


def _insert(repo, work_id=WORK, client=CLIENT, started_at=NOW, repo_path="D:/x",
            origin="EXPLICIT", title="제목"):
    return repo.insert_work(
        work_id=work_id,
        machine_id=MACHINE,
        client_instance_id=client,
        tool="codex",
        title=title,
        title_origin="USER" if title else None,
        goal="목표",
        origin=origin,
        started_at=started_at,
        repo_path=repo_path,
        repo_name="x",
        branch="main",
        commit_sha="a3f91c2",
        now_iso=started_at,
    )


def test_작업을_만들면_ACTIVE_다(repo):
    row, duplicate = _insert(repo)
    assert row["status"] == "ACTIVE"
    assert row["origin"] == "EXPLICIT"
    assert row["last_activity_at"] == NOW
    assert row["last_repo_path"] == "D:/x"
    assert duplicate is False


def test_같은_식별자를_다시_넣으면_기존_행을_준다(repo):
    _insert(repo, title="처음")
    row, duplicate = _insert(repo, title="나중")
    assert duplicate is True
    assert row["title"] == "처음"


def test_활동을_갱신하면_마지막_시각과_저장소가_바뀐다(repo):
    _insert(repo)
    repo.touch_work(WORK, T1, "D:/y")
    row = repo.get_work(WORK)
    assert row["last_activity_at"] == T1
    assert row["last_repo_path"] == "D:/y"


def test_저장소가_None_이면_기존_저장소를_유지한다(repo):
    _insert(repo)
    repo.touch_work(WORK, T1, None)
    assert repo.get_work(WORK)["last_repo_path"] == "D:/x"


def test_제목을_승격하면_파생으로_표시된다(repo):
    _insert(repo, title=None)
    repo.set_work_title(WORK, "첫 체크포인트 제목")
    row = repo.get_work(WORK)
    assert row["title"] == "첫 체크포인트 제목"
    assert row["title_origin"] == "DERIVED"


def test_대화로_진행중_작업을_찾는다(repo):
    _insert(repo)
    assert repo.find_active_by_client(CLIENT)["work_id"] == WORK


def test_대화에_진행중_작업이_여러_개면_가장_최근_것을_준다(repo):
    _insert(repo, work_id="wrk_A", started_at=NOW)
    _insert(repo, work_id="wrk_B", started_at=T1)
    assert repo.find_active_by_client(CLIENT)["work_id"] == "wrk_B"


def test_저장소와_시간창으로_진행중_작업을_찾는다(repo):
    _insert(repo)
    found = repo.find_active_by_repo(MACHINE, "codex", "D:/x", since_iso=NOW)
    assert found["work_id"] == WORK


def test_시간창_밖이면_찾지_않는다(repo):
    _insert(repo)
    assert repo.find_active_by_repo(MACHINE, "codex", "D:/x", since_iso=T1) is None


def test_마감하면_FINISHED_이고_사유가_남는다(repo):
    _insert(repo)
    row = repo.finish_work(
        work_id=WORK, result="됐다", limitations="한계", next_steps="다음",
        ended_at=T2, repo_path="D:/x", branch="main", commit_sha="bbb",
        now_iso=T2,
    )
    assert row["status"] == "FINISHED"
    assert row["ended_reason"] == "USER_FINISH"
    assert row["end_commit"] == "bbb"
    assert row["result"] == "됐다"


def test_마감된_작업은_대화_조회에_안_걸린다(repo):
    _insert(repo)
    repo.finish_work(
        work_id=WORK, result=None, limitations=None, next_steps=None,
        ended_at=T2, repo_path=None, branch=None, commit_sha=None, now_iso=T2,
    )
    assert repo.find_active_by_client(CLIENT) is None


def test_자동마감은_AUTO_CLOSED_이고_사유를_보존한다(repo):
    _insert(repo)
    row = repo.auto_close_work(WORK, "IDLE_TIMEOUT", ended_at=NOW, now_iso=T2)
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "IDLE_TIMEOUT"
    assert row["ended_at"] == NOW


def test_유휴_기준보다_오래된_진행중_작업을_찾는다(repo):
    _insert(repo, work_id="wrk_오래", started_at=NOW)
    _insert(repo, work_id="wrk_최근", started_at=T2)
    stale = repo.find_stale_active(before_iso=T1)
    assert [row["work_id"] for row in stale] == ["wrk_오래"]


def test_대화의_진행중_작업을_모두_찾는다(repo):
    _insert(repo, work_id="wrk_A", started_at=NOW)
    _insert(repo, work_id="wrk_B", started_at=T1)
    _insert(repo, work_id="wrk_C", client=OTHER_CLIENT, started_at=T1)
    ids = {row["work_id"] for row in repo.find_active_by_client_ids(CLIENT)}
    assert ids == {"wrk_A", "wrk_B"}
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_work.py -v
```

Expected: FAIL — `AttributeError: 'Repository' object has no attribute 'insert_work'`

- [ ] **Step 3: `Repository`에 work_session 메서드를 추가한다**

`local/src/warruru_local/store/repository.py`의 클래스 끝에 이어 붙인다.

```python
    # ------------------------------------------------------------------
    # work_session
    # ------------------------------------------------------------------

    def get_work(self, work_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session WHERE work_id = ?", (work_id,)
            ).fetchone()
        )

    def insert_work(
        self,
        *,
        work_id: str,
        machine_id: str,
        client_instance_id: str | None,
        tool: str,
        title: str | None,
        title_origin: str | None,
        goal: str | None,
        origin: str,
        started_at: str,
        repo_path: str | None,
        repo_name: str | None,
        branch: str | None,
        commit_sha: str | None,
        now_iso: str,
    ) -> tuple[dict, bool]:
        """멱등이다. 같은 식별자가 이미 있으면 기존 행과 True 를 준다."""
        existing = self.get_work(work_id)
        if existing is not None:
            return existing, True

        self._conn.execute(
            "INSERT INTO work_session ("
            " work_id, machine_id, client_instance_id, tool,"
            " title, title_origin, goal,"
            " status, origin,"
            " started_at, last_activity_at,"
            " start_repo_path, start_repo_name, start_branch, start_commit,"
            " last_repo_path, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                work_id, machine_id, client_instance_id, tool,
                title, title_origin, goal,
                origin,
                started_at, started_at,
                repo_path, repo_name, branch, commit_sha,
                repo_path, now_iso, now_iso,
            ),
        )
        return self.get_work(work_id), False

    def touch_work(self, work_id: str, now_iso: str, repo_path: str | None) -> None:
        """마지막 활동 시각을 올린다. 저장소가 None 이면 기존 값을 유지한다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " last_activity_at = ?,"
            " last_repo_path = COALESCE(?, last_repo_path),"
            " updated_at = ?"
            " WHERE work_id = ?",
            (now_iso, repo_path, now_iso, work_id),
        )

    def set_work_title(self, work_id: str, title: str) -> None:
        """제목이 없는 세션에만 붙인다. 이미 있으면 건드리지 않는다."""
        self._conn.execute(
            "UPDATE work_session SET title = ?, title_origin = 'DERIVED'"
            " WHERE work_id = ? AND title IS NULL",
            (title, work_id),
        )

    def find_active_by_client(self, client_instance_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session"
                " WHERE client_instance_id = ? AND status = 'ACTIVE'"
                "   AND deleted_at IS NULL"
                " ORDER BY started_at DESC LIMIT 1",
                (client_instance_id,),
            ).fetchone()
        )

    def find_active_by_client_ids(self, client_instance_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE client_instance_id = ? AND status = 'ACTIVE'"
            "   AND deleted_at IS NULL",
            (client_instance_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def find_active_by_repo(
        self, machine_id: str, tool: str, repo_path: str, since_iso: str
    ) -> dict | None:
        """어댑터가 재기동되어 대화 식별자가 바뀐 경우를 위한 경로다."""
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM work_session"
                " WHERE machine_id = ? AND tool = ? AND last_repo_path = ?"
                "   AND status = 'ACTIVE' AND deleted_at IS NULL"
                "   AND last_activity_at >= ?"
                " ORDER BY last_activity_at DESC LIMIT 1",
                (machine_id, tool, repo_path, since_iso),
            ).fetchone()
        )

    def finish_work(
        self,
        *,
        work_id: str,
        result: str | None,
        limitations: str | None,
        next_steps: str | None,
        ended_at: str,
        repo_path: str | None,
        branch: str | None,
        commit_sha: str | None,
        now_iso: str,
    ) -> dict:
        """자동 마감된 세션에도 쓸 수 있다. 상태를 FINISHED 로 덮는다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " status = 'FINISHED', ended_reason = 'USER_FINISH', ended_at = ?,"
            " result = COALESCE(?, result),"
            " limitations = COALESCE(?, limitations),"
            " next_steps = COALESCE(?, next_steps),"
            " end_repo_path = COALESCE(?, end_repo_path),"
            " end_branch = COALESCE(?, end_branch),"
            " end_commit = COALESCE(?, end_commit),"
            " updated_at = ?"
            " WHERE work_id = ?",
            (
                ended_at, result, limitations, next_steps,
                repo_path, branch, commit_sha, now_iso, work_id,
            ),
        )
        return self.get_work(work_id)

    def auto_close_work(
        self, work_id: str, ended_reason: str, ended_at: str, now_iso: str
    ) -> dict:
        """종료 Git 스냅샷은 수집하지 않는다. 지금 읽은 값은 그 작업의 결과가 아니다."""
        self._conn.execute(
            "UPDATE work_session SET"
            " status = 'AUTO_CLOSED', ended_reason = ?, ended_at = ?, updated_at = ?"
            " WHERE work_id = ? AND status = 'ACTIVE'",
            (ended_reason, ended_at, now_iso, work_id),
        )
        return self.get_work(work_id)

    def find_stale_active(self, before_iso: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE status = 'ACTIVE' AND last_activity_at < ?"
            "   AND deleted_at IS NULL",
            (before_iso,),
        ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_work.py -v
```

Expected: PASS — 14 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/store/repository.py tests/test_repository_work.py
git commit -m "feat: 리포지토리 work_session 쓰기와 조회"
```

---

## Task 6: 리포지토리 C — checkpoint

**Files:**
- Modify: `local/src/warruru_local/store/repository.py`
- Test: `local/tests/test_repository_checkpoint.py`

**Interfaces:**
- Consumes: Task 5의 `Repository`
- Produces: `Repository`에 다음 메서드
  - `insert_checkpoint(*, checkpoint_id, work_id, machine_id, tool, type, title, body, body_truncated, occurred_at, recorded_at, source, repo_path, repo_name, branch, commit_sha, dirty, dirty_file_count, dirty_count_capped, files, error_excerpt, tags) -> tuple[dict, bool]`
  - `get_checkpoint(checkpoint_id: str) -> dict | None`
  - `list_checkpoints(work_id: str, include_deleted: bool = False) -> list[dict]`
  - `count_checkpoints(work_id: str) -> int`
  - `count_types(work_id: str) -> dict[str, int]`
  - `files`/`tags`는 `list[str]`로 주고받는다. JSON 직렬화는 리포지토리 안에서 한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_repository_checkpoint.py`:

```python
import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

NOW = "2026-07-22T08:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, NOW)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", NOW)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", NOW)
    repository.insert_work(
        work_id=WORK, machine_id=MACHINE, client_instance_id=CLIENT, tool="codex",
        title="제목", title_origin="USER", goal=None, origin="EXPLICIT",
        started_at=NOW, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", now_iso=NOW,
    )
    return repository


def _insert(repo, checkpoint_id=CKP, ckp_type="PROBLEM", occurred_at=T1,
            files=None, tags=None, source="MCP"):
    return repo.insert_checkpoint(
        checkpoint_id=checkpoint_id, work_id=WORK, machine_id=MACHINE,
        tool="codex", type=ckp_type, title="제목", body="본문",
        body_truncated=False, occurred_at=occurred_at, recorded_at=occurred_at,
        source=source, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", dirty=True, dirty_file_count=4,
        dirty_count_capped=False, files=files, error_excerpt=None, tags=tags,
    )


def test_체크포인트를_넣으면_읽을_수_있다(repo):
    row, duplicate = _insert(repo)
    assert duplicate is False
    assert row["type"] == "PROBLEM"
    assert row["dirty"] == 1
    assert row["source"] == "MCP"


def test_같은_식별자면_기존_행을_준다(repo):
    _insert(repo, ckp_type="PROBLEM")
    row, duplicate = _insert(repo, ckp_type="RESULT")
    assert duplicate is True
    assert row["type"] == "PROBLEM"


def test_파일과_태그는_목록으로_오가며_JSON_으로_저장된다(repo):
    _insert(repo, files=["a.py", "b.py"], tags=["idempotency"])
    row = repo.get_checkpoint(CKP)
    assert row["files_json"] == '["a.py", "b.py"]'
    assert row["tags_json"] == '["idempotency"]'


def test_파일이_없으면_빈_목록으로_저장된다(repo):
    _insert(repo)
    assert repo.get_checkpoint(CKP)["files_json"] == "[]"


def test_작업의_체크포인트를_발생_시각_오름차순으로_준다(repo):
    _insert(repo, checkpoint_id="ckp_늦음", occurred_at=T2)
    _insert(repo, checkpoint_id="ckp_이름", occurred_at=T1)
    ids = [row["checkpoint_id"] for row in repo.list_checkpoints(WORK)]
    assert ids == ["ckp_이름", "ckp_늦음"]


def test_같은_시각이면_생성_순서로_결정한다(repo):
    _insert(repo, checkpoint_id="ckp_A", occurred_at=T1)
    _insert(repo, checkpoint_id="ckp_B", occurred_at=T1)
    ids = [row["checkpoint_id"] for row in repo.list_checkpoints(WORK)]
    assert ids == ["ckp_A", "ckp_B"]


def test_개수를_센다(repo):
    _insert(repo, checkpoint_id="ckp_A")
    _insert(repo, checkpoint_id="ckp_B")
    assert repo.count_checkpoints(WORK) == 2


def test_유형별_개수를_센다(repo):
    _insert(repo, checkpoint_id="ckp_A", ckp_type="ATTEMPT")
    _insert(repo, checkpoint_id="ckp_B", ckp_type="ATTEMPT")
    _insert(repo, checkpoint_id="ckp_C", ckp_type="RESULT")
    assert repo.count_types(WORK) == {"ATTEMPT": 2, "RESULT": 1}


def test_spool_에서_온_기록은_출처가_다르다(repo):
    _insert(repo, source="SPOOL")
    assert repo.get_checkpoint(CKP)["source"] == "SPOOL"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_checkpoint.py -v
```

Expected: FAIL — `AttributeError: 'Repository' object has no attribute 'insert_checkpoint'`

- [ ] **Step 3: `Repository`에 checkpoint 메서드를 추가한다**

파일 맨 위 import에 `import json`을 더한다. 클래스 끝에 이어 붙인다.

```python
    # ------------------------------------------------------------------
    # checkpoint
    # ------------------------------------------------------------------

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        return _as_dict(
            self._conn.execute(
                "SELECT * FROM checkpoint WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
        )

    def insert_checkpoint(
        self,
        *,
        checkpoint_id: str,
        work_id: str,
        machine_id: str,
        tool: str,
        type: str,
        title: str,
        body: str | None,
        body_truncated: bool,
        occurred_at: str,
        recorded_at: str,
        source: str,
        repo_path: str | None,
        repo_name: str | None,
        branch: str | None,
        commit_sha: str | None,
        dirty: bool | None,
        dirty_file_count: int | None,
        dirty_count_capped: bool,
        files: list[str] | None,
        error_excerpt: str | None,
        tags: list[str] | None,
    ) -> tuple[dict, bool]:
        """멱등이다. spool 을 두 번 흡수해도 중복이 생기지 않는다."""
        existing = self.get_checkpoint(checkpoint_id)
        if existing is not None:
            return existing, True

        self._conn.execute(
            "INSERT INTO checkpoint ("
            " checkpoint_id, work_id, machine_id, tool,"
            " type, title, body, body_truncated,"
            " occurred_at, recorded_at, source,"
            " repo_path, repo_name, branch, commit_sha,"
            " dirty, dirty_file_count, dirty_count_capped,"
            " files_json, error_excerpt, tags_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?)",
            (
                checkpoint_id, work_id, machine_id, tool,
                type, title, body, 1 if body_truncated else 0,
                occurred_at, recorded_at, source,
                repo_path, repo_name, branch, commit_sha,
                None if dirty is None else (1 if dirty else 0),
                dirty_file_count,
                1 if dirty_count_capped else 0,
                json.dumps(files or [], ensure_ascii=False),
                error_excerpt,
                json.dumps(tags or [], ensure_ascii=False),
                recorded_at,
            ),
        )
        return self.get_checkpoint(checkpoint_id), False

    def list_checkpoints(
        self, work_id: str, include_deleted: bool = False
    ) -> list[dict]:
        """발생 시각 오름차순. 순번을 두지 않고 시각으로 정렬한다."""
        condition = "" if include_deleted else " AND deleted_at IS NULL"
        rows = self._conn.execute(
            "SELECT * FROM checkpoint"
            f" WHERE work_id = ?{condition}"
            " ORDER BY occurred_at ASC, created_at ASC, checkpoint_id ASC",
            (work_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def count_checkpoints(self, work_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM checkpoint"
            " WHERE work_id = ? AND deleted_at IS NULL",
            (work_id,),
        ).fetchone()
        return int(row["c"])

    def count_types(self, work_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) AS c FROM checkpoint"
            " WHERE work_id = ? AND deleted_at IS NULL"
            " GROUP BY type",
            (work_id,),
        ).fetchall()
        return {row["type"]: int(row["c"]) for row in rows}
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_checkpoint.py -v
```

Expected: PASS — 9 passed

- [ ] **Step 5: 전체 테스트를 돌려 회귀가 없는지 본다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest -q
```

Expected: PASS — 56 passed

- [ ] **Step 6: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/store/repository.py tests/test_repository_checkpoint.py
git commit -m "feat: 리포지토리 checkpoint 쓰기와 조회"
```

---

## Task 7: 리포지토리 D — 날짜 조회와 삭제·복구

**Files:**
- Modify: `local/src/warruru_local/store/repository.py`
- Test: `local/tests/test_repository_query.py`

**Interfaces:**
- Consumes: Task 6의 `Repository`
- Produces: `Repository`에 다음 메서드
  - `list_works_between(start_iso: str, end_iso: str, include_deleted: bool = False) -> list[dict]` — `started_at` 기준, 내림차순
  - `list_deleted_works_between(start_iso: str, end_iso: str) -> list[dict]`
  - `soft_delete_work(work_id: str, now_iso: str) -> None`
  - `restore_work(work_id: str) -> None`
  - `soft_delete_checkpoint(checkpoint_id: str, now_iso: str) -> None`
  - `restore_checkpoint(checkpoint_id: str) -> None`
  - `list_deleted_checkpoints_between(start_iso: str, end_iso: str) -> list[dict]`
  - `latest_work_started_before(iso: str) -> str | None` — 기록이 있는 최근 날짜 링크용

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_repository_query.py`:

```python
import pytest

from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

DAY_START = "2026-07-22T00:00:00.000Z"
DAY_END = "2026-07-23T00:00:00.000Z"
T0 = "2026-07-21T23:00:00.000Z"
T1 = "2026-07-22T09:00:00.000Z"
T2 = "2026-07-22T10:00:00.000Z"
T9 = "2026-07-22T23:59:59.999Z"
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


@pytest.fixture
def repo(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, DAY_START)
    repository = Repository(conn)
    repository.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", DAY_START)
    repository.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", DAY_START)
    return repository


def _work(repo, work_id, started_at, tool="codex"):
    repo.insert_work(
        work_id=work_id, machine_id=MACHINE, client_instance_id=CLIENT, tool=tool,
        title="제목", title_origin="USER", goal=None, origin="EXPLICIT",
        started_at=started_at, repo_path="D:/x", repo_name="x", branch="main",
        commit_sha="aaa", now_iso=started_at,
    )


def _ckp(repo, checkpoint_id, work_id, occurred_at=T1):
    repo.insert_checkpoint(
        checkpoint_id=checkpoint_id, work_id=work_id, machine_id=MACHINE,
        tool="codex", type="NOTE", title="제목", body=None, body_truncated=False,
        occurred_at=occurred_at, recorded_at=occurred_at, source="MCP",
        repo_path=None, repo_name=None, branch=None, commit_sha=None,
        dirty=None, dirty_file_count=None, dirty_count_capped=False,
        files=None, error_excerpt=None, tags=None,
    )


def test_그_날짜의_작업만_준다(repo):
    _work(repo, "wrk_어제", T0)
    _work(repo, "wrk_오늘", T1)
    ids = [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_오늘"]


def test_경계_시각을_포함하고_다음날_시작은_뺀다(repo):
    _work(repo, "wrk_자정", DAY_START)
    _work(repo, "wrk_막차", T9)
    _work(repo, "wrk_내일", DAY_END)
    ids = {row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)}
    assert ids == {"wrk_자정", "wrk_막차"}


def test_시작_시각_내림차순으로_준다(repo):
    _work(repo, "wrk_이른", T1)
    _work(repo, "wrk_늦은", T2)
    ids = [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_늦은", "wrk_이른"]


def test_삭제한_작업은_기본_조회에서_빠진다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    assert repo.list_works_between(DAY_START, DAY_END) == []


def test_삭제한_작업은_삭제_목록에_나온다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    ids = [row["work_id"] for row in repo.list_deleted_works_between(DAY_START, DAY_END)]
    assert ids == ["wrk_A"]


def test_작업을_복구하면_다시_보인다(repo):
    _work(repo, "wrk_A", T1)
    repo.soft_delete_work("wrk_A", T2)
    repo.restore_work("wrk_A")
    assert [row["work_id"] for row in repo.list_works_between(DAY_START, DAY_END)] == ["wrk_A"]


def test_작업을_삭제해도_체크포인트_행은_남는다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_work("wrk_A", T2)
    assert repo.get_checkpoint("ckp_A")["deleted_at"] is None


def test_체크포인트를_삭제하면_목록에서_빠진다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    assert repo.list_checkpoints("wrk_A") == []
    assert len(repo.list_checkpoints("wrk_A", include_deleted=True)) == 1


def test_체크포인트를_복구하면_다시_보인다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    repo.restore_checkpoint("ckp_A")
    assert len(repo.list_checkpoints("wrk_A")) == 1


def test_삭제한_체크포인트는_삭제_목록에_나온다(repo):
    _work(repo, "wrk_A", T1)
    _ckp(repo, "ckp_A", "wrk_A")
    repo.soft_delete_checkpoint("ckp_A", T2)
    ids = [
        row["checkpoint_id"]
        for row in repo.list_deleted_checkpoints_between(DAY_START, DAY_END)
    ]
    assert ids == ["ckp_A"]


def test_기록이_있는_직전_시각을_찾는다(repo):
    _work(repo, "wrk_어제", T0)
    assert repo.latest_work_started_before(DAY_START) == T0


def test_직전_기록이_없으면_None_이다(repo):
    assert repo.latest_work_started_before(DAY_START) is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_query.py -v
```

Expected: FAIL — `AttributeError: 'Repository' object has no attribute 'list_works_between'`

- [ ] **Step 3: `Repository`에 조회와 삭제 메서드를 추가한다**

```python
    # ------------------------------------------------------------------
    # 날짜 조회
    # ------------------------------------------------------------------

    def list_works_between(
        self, start_iso: str, end_iso: str, include_deleted: bool = False
    ) -> list[dict]:
        """세션은 시작 시각 기준으로 그 날짜에 속한다. 끝 경계는 배타적이다."""
        condition = "" if include_deleted else " AND deleted_at IS NULL"
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            f" WHERE started_at >= ? AND started_at < ?{condition}"
            " ORDER BY started_at DESC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_deleted_works_between(self, start_iso: str, end_iso: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM work_session"
            " WHERE started_at >= ? AND started_at < ? AND deleted_at IS NOT NULL"
            " ORDER BY started_at DESC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_deleted_checkpoints_between(
        self, start_iso: str, end_iso: str
    ) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM checkpoint"
            " WHERE occurred_at >= ? AND occurred_at < ? AND deleted_at IS NOT NULL"
            " ORDER BY occurred_at ASC",
            (start_iso, end_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def latest_work_started_before(self, iso: str) -> str | None:
        row = self._conn.execute(
            "SELECT started_at FROM work_session"
            " WHERE started_at < ? AND deleted_at IS NULL"
            " ORDER BY started_at DESC LIMIT 1",
            (iso,),
        ).fetchone()
        return row["started_at"] if row is not None else None

    # ------------------------------------------------------------------
    # 삭제와 복구 — 물리 삭제하지 않는다
    # ------------------------------------------------------------------

    def soft_delete_work(self, work_id: str, now_iso: str) -> None:
        """하위 체크포인트 행은 건드리지 않는다. 조회가 상위 삭제를 함께 본다."""
        self._conn.execute(
            "UPDATE work_session SET deleted_at = ?, updated_at = ?"
            " WHERE work_id = ? AND deleted_at IS NULL",
            (now_iso, now_iso, work_id),
        )

    def restore_work(self, work_id: str) -> None:
        self._conn.execute(
            "UPDATE work_session SET deleted_at = NULL WHERE work_id = ?", (work_id,)
        )

    def soft_delete_checkpoint(self, checkpoint_id: str, now_iso: str) -> None:
        self._conn.execute(
            "UPDATE checkpoint SET deleted_at = ?"
            " WHERE checkpoint_id = ? AND deleted_at IS NULL",
            (now_iso, checkpoint_id),
        )

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        self._conn.execute(
            "UPDATE checkpoint SET deleted_at = NULL WHERE checkpoint_id = ?",
            (checkpoint_id,),
        )
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_repository_query.py -v
```

Expected: PASS — 12 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/store/repository.py tests/test_repository_query.py
git commit -m "feat: 리포지토리 날짜 조회와 소프트 삭제"
```

---

## Task 8: Git 스냅샷 수집기

**Files:**
- Create: `local/src/warruru_local/gitinfo.py`
- Test: `local/tests/test_gitinfo.py`

**Interfaces:**
- Consumes: `clock.Clock`
- Produces:
  - `gitinfo.GitSnapshot` (frozen dataclass): `repo_path: str | None`, `repo_name: str | None`, `branch: str | None`, `commit_sha: str | None`, `dirty: bool | None`, `dirty_file_count: int | None`, `dirty_count_capped: bool`
  - `GitSnapshot.EMPTY` — 전부 `None`, `dirty_count_capped=False`
  - `GitSnapshot.available -> bool` — `repo_path is not None`
  - `GitSnapshot.as_dict() -> dict | None` — 정보가 없으면 `None`. API 응답의 `git` 필드에 그대로 쓴다
  - `gitinfo.GitCollector(timeout_seconds: float = 2.0, cache_ttl_seconds: float = 5.0, dirty_file_cap: int = 500, monotonic=time.monotonic)`
  - `GitCollector.collect(path: str | None) -> GitSnapshot`

**주의:** subprocess 는 이 모듈이 독점한다. 셸을 거치지 않는다. 어떤 실패도 예외로 새어 나가지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_gitinfo.py`:

```python
import subprocess

import pytest

from warruru_local.gitinfo import GitCollector, GitSnapshot


def _run(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def git_repo(tmp_path):
    root = tmp_path / "sample-repo"
    root.mkdir()
    _run(root, "init", "-b", "main")
    _run(root, "config", "user.email", "test@example.com")
    _run(root, "config", "user.name", "Test")
    (root / "a.txt").write_text("hello", encoding="utf-8")
    _run(root, "add", "a.txt")
    _run(root, "commit", "-m", "first")
    return root


def test_저장소가_아니면_빈_스냅샷이다(tmp_path):
    snapshot = GitCollector().collect(str(tmp_path))
    assert snapshot.available is False
    assert snapshot.as_dict() is None


def test_경로가_None_이면_빈_스냅샷이다():
    assert GitCollector().collect(None).available is False


def test_없는_경로면_빈_스냅샷이다(tmp_path):
    assert GitCollector().collect(str(tmp_path / "없음")).available is False


def test_저장소면_브랜치와_커밋을_읽는다(git_repo):
    snapshot = GitCollector().collect(str(git_repo))
    assert snapshot.available is True
    assert snapshot.repo_name == "sample-repo"
    assert snapshot.branch == "main"
    assert len(snapshot.commit_sha) == 40
    assert snapshot.dirty is False
    assert snapshot.dirty_file_count == 0


def test_미커밋_변경이_있으면_dirty_다(git_repo):
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    snapshot = GitCollector().collect(str(git_repo))
    assert snapshot.dirty is True
    assert snapshot.dirty_file_count == 1


def test_변경_파일_수는_상한까지만_센다(git_repo):
    for index in range(5):
        (git_repo / f"f{index}.txt").write_text("x", encoding="utf-8")
    snapshot = GitCollector(dirty_file_cap=3).collect(str(git_repo))
    assert snapshot.dirty_file_count == 3
    assert snapshot.dirty_count_capped is True


def test_하위_디렉터리에서도_최상위를_찾는다(git_repo):
    nested = git_repo / "src" / "deep"
    nested.mkdir(parents=True)
    snapshot = GitCollector().collect(str(nested))
    assert snapshot.repo_name == "sample-repo"


def test_같은_경로는_캐시_동안_다시_읽지_않는다(git_repo):
    ticks = iter([0.0, 0.0, 1.0, 1.0])
    collector = GitCollector(cache_ttl_seconds=5.0, monotonic=lambda: next(ticks))
    first = collector.collect(str(git_repo))
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    second = collector.collect(str(git_repo))
    assert second.dirty == first.dirty is False


def test_캐시가_만료되면_다시_읽는다(git_repo):
    ticks = iter([0.0, 0.0, 99.0, 99.0])
    collector = GitCollector(cache_ttl_seconds=5.0, monotonic=lambda: next(ticks))
    collector.collect(str(git_repo))
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    assert collector.collect(str(git_repo)).dirty is True


def test_빈_스냅샷의_as_dict_는_None_이다():
    assert GitSnapshot.EMPTY.as_dict() is None


def test_스냅샷의_as_dict_는_API_필드_이름을_쓴다(git_repo):
    payload = GitCollector().collect(str(git_repo)).as_dict()
    assert set(payload) == {
        "repo_path", "repo_name", "branch", "commit", "dirty", "dirty_file_count",
    }
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_gitinfo.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.gitinfo'`

- [ ] **Step 3: `gitinfo.py`를 쓴다**

```python
"""Git 스냅샷. 부가 정보이지 기록의 조건이 아니다.

어떤 실패도 예외로 새어 나가지 않는다. 실패하면 값이 비어 있을 뿐이다.
플래그 대신 값의 유무로 표현한다 — 플래그와 값이 어긋날 여지를 없앤다.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_NO_WINDOW = 0
if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows 에서 콘솔 창이 뜨지 않게 한다
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW


@dataclass(frozen=True)
class GitSnapshot:
    repo_path: str | None = None
    repo_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    dirty: bool | None = None
    dirty_file_count: int | None = None
    dirty_count_capped: bool = False

    EMPTY: "GitSnapshot"

    @property
    def available(self) -> bool:
        return self.repo_path is not None

    def as_dict(self) -> dict | None:
        if not self.available:
            return None
        return {
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "commit": self.commit_sha,
            "dirty": self.dirty,
            "dirty_file_count": self.dirty_file_count,
        }


GitSnapshot.EMPTY = GitSnapshot()


class GitCollector:
    def __init__(
        self,
        timeout_seconds: float = 2.0,
        cache_ttl_seconds: float = 5.0,
        dirty_file_cap: int = 500,
        monotonic=time.monotonic,
    ) -> None:
        self._timeout = timeout_seconds
        self._ttl = cache_ttl_seconds
        self._cap = dirty_file_cap
        self._monotonic = monotonic
        self._cache: dict[str, tuple[float, GitSnapshot]] = {}

    def collect(self, path: str | None) -> GitSnapshot:
        if not path:
            return GitSnapshot.EMPTY
        if not Path(path).is_dir():
            return GitSnapshot.EMPTY

        now = self._monotonic()
        cached = self._cache.get(path)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]

        snapshot = self._read(path, now)
        self._cache[path] = (self._monotonic(), snapshot)
        return snapshot

    def _read(self, path: str, started: float) -> GitSnapshot:
        toplevel = self._git(path, "rev-parse", "--show-toplevel", started)
        if toplevel is None:
            return GitSnapshot.EMPTY

        branch = self._git(path, "rev-parse", "--abbrev-ref", "HEAD", started)
        commit = self._git(path, "rev-parse", "HEAD", started)
        dirty, count, capped = self._read_status(path, started)

        return GitSnapshot(
            repo_path=toplevel,
            repo_name=Path(toplevel).name,
            branch=branch,
            commit_sha=commit,
            dirty=dirty,
            dirty_file_count=count,
            dirty_count_capped=capped,
        )

    def _read_status(
        self, path: str, started: float
    ) -> tuple[bool | None, int | None, bool]:
        output = self._git(path, "status", "--porcelain", started, allow_empty=True)
        if output is None:
            return None, None, False
        lines = [line for line in output.splitlines() if line.strip()]
        if len(lines) > self._cap:
            return True, self._cap, True
        return bool(lines), len(lines), False

    def _remaining(self, started: float) -> float:
        return self._timeout - (self._monotonic() - started)

    def _git(
        self, path: str, *args: object, allow_empty: bool = False
    ) -> str | None:
        """마지막 위치 인자가 시작 시각이다. 남은 예산이 없으면 즉시 포기한다."""
        started = float(args[-1])
        command = [str(value) for value in args[:-1]]
        budget = self._remaining(started)
        if budget <= 0:
            return None
        try:
            completed = subprocess.run(
                ["git", "-C", path, *command],
                capture_output=True,
                text=True,
                timeout=budget,
                creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        value = completed.stdout.strip()
        if not value and not allow_empty:
            return None
        return value
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_gitinfo.py -v
```

Expected: PASS — 11 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/gitinfo.py tests/test_gitinfo.py
git commit -m "feat: Git 스냅샷 수집기와 경로 캐시"
```

---

## Task 9: 세션 귀속 규칙

기능 명세서 F-03을 그대로 옮긴다. **이 시스템에서 가장 틀리기 쉬운 부분이다.** 순수 규칙으로 두고 HTTP와 파일 시스템을 모르게 한다.

**Files:**
- Create: `local/src/warruru_local/session.py`
- Test: `local/tests/test_session_attach.py`

**Interfaces:**
- Consumes: `Repository`, `clock.Clock`, `gitinfo.GitSnapshot`, `config.Settings`, `ids.new_id`
- Produces:
  - `session.Attachment` (frozen dataclass): `work: dict`, `attached_by: str`
  - `session.SessionService(repo, clock, settings, id_factory=new_id)`
  - `SessionService.attach(*, work_id: str | None, client_instance_id: str | None, machine_id: str, tool: str, snapshot: GitSnapshot) -> Attachment`
  - `SessionService.start(*, work_id: str, client_instance_id: str | None, machine_id: str, tool: str, title: str | None, goal: str | None, snapshot: GitSnapshot, started_at: str | None = None) -> tuple[dict, bool]`
  - `SessionService.promote_title(work: dict, title: str) -> None`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_session_attach.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from warruru_local.clock import FixedClock, to_iso
from warruru_local.config import Settings
from warruru_local.gitinfo import GitSnapshot
from warruru_local.session import SessionService
from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
OTHER = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF5"
SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="aaa",
    dirty=False, dirty_file_count=0,
)


def _settings(tmp_path) -> Settings:
    return Settings(
        home=tmp_path, host="127.0.0.1", port=8787, token="t", tool=None,
        http_timeout_seconds=3.0, autostart_daemon=False,
        attach_window_minutes=90, idle_timeout_hours=4,
        sweep_interval_seconds=300, git_timeout_seconds=2.0,
        git_cache_ttl_seconds=5.0, git_dirty_file_cap=500,
        spool_quiet_seconds=10, log_level="INFO",
    )


@pytest.fixture
def service(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, to_iso(START))
    repo = Repository(conn)
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", to_iso(START))
    repo.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", to_iso(START))
    repo.ensure_client(OTHER, MACHINE, "codex", None, None, "D:/x", to_iso(START))
    clock = FixedClock(START)
    counter = iter(f"wrk_생성{index}" for index in range(100))
    made = SessionService(
        repo, clock, _settings(tmp_path), id_factory=lambda prefix: next(counter)
    )
    made.repo = repo
    made.clock = clock
    return made


def _attach(service, work_id=None, client=CLIENT, snapshot=SNAPSHOT):
    return service.attach(
        work_id=work_id, client_instance_id=client, machine_id=MACHINE,
        tool="codex", snapshot=snapshot,
    )


def test_요청에_식별자가_있으면_그_작업에_붙는다(service):
    work, _ = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, work_id="wrk_A")
    assert result.work["work_id"] == "wrk_A"
    assert result.attached_by == "REQUEST"


def test_없는_식별자를_주면_그_식별자로_만든다(service):
    result = _attach(service, work_id="wrk_늦게도착")
    assert result.work["work_id"] == "wrk_늦게도착"
    assert result.work["origin"] == "INFERRED"
    assert result.attached_by == "REQUEST"


def test_이미_마감된_작업에도_그대로_붙인다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    service.repo.finish_work(
        work_id="wrk_A", result=None, limitations=None, next_steps=None,
        ended_at=to_iso(START), repo_path=None, branch=None, commit_sha=None,
        now_iso=to_iso(START),
    )
    assert _attach(service, work_id="wrk_A").work["status"] == "FINISHED"


def test_식별자가_없으면_같은_대화의_진행중_작업에_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service)
    assert result.work["work_id"] == "wrk_A"
    assert result.attached_by == "CLIENT_INSTANCE"


def test_대화가_다르면_그_대화의_작업에_붙지_않는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=CLIENT)
    assert result.attached_by == "REPO_WINDOW"
    assert result.work["work_id"] == "wrk_A"


def test_대화가_없으면_저장소와_시간창으로_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=None)
    assert result.attached_by == "REPO_WINDOW"


def test_시간창을_넘기면_새_작업을_만든다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    service.clock.advance(timedelta(minutes=91).total_seconds())
    result = _attach(service, client=None)
    assert result.attached_by == "NEW"
    assert result.work["work_id"] == "wrk_생성0"


def test_저장소_정보가_없으면_시간창_규칙을_쓰지_않는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=OTHER, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    result = _attach(service, client=None, snapshot=GitSnapshot.EMPTY)
    assert result.attached_by == "NEW"


def test_아무것도_없으면_새_작업을_만들고_제목이_없다(service):
    result = _attach(service)
    assert result.attached_by == "NEW"
    assert result.work["origin"] == "INFERRED"
    assert result.work["title"] is None


def test_한_대화에_진행중이_여럿이면_가장_최근에_붙는다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="처음", goal=None, snapshot=SNAPSHOT,
    )
    service.clock.advance(60)
    service.start(
        work_id="wrk_B", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="나중", goal=None, snapshot=SNAPSHOT,
    )
    assert _attach(service).work["work_id"] == "wrk_B"


def test_start_는_명시적_세션을_만든다(service):
    work, duplicate = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="제목", goal="목표", snapshot=SNAPSHOT,
    )
    assert duplicate is False
    assert work["origin"] == "EXPLICIT"
    assert work["title_origin"] == "USER"
    assert work["start_commit"] == "aaa"


def test_start_를_두_번_부르면_기존_세션을_준다(service):
    service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="처음", goal=None, snapshot=SNAPSHOT,
    )
    work, duplicate = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="나중", goal=None, snapshot=SNAPSHOT,
    )
    assert duplicate is True
    assert work["title"] == "처음"


def test_제목이_없는_세션은_제목을_승격한다(service):
    result = _attach(service)
    service.promote_title(result.work, "첫 체크포인트")
    assert service.repo.get_work(result.work["work_id"])["title"] == "첫 체크포인트"


def test_제목이_있으면_승격하지_않는다(service):
    work, _ = service.start(
        work_id="wrk_A", client_instance_id=CLIENT, machine_id=MACHINE,
        tool="codex", title="원래 제목", goal=None, snapshot=SNAPSHOT,
    )
    service.promote_title(work, "덮어쓰기 시도")
    assert service.repo.get_work("wrk_A")["title"] == "원래 제목"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_session_attach.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.session'`

- [ ] **Step 3: `session.py`를 쓴다**

```python
"""세션 귀속과 마감. 순수 규칙이며 HTTP 와 파일 시스템을 모른다.

귀속 우선순위(기능 명세 F-03)
  1. 요청의 work_id
  2. 같은 대화의 진행 중 세션      <- 대화 하나 = 작업 하나. 가장 믿을 만한 신호
  3. 같은 머신·도구·저장소 + 시간창 <- 어댑터가 재기동되어 대화 식별자가 바뀐 경우
  4. 새 세션
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from warruru_local.clock import Clock, to_iso
from warruru_local.config import Settings
from warruru_local.gitinfo import GitSnapshot
from warruru_local.ids import new_id
from warruru_local.store.repository import Repository


@dataclass(frozen=True)
class Attachment:
    work: dict
    attached_by: str


class SessionService:
    def __init__(
        self,
        repo: Repository,
        clock: Clock,
        settings: Settings,
        id_factory=new_id,
    ) -> None:
        self.repo = repo
        self.clock = clock
        self.settings = settings
        self._id_factory = id_factory

    # ------------------------------------------------------------------

    def start(
        self,
        *,
        work_id: str,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        title: str | None,
        goal: str | None,
        snapshot: GitSnapshot,
        started_at: str | None = None,
    ) -> tuple[dict, bool]:
        now = started_at or to_iso(self.clock.now())
        return self.repo.insert_work(
            work_id=work_id,
            machine_id=machine_id,
            client_instance_id=client_instance_id,
            tool=tool,
            title=title,
            title_origin="USER" if title else None,
            goal=goal,
            origin="EXPLICIT",
            started_at=now,
            repo_path=snapshot.repo_path,
            repo_name=snapshot.repo_name,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )

    def attach(
        self,
        *,
        work_id: str | None,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        snapshot: GitSnapshot,
    ) -> Attachment:
        now = to_iso(self.clock.now())

        if work_id:
            existing = self.repo.get_work(work_id)
            if existing is None:
                existing = self._create(
                    work_id, client_instance_id, machine_id, tool, snapshot, now
                )
            return Attachment(existing, "REQUEST")

        if client_instance_id:
            found = self.repo.find_active_by_client(client_instance_id)
            if found is not None:
                return Attachment(found, "CLIENT_INSTANCE")

        if snapshot.repo_path:
            since = to_iso(
                self.clock.now()
                - timedelta(minutes=self.settings.attach_window_minutes)
            )
            found = self.repo.find_active_by_repo(
                machine_id, tool, snapshot.repo_path, since
            )
            if found is not None:
                return Attachment(found, "REPO_WINDOW")

        created = self._create(
            self._id_factory("wrk"), client_instance_id, machine_id, tool, snapshot, now
        )
        return Attachment(created, "NEW")

    def promote_title(self, work: dict, title: str) -> None:
        """제목이 없는 세션에만 붙는다. 리포지토리가 조건을 지킨다."""
        if work.get("title") is None:
            self.repo.set_work_title(work["work_id"], title)

    # ------------------------------------------------------------------

    def _create(
        self,
        work_id: str,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        snapshot: GitSnapshot,
        now: str,
    ) -> dict:
        work, _ = self.repo.insert_work(
            work_id=work_id,
            machine_id=machine_id,
            client_instance_id=client_instance_id,
            tool=tool,
            title=None,
            title_origin=None,
            goal=None,
            origin="INFERRED",
            started_at=now,
            repo_path=snapshot.repo_path,
            repo_name=snapshot.repo_name,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )
        return work
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_session_attach.py -v
```

Expected: PASS — 14 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/session.py tests/test_session_attach.py
git commit -m "feat: 세션 귀속 규칙"
```

---

## Task 10: 자동 마감

**Files:**
- Modify: `local/src/warruru_local/session.py`
- Test: `local/tests/test_session_close.py`

**Interfaces:**
- Consumes: Task 9의 `SessionService`
- Produces: `SessionService`에 다음 메서드
  - `sweep_idle() -> list[str]` — 마감한 `work_id` 목록
  - `close_client(client_instance_id: str) -> list[str]`
  - `finish(*, work_id: str | None, client_instance_id: str | None, result, limitations, next_steps, snapshot: GitSnapshot) -> dict | None` — 대상이 없으면 `None`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_session_close.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from warruru_local.clock import FixedClock, to_iso
from warruru_local.config import Settings
from warruru_local.gitinfo import GitSnapshot
from warruru_local.session import SessionService
from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
MACHINE = "mch_01K0W2H8N3ZK5T7QRDVXA6MFCY"
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="aaa",
    dirty=False, dirty_file_count=0,
)
END_SNAPSHOT = GitSnapshot(
    repo_path="D:/x", repo_name="x", branch="main", commit_sha="bbb",
    dirty=False, dirty_file_count=0,
)


def _settings(tmp_path) -> Settings:
    return Settings(
        home=tmp_path, host="127.0.0.1", port=8787, token="t", tool=None,
        http_timeout_seconds=3.0, autostart_daemon=False,
        attach_window_minutes=90, idle_timeout_hours=4,
        sweep_interval_seconds=300, git_timeout_seconds=2.0,
        git_cache_ttl_seconds=5.0, git_dirty_file_cap=500,
        spool_quiet_seconds=10, log_level="INFO",
    )


@pytest.fixture
def service(tmp_path):
    conn = db.connect(tmp_path / "warruru.db")
    migrations.migrate(conn, to_iso(START))
    repo = Repository(conn)
    repo.ensure_machine(MACHINE, "DESKTOP-A", "Windows 11", to_iso(START))
    repo.ensure_client(CLIENT, MACHINE, "codex", None, None, "D:/x", to_iso(START))
    return SessionService(repo, FixedClock(START), _settings(tmp_path))


def _start(service, work_id="wrk_A", client=CLIENT):
    work, _ = service.start(
        work_id=work_id, client_instance_id=client, machine_id=MACHINE,
        tool="codex", title="제목", goal=None, snapshot=SNAPSHOT,
    )
    return work


def test_유휴_제한_전에는_마감하지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=3).total_seconds())
    assert service.sweep_idle() == []
    assert service.repo.get_work("wrk_A")["status"] == "ACTIVE"


def test_유휴_제한을_넘기면_자동_마감한다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    assert service.sweep_idle() == ["wrk_A"]
    row = service.repo.get_work("wrk_A")
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "IDLE_TIMEOUT"


def test_자동_마감_시각은_마지막_활동_시각이다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.repo.get_work("wrk_A")["ended_at"] == to_iso(START)


def test_자동_마감은_종료_커밋을_남기지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.repo.get_work("wrk_A")["end_commit"] is None


def test_두_번_쓸어도_같은_작업을_다시_마감하지_않는다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    assert service.sweep_idle() == []


def test_대화가_끝나면_진행중_작업을_마감한다(service):
    _start(service, work_id="wrk_A")
    _start(service, work_id="wrk_B")
    closed = service.close_client(CLIENT)
    assert set(closed) == {"wrk_A", "wrk_B"}
    assert service.repo.get_work("wrk_A")["ended_reason"] == "CLIENT_EXIT"


def test_대화가_끝나면_대화_행에도_닫힌_시각이_남는다(service):
    _start(service)
    service.close_client(CLIENT)
    assert service.repo.get_client(CLIENT)["closed_at"] is not None


def test_진행중_작업이_없는_대화를_닫아도_터지지_않는다(service):
    assert service.close_client(CLIENT) == []


def test_마감하면_결과와_종료_커밋이_남는다(service):
    _start(service)
    service.clock.advance(600)
    row = service.finish(
        work_id="wrk_A", client_instance_id=CLIENT, result="됐다",
        limitations="한계", next_steps="다음", snapshot=END_SNAPSHOT,
    )
    assert row["status"] == "FINISHED"
    assert row["end_commit"] == "bbb"
    assert row["result"] == "됐다"


def test_식별자가_없으면_그_대화의_최근_작업을_마감한다(service):
    _start(service, work_id="wrk_A")
    service.clock.advance(60)
    _start(service, work_id="wrk_B")
    row = service.finish(
        work_id=None, client_instance_id=CLIENT, result=None, limitations=None,
        next_steps=None, snapshot=END_SNAPSHOT,
    )
    assert row["work_id"] == "wrk_B"


def test_마감할_작업이_없으면_None_이다(service):
    assert service.finish(
        work_id=None, client_instance_id=CLIENT, result=None, limitations=None,
        next_steps=None, snapshot=END_SNAPSHOT,
    ) is None


def test_자동_마감된_작업도_뒤늦게_마감할_수_있다(service):
    _start(service)
    service.clock.advance(timedelta(hours=5).total_seconds())
    service.sweep_idle()
    row = service.finish(
        work_id="wrk_A", client_instance_id=CLIENT, result="뒤늦은 결과",
        limitations=None, next_steps=None, snapshot=END_SNAPSHOT,
    )
    assert row["status"] == "FINISHED"
    assert row["ended_reason"] == "USER_FINISH"
    assert row["result"] == "뒤늦은 결과"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_session_close.py -v
```

Expected: FAIL — `AttributeError: 'SessionService' object has no attribute 'sweep_idle'`

- [ ] **Step 3: `SessionService`에 마감 메서드를 추가한다**

```python
    # ------------------------------------------------------------------
    # 마감
    # ------------------------------------------------------------------

    def sweep_idle(self) -> list[str]:
        """유휴 제한을 넘긴 진행 중 세션을 마감한다. 데몬 기동 직후에도 한 번 돈다."""
        now = self.clock.now()
        threshold = to_iso(now - timedelta(hours=self.settings.idle_timeout_hours))
        closed = []
        for row in self.repo.find_stale_active(threshold):
            self.repo.auto_close_work(
                row["work_id"],
                "IDLE_TIMEOUT",
                ended_at=row["last_activity_at"],
                now_iso=to_iso(now),
            )
            closed.append(row["work_id"])
        return closed

    def close_client(self, client_instance_id: str) -> list[str]:
        now = to_iso(self.clock.now())
        closed = []
        for row in self.repo.find_active_by_client_ids(client_instance_id):
            self.repo.auto_close_work(
                row["work_id"],
                "CLIENT_EXIT",
                ended_at=row["last_activity_at"],
                now_iso=now,
            )
            closed.append(row["work_id"])
        self.repo.close_client(client_instance_id, now)
        return closed

    def finish(
        self,
        *,
        work_id: str | None,
        client_instance_id: str | None,
        result: str | None,
        limitations: str | None,
        next_steps: str | None,
        snapshot: GitSnapshot,
    ) -> dict | None:
        """대상이 없으면 None 이다. 오류가 아니다."""
        target = work_id
        if target is None and client_instance_id:
            found = self.repo.find_active_by_client(client_instance_id)
            target = found["work_id"] if found is not None else None
        if target is None or self.repo.get_work(target) is None:
            return None

        now = to_iso(self.clock.now())
        return self.repo.finish_work(
            work_id=target,
            result=result,
            limitations=limitations,
            next_steps=next_steps,
            ended_at=now,
            repo_path=snapshot.repo_path,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_session_close.py -v
```

Expected: PASS — 12 passed

- [ ] **Step 5: 전체 테스트를 돌린다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest -q
```

Expected: PASS — 105 passed

- [ ] **Step 6: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/session.py tests/test_session_close.py
git commit -m "feat: 유휴 자동 마감·대화 종료 마감·사용자 마감"
```

---

## Task 11: 데몬 골격 — 단일 인스턴스 잠금, 인증, health

**Files:**
- Create: `local/src/warruru_local/daemon/__init__.py`, `local/src/warruru_local/daemon/lock.py`, `local/src/warruru_local/daemon/auth.py`, `local/src/warruru_local/daemon/app.py`
- Test: `local/tests/test_lock.py`, `local/tests/test_api_health.py`

**Interfaces:**
- Consumes: `config.Settings`, `db.connect`, `migrations.migrate`, `Repository`, `SessionService`, `GitCollector`, `clock`
- Produces:
  - `lock.SingleInstanceLock(path: Path)` — `acquire() -> bool`, `release() -> None`
  - `auth.require_token(request: Request) -> None` — FastAPI 의존성. 실패 시 401 `INVALID_TOKEN`
  - `app.AppContext` (dataclass): `settings`, `conn`, `repo`, `sessions`, `git`, `clock`, `machine_id`, `started_at`, `logger`
  - `app.create_app(settings: Settings, clock=None, start_background: bool = True) -> FastAPI` — `app.state.ctx`에 `AppContext`
  - `app.main() -> None` — 콘솔 스크립트 진입점
- 모든 오류 응답은 `{"error": {"code": ..., "message": ..., "detail": {...}}}` 형태다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_lock.py`:

```python
from warruru_local.daemon.lock import SingleInstanceLock


def test_처음_잠그면_성공한다(tmp_path):
    lock = SingleInstanceLock(tmp_path / "daemon.lock")
    assert lock.acquire() is True
    lock.release()


def test_이미_잠겨_있으면_실패한다(tmp_path):
    path = tmp_path / "daemon.lock"
    first = SingleInstanceLock(path)
    assert first.acquire() is True
    second = SingleInstanceLock(path)
    assert second.acquire() is False
    first.release()


def test_풀고_나면_다시_잠글_수_있다(tmp_path):
    path = tmp_path / "daemon.lock"
    first = SingleInstanceLock(path)
    first.acquire()
    first.release()
    assert SingleInstanceLock(path).acquire() is True


def test_풀기를_두_번_불러도_터지지_않는다(tmp_path):
    lock = SingleInstanceLock(tmp_path / "daemon.lock")
    lock.acquire()
    lock.release()
    lock.release()
```

`local/tests/test_api_health.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def test_health_는_토큰_없이도_열린다(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_는_스키마_버전과_머신을_알린다(client):
    payload = client.get("/v1/health").json()
    assert payload["schema_version"] == 1
    assert payload["machine_id"].startswith("mch_")
    assert payload["version"] == "0.1.0"


def test_토큰이_없으면_401_이다(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.post("/v1/works", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_토큰이_틀리면_401_이다(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as bare:
        response = bare.post(
            "/v1/works", json={}, headers={"X-Warruru-Token": "틀린값"}
        )
    assert response.status_code == 401


def test_기동하면_머신_행이_생긴다(client):
    machine_id = client.get("/v1/health").json()["machine_id"]
    row = client.app.state.ctx.repo._conn.execute(  # noqa: SLF001
        "SELECT * FROM machine WHERE machine_id = ?", (machine_id,)
    ).fetchone()
    assert row is not None
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_lock.py tests/test_api_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.daemon'`

- [ ] **Step 3: `daemon/__init__.py`와 `daemon/lock.py`를 쓴다**

`local/src/warruru_local/daemon/__init__.py`:

```python
```

(빈 파일이다.)

`local/src/warruru_local/daemon/lock.py`:

```python
"""단일 인스턴스 잠금. 잠금을 잡지 못한 데몬은 즉시 종료한다.

프로세스가 죽으면 OS 가 잠금을 자동으로 푼다. pid 파일만 쓰는 방식과 달리
남은 파일 때문에 기동이 막히는 일이 없다.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # POSIX
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # Windows
    import msvcrt

    _HAS_FCNTL = False


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+b")
        try:
            if _HAS_FCNTL:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if _HAS_FCNTL:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            else:
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self._handle.close()
        self._handle = None
```

**주의:** Windows 의 `msvcrt.locking` 은 파일 오프셋 기준으로 잠근다. 잠글 때와 풀 때 모두 `seek(0)` 을 해야 한다. 잠근 뒤 pid 를 쓰면 오프셋이 움직이므로, `release` 에서 다시 `seek(0)` 한다.

- [ ] **Step 4: `daemon/auth.py`를 쓴다**

```python
"""토큰 인증. /v1/health 를 제외한 모든 /v1 요청에 필요하다."""

from __future__ import annotations

from fastapi import HTTPException, Request

HEADER = "X-Warruru-Token"


def require_token(request: Request) -> None:
    expected = request.app.state.ctx.settings.token
    provided = request.headers.get(HEADER)
    if not provided or provided != expected:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "토큰이 없거나 올바르지 않습니다"},
        )
```

- [ ] **Step 5: `daemon/app.py`를 쓴다**

```python
"""데몬 조립. SQLite 의 유일한 writer 다."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from warruru_local import __version__, config, logging_setup, paths
from warruru_local.clock import Clock, SystemClock, to_iso
from warruru_local.gitinfo import GitCollector
from warruru_local.session import SessionService
from warruru_local.store import db, migrations
from warruru_local.store.repository import Repository


@dataclass
class AppContext:
    settings: config.Settings
    conn: object
    repo: Repository
    sessions: SessionService
    git: GitCollector
    clock: Clock
    machine_id: str
    started_at: str
    logger: logging.Logger


def _build_context(settings: config.Settings, clock: Clock) -> AppContext:
    paths.ensure_layout(settings.home)
    logger = logging_setup.setup_logging(settings.home, "daemon", settings.log_level)

    conn = db.connect(paths.db_path(settings.home))
    now = to_iso(clock.now())
    migrations.migrate(conn, now)

    repo = Repository(conn)
    machine = config.load_or_create_machine(settings.home)
    repo.ensure_machine(
        machine["machine_id"], machine["hostname"], machine["os"], machine["created_at"]
    )

    git = GitCollector(
        timeout_seconds=settings.git_timeout_seconds,
        cache_ttl_seconds=settings.git_cache_ttl_seconds,
        dirty_file_cap=settings.git_dirty_file_cap,
    )
    sessions = SessionService(repo, clock, settings)

    return AppContext(
        settings=settings,
        conn=conn,
        repo=repo,
        sessions=sessions,
        git=git,
        clock=clock,
        machine_id=machine["machine_id"],
        started_at=now,
        logger=logger,
    )


def create_app(
    settings: config.Settings,
    clock: Clock | None = None,
    start_background: bool = True,
) -> FastAPI:
    resolved_clock = clock or SystemClock()

    @contextlib.asynccontextmanager
    async def lifespan(instance: FastAPI):
        instance.state.ctx = _build_context(settings, resolved_clock)
        # 데몬이 몇 시간 꺼져 있었다면 그 사이 방치된 세션이 있다.
        instance.state.ctx.sessions.sweep_idle()
        stop = None
        if start_background:
            from warruru_local.daemon.sweeper import start_sweeper

            stop = start_sweeper(instance.state.ctx)
        yield
        if stop is not None:
            await stop()
        instance.state.ctx.conn.close()

    app = FastAPI(title="Warruru Local Daemon", version=__version__, lifespan=lifespan)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.ctx.logger.exception("처리하지 못한 오류")
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "STORAGE_ERROR", "message": str(exc), "detail": {}}
            },
        )

    @app.get("/v1/health")
    async def health(request: Request) -> dict:
        ctx = request.app.state.ctx
        return {
            "status": "ok",
            "version": __version__,
            "schema_version": migrations.CURRENT_VERSION,
            "machine_id": ctx.machine_id,
            "started_at": ctx.started_at,
        }

    from warruru_local.daemon import routes_api, routes_web

    app.include_router(routes_api.router)
    app.include_router(routes_web.router)
    return app


def main() -> None:
    import uvicorn

    from warruru_local.daemon.lock import SingleInstanceLock

    settings = config.load_settings()
    guard = SingleInstanceLock(paths.run_dir(settings.home) / "daemon.lock")
    if not guard.acquire():
        return  # 이미 다른 데몬이 돈다. 조용히 끝낸다.
    try:
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )
    finally:
        guard.release()
```

- [ ] **Step 6: 오류 형태를 통일하는 핸들러를 더한다**

`create_app` 안, `_unhandled` 바로 위에 넣는다. FastAPI 의 `HTTPException` 은 기본적으로 `{"detail": ...}` 을 내므로 명세서 형태로 바꾼다.

```python
    from fastapi.exceptions import HTTPException as FastAPIHTTPException

    @app.exception_handler(FastAPIHTTPException)
    async def _http_error(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
        payload = exc.detail
        if not isinstance(payload, dict):
            payload = {"code": "INVALID_REQUEST", "message": str(payload)}
        payload.setdefault("detail", {})
        return JSONResponse(status_code=exc.status_code, content={"error": payload})
```

- [ ] **Step 7: 아직 없는 모듈의 빈 껍데기를 만든다**

`create_app`이 `routes_api`, `routes_web`, `sweeper`를 부르므로 Task 12~17 전까지 임시로 비워 둔다.

`local/src/warruru_local/daemon/routes_api.py`:

```python
from fastapi import APIRouter

router = APIRouter()
```

`local/src/warruru_local/daemon/routes_web.py`:

```python
from fastapi import APIRouter

router = APIRouter()
```

`local/src/warruru_local/daemon/sweeper.py`:

```python
async def _noop() -> None:
    return None


def start_sweeper(ctx):
    return _noop
```

- [ ] **Step 8: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_lock.py tests/test_api_health.py -v
```

Expected: PASS — 9 passed

- [ ] **Step 9: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/daemon/ tests/test_lock.py tests/test_api_health.py
git commit -m "feat: 데몬 골격·단일 인스턴스 잠금·토큰 인증·health"
```

---

## Task 12: 기록 API

**Files:**
- Create: `local/src/warruru_local/daemon/models.py`, `local/src/warruru_local/daemon/recording.py`
- Modify: `local/src/warruru_local/daemon/routes_api.py`
- Test: `local/tests/test_api_record.py`

**Interfaces:**
- Consumes: Task 11의 `AppContext`, Task 9~10의 `SessionService`
- Produces: 다음 엔드포인트
  - `POST /v1/works`
  - `POST /v1/checkpoints`
  - `POST /v1/works/{work_id}/finish` — `work_id`가 `auto`면 대화 기준으로 고른다
  - `POST /v1/clients/{client_instance_id}/closed`
- `models.CHECKPOINT_TYPES: set[str]` — 허용 9종
- `recording.start_work(ctx, payload: dict) -> dict`
- `recording.record_checkpoint(ctx, payload: dict, source: str = "MCP") -> dict`
- `recording.finish_work(ctx, work_id: str | None, payload: dict) -> dict`

**배치 이유:** 기록 로직을 라우터가 아니라 `recording.py`에 둔다. Task 14의 spool 흡수가 HTTP를 거치지 않고 **같은 경로**를 써야 하기 때문이다. 라우터는 pydantic 모델을 `dict`로 바꿔 넘기는 것 말고는 하는 일이 없다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_api_record.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"

COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _start(client, work_id=WORK, title="제목"):
    return client.post(
        "/v1/works",
        json={"work_id": work_id, "title": title, "goal": "목표", **COMMON},
    )


def _checkpoint(client, checkpoint_id=CKP, work_id=None, ckp_type="PROBLEM", **extra):
    payload = {
        "checkpoint_id": checkpoint_id,
        "work_id": work_id,
        "type": ckp_type,
        "title": "체크포인트 제목",
        "body": "본문",
        **COMMON,
        **extra,
    }
    return client.post("/v1/checkpoints", json=payload)


def test_작업을_시작하면_200_이고_식별자를_돌려준다(client):
    response = _start(client)
    assert response.status_code == 200
    body = response.json()
    assert body["work_id"] == WORK
    assert body["duplicate"] is False


def test_같은_식별자로_두_번_시작하면_중복이라고_알린다(client):
    _start(client, title="처음")
    body = _start(client, title="나중").json()
    assert body["duplicate"] is True
    assert body["title"] == "처음"


def test_체크포인트를_기록하면_귀속_경로를_알려준다(client):
    _start(client)
    body = _checkpoint(client, work_id=WORK).json()
    assert body["work_id"] == WORK
    assert body["attached_by"] == "REQUEST"
    assert body["work_origin"] == "EXPLICIT"


def test_식별자를_빼면_같은_대화의_작업에_붙는다(client):
    _start(client)
    body = _checkpoint(client).json()
    assert body["work_id"] == WORK
    assert body["attached_by"] == "CLIENT_INSTANCE"


def test_작업_없이_체크포인트만_보내도_저장된다(client):
    body = _checkpoint(client).json()
    assert body["attached_by"] == "NEW"
    assert body["work_origin"] == "INFERRED"


def test_자동_생성된_세션은_첫_체크포인트_제목을_물려받는다(client):
    work_id = _checkpoint(client).json()["work_id"]
    row = client.app.state.ctx.repo.get_work(work_id)
    assert row["title"] == "체크포인트 제목"
    assert row["title_origin"] == "DERIVED"


def test_모르는_식별자를_주면_그_식별자로_세션을_만든다(client):
    body = _checkpoint(client, work_id="wrk_늦게도착").json()
    assert body["work_id"] == "wrk_늦게도착"
    assert body["work_origin"] == "INFERRED"


def test_같은_체크포인트를_두_번_보내면_중복이라고_알린다(client):
    _checkpoint(client, ckp_type="PROBLEM")
    body = _checkpoint(client, ckp_type="RESULT").json()
    assert body["duplicate"] is True


def test_모르는_유형은_NOTE_로_바꾸고_태그에_남긴다(client):
    body = _checkpoint(client, ckp_type="THINKING").json()
    row = client.app.state.ctx.repo.get_checkpoint(CKP)
    assert row["type"] == "NOTE"
    assert "type:THINKING" in row["tags_json"]
    assert body["duplicate"] is False


def test_긴_본문은_자르고_잘림을_표시한다(client):
    _checkpoint(client, body="가" * 70000)
    row = client.app.state.ctx.repo.get_checkpoint(CKP)
    assert len(row["body"]) == 65536
    assert row["body_truncated"] == 1


def test_제목이_필수다(client):
    response = client.post(
        "/v1/checkpoints",
        json={"checkpoint_id": CKP, "type": "NOTE", **COMMON},
    )
    assert response.status_code == 422


def test_마감하면_결과가_남는다(client):
    _start(client)
    _checkpoint(client, work_id=WORK)
    body = client.post(
        f"/v1/works/{WORK}/finish",
        json={"result": "됐다", "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] == WORK
    assert body["checkpoint_count"] == 1
    assert body["duration_seconds"] == 0


def test_auto_로_마감하면_대화의_최근_작업을_고른다(client):
    _start(client)
    body = client.post(
        "/v1/works/auto/finish",
        json={"result": None, "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] == WORK


def test_마감할_작업이_없으면_200_이고_사유를_준다(client):
    body = client.post(
        "/v1/works/auto/finish",
        json={"result": None, "limitations": None, "next_steps": None, **COMMON},
    ).json()
    assert body["work_id"] is None
    assert body["reason"] == "NO_ACTIVE_WORK"


def test_대화가_끝나면_진행중_작업이_자동_마감된다(client):
    _start(client)
    response = client.post(f"/v1/clients/{CLIENT}/closed")
    assert response.status_code == 200
    row = client.app.state.ctx.repo.get_work(WORK)
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "CLIENT_EXIT"


def test_없는_대화를_닫아도_200_이다(client):
    assert client.post("/v1/clients/cli_없음/closed").status_code == 200
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_api_record.py -v
```

Expected: FAIL — 404 Not Found (라우트가 없다)

- [ ] **Step 3: `daemon/models.py`를 쓴다**

```python
"""요청·응답 스키마. 상한을 넘는 값은 거절하지 않고 라우터에서 자른다."""

from __future__ import annotations

from pydantic import BaseModel

CHECKPOINT_TYPES = {
    "PROBLEM",
    "ATTEMPT",
    "FAILED_ATTEMPT",
    "ERROR",
    "TEST_RESULT",
    "DECISION",
    "RESULT",
    "LIMITATION",
    "NOTE",
}


class CommonFields(BaseModel):
    client_instance_id: str | None = None
    tool: str = "unknown"
    cwd: str | None = None
    client_name: str | None = None
    client_version: str | None = None


class StartWorkRequest(CommonFields):
    work_id: str
    title: str | None = None
    goal: str | None = None
    started_at: str | None = None
    repo_path: str | None = None


class CheckpointRequest(CommonFields):
    checkpoint_id: str
    work_id: str | None = None
    type: str
    title: str
    body: str | None = None
    files: list[str] | None = None
    error_excerpt: str | None = None
    tags: list[str] | None = None
    occurred_at: str | None = None
    repo_path: str | None = None


class FinishWorkRequest(CommonFields):
    result: str | None = None
    limitations: str | None = None
    next_steps: str | None = None
    ended_at: str | None = None
    repo_path: str | None = None
```

- [ ] **Step 4: `daemon/recording.py`를 쓴다**

기록 로직은 전부 여기 둔다. 라우터는 얇게 유지하고, Task 14 의 spool 흡수가 HTTP 를 거치지 않고 같은 경로를 쓰게 하기 위한 배치다. `Request` 대신 `ctx`를, pydantic 모델 대신 `dict`를 받는다.

`local/src/warruru_local/daemon/recording.py`:

```python
"""기록 로직. HTTP 와 spool 흡수가 같은 경로를 쓰도록 여기 모은다."""

from __future__ import annotations

from warruru_local import limits
from warruru_local.clock import parse_iso, to_iso
from warruru_local.daemon.models import CHECKPOINT_TYPES


def _register_client(ctx, payload: dict, now: str) -> None:
    client_instance_id = payload.get("client_instance_id")
    if not client_instance_id:
        return
    ctx.repo.ensure_client(
        client_instance_id,
        ctx.machine_id,
        payload.get("tool") or "unknown",
        payload.get("client_name"),
        payload.get("client_version"),
        payload.get("cwd"),
        now,
    )


def _snapshot(ctx, payload: dict):
    return ctx.git.collect(payload.get("repo_path") or payload.get("cwd"))


def start_work(ctx, payload: dict) -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    goal, _ = limits.clamp_text(payload.get("goal"), limits.TEXT_MAX)
    snapshot = _snapshot(ctx, payload)

    work, duplicate = ctx.sessions.start(
        work_id=payload["work_id"],
        client_instance_id=payload.get("client_instance_id"),
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        title=title,
        goal=goal,
        snapshot=snapshot,
        started_at=payload.get("started_at") or now,
    )
    return {
        "work_id": work["work_id"],
        "title": work["title"],
        "started_at": work["started_at"],
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
    }


def record_checkpoint(ctx, payload: dict, source: str = "MCP") -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    snapshot = _snapshot(ctx, payload)
    attachment = ctx.sessions.attach(
        work_id=payload.get("work_id"),
        client_instance_id=payload.get("client_instance_id"),
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        snapshot=snapshot,
    )
    work = attachment.work

    tags = limits.clamp_list(payload.get("tags"), limits.TAGS_MAX)
    raw_type = payload.get("type") or "NOTE"
    kind = raw_type.upper()
    if kind not in CHECKPOINT_TYPES:
        tags = [*tags, f"type:{raw_type}"][: limits.TAGS_MAX]
        kind = "NOTE"

    title, _ = limits.clamp_text(payload.get("title"), limits.TITLE_MAX)
    body, body_truncated = limits.clamp_text(payload.get("body"), limits.BODY_MAX)
    excerpt, _ = limits.clamp_text(
        payload.get("error_excerpt"), limits.ERROR_EXCERPT_MAX
    )

    row, duplicate = ctx.repo.insert_checkpoint(
        checkpoint_id=payload["checkpoint_id"],
        work_id=work["work_id"],
        machine_id=ctx.machine_id,
        tool=payload.get("tool") or "unknown",
        type=kind,
        title=title,
        body=body,
        body_truncated=body_truncated,
        occurred_at=payload.get("occurred_at") or now,
        recorded_at=now,
        source=source,
        repo_path=snapshot.repo_path,
        repo_name=snapshot.repo_name,
        branch=snapshot.branch,
        commit_sha=snapshot.commit_sha,
        dirty=snapshot.dirty,
        dirty_file_count=snapshot.dirty_file_count,
        dirty_count_capped=snapshot.dirty_count_capped,
        files=limits.clamp_list(payload.get("files"), limits.FILES_MAX),
        error_excerpt=excerpt,
        tags=tags,
    )

    if not duplicate:
        ctx.repo.touch_work(work["work_id"], now, snapshot.repo_path)
        ctx.sessions.promote_title(work, title)

    return {
        "checkpoint_id": row["checkpoint_id"],
        "work_id": work["work_id"],
        "work_origin": work["origin"],
        "attached_by": attachment.attached_by,
        "git": snapshot.as_dict(),
        "duplicate": duplicate,
    }


def finish_work(ctx, work_id: str | None, payload: dict) -> dict:
    now = to_iso(ctx.clock.now())
    _register_client(ctx, payload, now)

    snapshot = _snapshot(ctx, payload)
    result, _ = limits.clamp_text(payload.get("result"), limits.TEXT_MAX)
    limitations, _ = limits.clamp_text(payload.get("limitations"), limits.TEXT_MAX)
    next_steps, _ = limits.clamp_text(payload.get("next_steps"), limits.TEXT_MAX)

    work = ctx.sessions.finish(
        work_id=work_id,
        client_instance_id=payload.get("client_instance_id"),
        result=result,
        limitations=limitations,
        next_steps=next_steps,
        snapshot=snapshot,
    )
    if work is None:
        return {
            "work_id": None,
            "reason": "NO_ACTIVE_WORK",
            "ended_at": None,
            "checkpoint_count": 0,
            "duration_seconds": 0,
            "git": snapshot.as_dict(),
        }

    started = parse_iso(work["started_at"])
    ended = parse_iso(work["ended_at"])
    return {
        "work_id": work["work_id"],
        "reason": None,
        "ended_at": work["ended_at"],
        "checkpoint_count": ctx.repo.count_checkpoints(work["work_id"]),
        "duration_seconds": int((ended - started).total_seconds()),
        "git": snapshot.as_dict(),
    }
```

- [ ] **Step 5: `daemon/routes_api.py`를 쓴다**

라우터는 얇다. 판단은 `recording` 과 `SessionService` 에 있다.

```python
"""기록 API. 얇게 두고 판단은 recording 과 SessionService 에 맡긴다."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from warruru_local.daemon import recording
from warruru_local.daemon.auth import require_token
from warruru_local.daemon.models import (
    CheckpointRequest,
    FinishWorkRequest,
    StartWorkRequest,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


@router.post("/works")
async def start_work(request: Request, payload: StartWorkRequest) -> dict:
    return recording.start_work(request.app.state.ctx, payload.model_dump())


@router.post("/checkpoints")
async def record_checkpoint(request: Request, payload: CheckpointRequest) -> dict:
    return recording.record_checkpoint(request.app.state.ctx, payload.model_dump())


@router.post("/works/{work_id}/finish")
async def finish_work(
    request: Request, work_id: str, payload: FinishWorkRequest
) -> dict:
    target = None if work_id == "auto" else work_id
    return recording.finish_work(request.app.state.ctx, target, payload.model_dump())


@router.post("/clients/{client_instance_id}/closed")
async def close_client(request: Request, client_instance_id: str) -> dict:
    ctx = request.app.state.ctx
    return {"closed_work_ids": ctx.sessions.close_client(client_instance_id)}
```

- [ ] **Step 6: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_api_record.py -v
```

Expected: PASS — 16 passed

- [ ] **Step 7: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/daemon/models.py src/warruru_local/daemon/recording.py src/warruru_local/daemon/routes_api.py tests/test_api_record.py
git commit -m "feat: 기록 API — 작업 시작·체크포인트·마감·대화 종료"
```

---

## Task 13: 조회 API와 요약 마크다운

**Files:**
- Modify: `local/src/warruru_local/clock.py` (날짜 경계 헬퍼 추가)
- Create: `local/src/warruru_local/daemon/context.py`
- Modify: `local/src/warruru_local/daemon/routes_api.py` (`GET /v1/context` 추가)
- Test: `local/tests/test_context.py`

**Interfaces:**
- Consumes: Task 12의 라우터, `Repository`
- Produces:
  - `clock.local_day_bounds(date_str: str) -> tuple[str, str]` — 로컬 시간대 하루의 `[시작, 끝)` UTC ISO
  - `clock.local_date_of(iso: str) -> str` — UTC ISO를 로컬 `YYYY-MM-DD`로
  - `context.build_context(ctx, date_str: str, tool: str | None, limit: int) -> dict` — `date` / `summary_markdown` / `works`
  - `GET /v1/context?date=&tool=&limit=`
- `works[]` 항목: `work_id` `tool` `title` `status` `ended_reason` `started_at` `ended_at` `repo_name` `branch` `type_counts` `recent_checkpoints`(최대 5개, `type`/`title`/`occurred_at`)
- **본문은 담지 않는다.** 이 도구는 맥락 복원용이며 에이전트 컨텍스트를 잡아먹으면 안 된다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_context.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock, local_date_of, local_day_bounds
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _seed(client, work_id="wrk_A", tool="codex"):
    payload = dict(COMMON, tool=tool)
    client.post("/v1/works", json={"work_id": work_id, "title": "제목", **payload})
    for index, kind in enumerate(["PROBLEM", "ATTEMPT", "ATTEMPT", "RESULT"]):
        client.post(
            "/v1/checkpoints",
            json={
                "checkpoint_id": f"ckp_{work_id}_{index}",
                "work_id": work_id,
                "type": kind,
                "title": f"{kind} 제목",
                **payload,
            },
        )


def test_하루_경계는_로컬_시간대를_따른다():
    start, end = local_day_bounds("2026-07-22")
    assert local_date_of(start) == "2026-07-22"
    assert local_date_of(end) == "2026-07-23"
    assert start < end


def test_기록이_없으면_빈_목록과_안내를_준다(client):
    body = client.get("/v1/context", params={"date": "2020-01-01"}).json()
    assert body["works"] == []
    assert "기록 없음" in body["summary_markdown"]


def test_그_날짜의_작업을_준다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get("/v1/context", params={"date": today}).json()
    assert [work["work_id"] for work in body["works"]] == ["wrk_A"]


def test_유형별_개수를_센다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    work = client.get("/v1/context", params={"date": today}).json()["works"][0]
    assert work["type_counts"] == {"PROBLEM": 1, "ATTEMPT": 2, "RESULT": 1}


def test_최근_체크포인트는_다섯_개까지다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    work = client.get("/v1/context", params={"date": today}).json()["works"][0]
    assert len(work["recent_checkpoints"]) <= 5
    assert set(work["recent_checkpoints"][0]) == {"type", "title", "occurred_at"}


def test_본문은_담지_않는다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get("/v1/context", params={"date": today}).text
    assert "본문" not in body


def test_도구로_거를_수_있다(client):
    _seed(client, work_id="wrk_A", tool="codex")
    _seed(client, work_id="wrk_B", tool="claude-code")
    today = local_date_of("2026-07-22T08:00:00.000Z")
    body = client.get(
        "/v1/context", params={"date": today, "tool": "claude-code"}
    ).json()
    assert [work["work_id"] for work in body["works"]] == ["wrk_B"]


def test_상한을_넘기면_30개로_묶는다(client):
    today = local_date_of("2026-07-22T08:00:00.000Z")
    response = client.get("/v1/context", params={"date": today, "limit": 999})
    assert response.status_code == 200


def test_날짜를_빼면_오늘을_쓴다(client):
    _seed(client)
    body = client.get("/v1/context").json()
    assert body["date"] == local_date_of("2026-07-22T08:00:00.000Z")


def test_요약에_제목과_상태가_들어간다(client):
    _seed(client)
    today = local_date_of("2026-07-22T08:00:00.000Z")
    summary = client.get("/v1/context", params={"date": today}).json()[
        "summary_markdown"
    ]
    assert "제목" in summary
    assert "codex" in summary
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_context.py -v
```

Expected: FAIL — `ImportError: cannot import name 'local_day_bounds'`

- [ ] **Step 3: `clock.py`에 날짜 경계 헬퍼를 더한다**

파일 끝에 이어 붙인다. `date` 를 import 목록에 더한다.

```python
def local_day_bounds(date_str: str) -> tuple[str, str]:
    """로컬 시간대 하루의 [시작, 끝) 을 UTC ISO 로 준다. 끝은 배타적이다."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    local_zone = datetime.now().astimezone().tzinfo
    start = datetime(day.year, day.month, day.day, tzinfo=local_zone)
    return to_iso(start), to_iso(start + timedelta(days=1))


def local_date_of(iso: str) -> str:
    """UTC ISO 문자열을 로컬 시간대의 YYYY-MM-DD 로 바꾼다."""
    local_zone = datetime.now().astimezone().tzinfo
    return parse_iso(iso).astimezone(local_zone).strftime("%Y-%m-%d")
```

- [ ] **Step 4: `daemon/context.py`를 쓴다**

```python
"""맥락 조회. 에이전트가 그대로 읽는 요약과 구조화 목록을 함께 준다."""

from __future__ import annotations

from warruru_local.clock import local_date_of, local_day_bounds, to_iso

RECENT_LIMIT = 5
MAX_WORKS = 30


def build_context(ctx, date_str: str | None, tool: str | None, limit: int) -> dict:
    date_value = date_str or local_date_of(to_iso(ctx.clock.now()))
    start, end = local_day_bounds(date_value)
    capped = max(1, min(limit, MAX_WORKS))

    works = []
    for row in ctx.repo.list_works_between(start, end):
        if tool and row["tool"] != tool:
            continue
        works.append(_summarize(ctx, row))
        if len(works) >= capped:
            break

    return {
        "date": date_value,
        "summary_markdown": _render(date_value, works),
        "works": works,
    }


def _summarize(ctx, row: dict) -> dict:
    checkpoints = ctx.repo.list_checkpoints(row["work_id"])
    recent = [
        {
            "type": item["type"],
            "title": item["title"],
            "occurred_at": item["occurred_at"],
        }
        for item in checkpoints[-RECENT_LIMIT:]
    ]
    return {
        "work_id": row["work_id"],
        "tool": row["tool"],
        "title": row["title"],
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "repo_name": row["start_repo_name"],
        "branch": row["start_branch"],
        "type_counts": ctx.repo.count_types(row["work_id"]),
        "recent_checkpoints": recent,
    }


def _render(date_value: str, works: list[dict]) -> str:
    if not works:
        return f"# {date_value}\n\n기록 없음.\n"

    lines = [f"# {date_value}", ""]
    by_tool: dict[str, list[dict]] = {}
    for work in works:
        by_tool.setdefault(work["tool"], []).append(work)

    for tool_name, items in by_tool.items():
        lines.append(f"## {tool_name}")
        lines.append("")
        for work in items:
            title = work["title"] or "(제목 없음)"
            counts = " ".join(
                f"{name} {count}" for name, count in work["type_counts"].items()
            )
            lines.append(f"- **{title}** — {work['status']}")
            if work["repo_name"]:
                lines.append(f"  - {work['repo_name']} / {work['branch'] or '-'}")
            if counts:
                lines.append(f"  - {counts}")
            for item in work["recent_checkpoints"]:
                lines.append(f"  - {item['type']}: {item['title']}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 5: `routes_api.py`에 조회 라우트를 더한다**

파일 끝에 붙이고, 위쪽 import 에 `from warruru_local.daemon import context` 를 더한다.

```python
@router.get("/context")
async def get_context(
    request: Request,
    date: str | None = None,
    tool: str | None = None,
    limit: int = 10,
) -> dict:
    return context.build_context(request.app.state.ctx, date, tool, limit)
```

- [ ] **Step 6: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_context.py -v
```

Expected: PASS — 10 passed

- [ ] **Step 7: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/clock.py src/warruru_local/daemon/context.py src/warruru_local/daemon/routes_api.py tests/test_context.py
git commit -m "feat: 날짜 맥락 조회 API 와 요약 마크다운"
```

---

## Task 14: Spool 쓰기와 흡수

기록 무손실(NFR-01)을 실제로 보장하는 부분이다. 흡수는 HTTP 를 거치지 않고 Task 12 의 `recording.py` 를 직접 부른다. 정상 경로와 같은 코드를 쓰므로 귀속·제목 승격·멱등성이 저절로 따라온다.

**Files:**
- Create: `local/src/warruru_local/spool.py`, `local/src/warruru_local/daemon/absorb.py`
- Modify: `local/src/warruru_local/daemon/sweeper.py`, `local/src/warruru_local/daemon/app.py`
- Test: `local/tests/test_spool.py`, `local/tests/test_absorb.py`

**Interfaces:**
- Produces:
  - `spool.ENVELOPE_VERSION: int` (= 1)
  - `spool.spool_path(home: Path, client_instance_id: str) -> Path`
  - `spool.append(home: Path, client_instance_id: str, kind: str, payload: dict, enqueued_at: str, event_id: str) -> None`
  - `spool.read_envelopes(path: Path) -> list[dict]` — 깨진 줄은 건너뛴다
  - `absorb.absorb_all(ctx) -> int` — 반영한 봉투 수
  - `sweeper.start_sweeper(ctx) -> Callable[[], Awaitable[None]]`
- `kind` 허용값: `start_work` `record_checkpoint` `finish_work` `client_closed`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_spool.py`:

```python
from warruru_local import paths, spool

CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
NOW = "2026-07-22T09:00:00.000Z"


def test_봉투를_한_줄로_덧붙인다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "record_checkpoint", {"a": 1}, NOW, "evt_A")
    spool.append(home, CLIENT, "record_checkpoint", {"a": 2}, NOW, "evt_B")
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert [item["payload"]["a"] for item in envelopes] == [1, 2]


def test_봉투에_필요한_필드가_들어간다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "start_work", {"work_id": "wrk_A"}, NOW, "evt_A")
    envelope = spool.read_envelopes(spool.spool_path(home, CLIENT))[0]
    assert envelope["envelope_version"] == spool.ENVELOPE_VERSION
    assert envelope["event_id"] == "evt_A"
    assert envelope["kind"] == "start_work"
    assert envelope["enqueued_at"] == NOW


def test_대화마다_파일이_나뉜다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "start_work", {}, NOW, "evt_A")
    spool.append(home, "cli_다른대화", "start_work", {}, NOW, "evt_B")
    assert spool.spool_path(home, CLIENT) != spool.spool_path(home, "cli_다른대화")


def test_깨진_줄은_건너뛴다(home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    spool.append(home, CLIENT, "start_work", {"a": 1}, NOW, "evt_A")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("이건 JSON 이 아니다\n")
    spool.append(home, CLIENT, "start_work", {"a": 2}, NOW, "evt_B")
    assert len(spool.read_envelopes(target)) == 2


def test_빈_파일은_빈_목록이다(home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    target.write_text("", encoding="utf-8")
    assert spool.read_envelopes(target) == []


def test_한글_본문이_깨지지_않는다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "record_checkpoint", {"body": "한글 본문"}, NOW, "evt_A")
    envelope = spool.read_envelopes(spool.spool_path(home, CLIENT))[0]
    assert envelope["payload"]["body"] == "한글 본문"
```

`local/tests/test_absorb.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths, spool
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import absorb
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
WORK = "wrk_01K0X4M3F8QYB2N7VJ5RTZ9C6D"
CKP = "ckp_01K0X4M9A1WKD3PQ8HRG2VT5NE"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _age(home, seconds=60):
    """방금 쓴 파일을 조용해진 것으로 만든다."""
    import os
    import time

    for path in paths.spool_dir(home).glob("*.jsonl"):
        stamp = time.time() - seconds
        os.utime(path, (stamp, stamp))


def test_조용해진_파일만_흡수한다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    assert absorb.absorb_all(client.app.state.ctx) == 0  # 아직 쓰는 중일 수 있다
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1


def test_흡수한_기록의_출처는_SPOOL_이다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert client.app.state.ctx.repo.get_checkpoint(CKP)["source"] == "SPOOL"


def test_흡수한_파일은_absorbed_로_옮긴다(client, home):
    spool.append(home, CLIENT, "start_work",
                 {"work_id": WORK, "title": "제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert list(paths.spool_dir(home).glob("*.jsonl")) == []
    assert len(list(paths.absorbed_dir(home).glob("*.jsonl"))) == 1


def test_두_번_흡수해도_중복이_생기지_않는다(client, home):
    payload = {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON}
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    spool.append(home, CLIENT, "record_checkpoint", payload,
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    ctx = client.app.state.ctx
    work_id = ctx.repo.get_checkpoint(CKP)["work_id"]
    assert ctx.repo.count_checkpoints(work_id) == 1


def test_체크포인트가_start_work_보다_먼저_와도_붙는다(client, home):
    spool.append(
        home, CLIENT, "record_checkpoint",
        {"checkpoint_id": CKP, "work_id": WORK, "type": "NOTE", "title": "제목",
         **COMMON},
        "2026-07-22T09:00:00.000Z", "evt_A",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    ctx = client.app.state.ctx
    assert ctx.repo.get_work(WORK) is not None
    assert ctx.repo.get_checkpoint(CKP)["work_id"] == WORK


def test_봉투는_enqueue_시각_순으로_적용한다(client, home):
    spool.append(home, CLIENT, "record_checkpoint",
                 {"checkpoint_id": "ckp_늦음", "work_id": WORK, "type": "NOTE",
                  "title": "늦음", **COMMON},
                 "2026-07-22T10:00:00.000Z", "evt_B")
    spool.append(home, CLIENT, "start_work",
                 {"work_id": WORK, "title": "원래 제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert client.app.state.ctx.repo.get_work(WORK)["title"] == "원래 제목"


def test_깨진_봉투가_있어도_나머지를_반영한다(client, home):
    target = spool.spool_path(home, CLIENT)
    spool.append(home, CLIENT, "record_checkpoint",
                 {"checkpoint_id": CKP, "type": "NOTE", "title": "제목", **COMMON},
                 "2026-07-22T09:00:00.000Z", "evt_A")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("{깨짐\n")
    _age(home)
    assert absorb.absorb_all(client.app.state.ctx) == 1


def test_모르는_봉투_버전은_남겨_둔다(client, home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    target.write_text(
        '{"envelope_version": 99, "event_id": "evt_A", "kind": "start_work",'
        ' "enqueued_at": "2026-07-22T09:00:00.000Z", "payload": {}}\n',
        encoding="utf-8",
    )
    _age(home)
    absorb.absorb_all(client.app.state.ctx)
    assert target.exists()
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_spool.py tests/test_absorb.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.spool'`

- [ ] **Step 3: `spool.py`를 쓴다**

```python
"""데몬에 닿지 못한 요청을 보존한다. 어댑터가 쓰고 데몬이 흡수한다."""

from __future__ import annotations

import json
from pathlib import Path

from warruru_local import paths

ENVELOPE_VERSION = 1
KINDS = {"start_work", "record_checkpoint", "finish_work", "client_closed"}


def spool_path(home: Path, client_instance_id: str) -> Path:
    """대화마다 파일을 나눈다. 여러 어댑터가 같은 파일에 동시에 쓰지 않게 한다."""
    return paths.spool_dir(home) / f"{client_instance_id}.jsonl"


def append(
    home: Path,
    client_instance_id: str,
    kind: str,
    payload: dict,
    enqueued_at: str,
    event_id: str,
) -> None:
    target = spool_path(home, client_instance_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "envelope_version": ENVELOPE_VERSION,
        "event_id": event_id,
        "kind": kind,
        "enqueued_at": enqueued_at,
        "payload": payload,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def read_envelopes(path: Path) -> list[dict]:
    """깨진 줄은 건너뛴다. 한 줄이 깨졌다고 파일 전체를 버리지 않는다."""
    if not path.exists():
        return []
    envelopes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            envelopes.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return envelopes
```

- [ ] **Step 4: `daemon/absorb.py`를 쓴다**

```python
"""spool 흡수. 정상 경로와 같은 recording 함수를 쓴다."""

from __future__ import annotations

import time

from warruru_local import paths, spool
from warruru_local.clock import to_iso
from warruru_local.daemon import recording

_HANDLERS = {
    "start_work": lambda ctx, payload: recording.start_work(ctx, payload),
    "record_checkpoint": lambda ctx, payload: recording.record_checkpoint(
        ctx, payload, source="SPOOL"
    ),
    "finish_work": lambda ctx, payload: recording.finish_work(
        ctx, payload.get("work_id"), payload
    ),
    "client_closed": lambda ctx, payload: ctx.sessions.close_client(
        payload["client_instance_id"]
    ),
}


def absorb_all(ctx) -> int:
    """마지막 수정 후 조용해진 파일만 처리한다. 아직 쓰는 중일 수 있다."""
    home = ctx.settings.home
    quiet_before = time.time() - ctx.settings.spool_quiet_seconds
    applied = 0

    for path in sorted(paths.spool_dir(home).glob("*.jsonl")):
        if path.stat().st_mtime > quiet_before:
            continue

        envelopes = spool.read_envelopes(path)
        unknown = [
            item
            for item in envelopes
            if item.get("envelope_version") != spool.ENVELOPE_VERSION
        ]
        if unknown:
            ctx.logger.warning("모르는 봉투 버전이 있어 남겨 둔다: %s", path.name)
            continue

        for envelope in sorted(envelopes, key=lambda item: item.get("enqueued_at", "")):
            handler = _HANDLERS.get(envelope.get("kind"))
            if handler is None:
                ctx.logger.warning("모르는 봉투 종류: %s", envelope.get("kind"))
                continue
            try:
                handler(ctx, envelope.get("payload") or {})
                applied += 1
            except Exception:  # 한 봉투가 실패해도 나머지를 반영한다
                ctx.logger.exception("봉투를 반영하지 못했다: %s", envelope.get("event_id"))

        stamp = to_iso(ctx.clock.now()).replace(":", "").replace("-", "")
        target = paths.absorbed_dir(home) / f"{path.stem}.{stamp}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        path.replace(target)

    return applied
```

- [ ] **Step 5: `daemon/sweeper.py`를 실제 구현으로 바꾼다**

```python
"""주기 작업. 유휴 세션을 마감하고 spool 을 흡수한다."""

from __future__ import annotations

import asyncio

from warruru_local.daemon import absorb


def start_sweeper(ctx):
    interval = ctx.settings.sweep_interval_seconds

    async def loop() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                closed = ctx.sessions.sweep_idle()
                applied = absorb.absorb_all(ctx)
                if closed or applied:
                    ctx.logger.info("자동 마감 %d건, spool 반영 %d건", len(closed), applied)
            except Exception:
                ctx.logger.exception("주기 작업이 실패했다")

    task = asyncio.create_task(loop())

    async def stop() -> None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return stop
```

- [ ] **Step 6: 데몬 기동 시에도 흡수하도록 `app.py`를 고친다**

`lifespan` 안의 `sweep_idle()` 호출 바로 아래에 더한다.

```python
        from warruru_local.daemon import absorb

        absorb.absorb_all(instance.state.ctx)
```

- [ ] **Step 7: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_spool.py tests/test_absorb.py -v
```

Expected: PASS — 14 passed

- [ ] **Step 8: 전체 테스트를 돌린다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest -q
```

Expected: PASS — 154 passed

- [ ] **Step 9: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/spool.py src/warruru_local/daemon/ tests/test_spool.py tests/test_absorb.py
git commit -m "feat: spool 폴백 포맷과 데몬 흡수·주기 작업"
```

---

## Task 15: MCP 어댑터의 데몬 클라이언트

**Files:**
- Create: `local/src/warruru_local/mcp/__init__.py`, `local/src/warruru_local/mcp/client.py`
- Modify: `local/src/warruru_local/daemon/app.py` (`__main__` 진입 추가)
- Test: `local/tests/test_mcp_client.py`

**Interfaces:**
- Consumes: `config.Settings`, `spool`, `ids.new_id`, `clock`
- Produces:
  - `client.Outcome` (frozen dataclass): `body: dict | None`, `storage: str`, `message: str`
  - `client.DaemonClient(settings, client_instance_id, logger, clock, transport=None, spawner=None)`
  - `DaemonClient.send(kind: str, path: str, payload: dict) -> Outcome` — 기록 계열
  - `DaemonClient.query(path: str, params: dict) -> Outcome` — 조회. spool 폴백이 없다
  - `DaemonClient.close() -> Outcome`
- `transport`와 `spawner`는 테스트에서 갈아 끼우기 위한 것이다. 기본은 httpx 와 실제 프로세스 기동이다.

**폴백 규칙(기능 명세 F-08, 인터페이스 4.3)**

| 상황 | 처리 |
| --- | --- |
| 연결 실패 / 시간 초과 | 데몬 기동 1회 시도 → 재시도 → 실패하면 spool |
| 500 `STORAGE_ERROR` | spool |
| 503 `NOT_READY` | 재시도 1회 → 실패하면 spool |
| 400 / 401 | spool 하지 않는다. 재시도해도 같다 |

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_mcp_client.py`:

```python
from datetime import datetime, timezone

import httpx
import pytest

from warruru_local import spool
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.mcp.client import DaemonClient

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"


class FakeTransport:
    """응답 또는 예외를 순서대로 돌려준다."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append((method, url, json, params, headers, timeout))
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcomes_default()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def outcomes_default(self):
        return httpx.Response(200, json={"ok": True})


def _client(home, transport, spawned=None, logger=None):
    import logging

    settings = load_settings(home)
    return DaemonClient(
        settings,
        CLIENT,
        logger or logging.getLogger("test"),
        FixedClock(START),
        transport=transport,
        spawner=(spawned if spawned is not None else (lambda: False)),
    )


def test_정상이면_데몬_저장이다(home):
    transport = FakeTransport(httpx.Response(200, json={"work_id": "wrk_A"}))
    outcome = _client(home, transport).send("start_work", "/v1/works", {"a": 1})
    assert outcome.storage == "DAEMON"
    assert outcome.body["work_id"] == "wrk_A"


def test_토큰_헤더와_주소와_시간초과를_제대로_보낸다(home):
    transport = FakeTransport(httpx.Response(200, json={}))
    settings = load_settings(home)
    _client(home, transport).send("start_work", "/v1/works", {"a": 1})

    method, url, body, _, headers, timeout = transport.calls[0]
    assert method == "POST"
    assert url == f"http://{settings.host}:{settings.port}/v1/works"
    assert body == {"a": 1}
    assert headers["X-Warruru-Token"] == settings.token
    assert timeout == settings.http_timeout_seconds


def test_연결_실패면_기동을_시도하고_재시도한다(home):
    transport = FakeTransport(
        httpx.ConnectError("연결 불가"), httpx.Response(200, json={"ok": True})
    )
    spawned = []
    outcome = _client(
        home, transport, spawned=lambda: (spawned.append(1), True)[1]
    ).send("start_work", "/v1/works", {})
    assert spawned == [1]
    assert outcome.storage == "DAEMON"


def test_재시도도_실패하면_spool_에_남긴다(home):
    transport = FakeTransport(
        httpx.ConnectError("연결 불가"), httpx.ConnectError("연결 불가")
    )
    outcome = _client(home, transport).send("start_work", "/v1/works", {"a": 1})
    assert outcome.storage == "SPOOL"
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert envelopes[0]["kind"] == "start_work"
    assert envelopes[0]["payload"] == {"a": 1}


def test_시간_초과도_spool_로_간다(home):
    transport = FakeTransport(
        httpx.ReadTimeout("느림"), httpx.ReadTimeout("느림")
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "SPOOL"


def test_500_이면_spool_로_간다(home):
    transport = FakeTransport(
        httpx.Response(500, json={"error": {"code": "STORAGE_ERROR"}})
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "SPOOL"


def test_400_이면_spool_하지_않는다(home):
    transport = FakeTransport(
        httpx.Response(400, json={"error": {"code": "INVALID_REQUEST",
                                            "message": "type 은 필수입니다"}})
    )
    outcome = _client(home, transport).send("s", "/v1/works", {})
    assert outcome.storage == "DAEMON"
    assert outcome.body is None
    assert "type 은 필수입니다" in outcome.message
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []


def test_401_이면_spool_하지_않는다(home):
    transport = FakeTransport(
        httpx.Response(401, json={"error": {"code": "INVALID_TOKEN",
                                            "message": "토큰 오류"}})
    )
    outcome = _client(home, transport).send("s", "/v1/works", {})
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []
    assert outcome.storage == "DAEMON"


def test_503_이면_한_번_재시도한다(home):
    transport = FakeTransport(
        httpx.Response(503, json={"error": {"code": "NOT_READY"}}),
        httpx.Response(200, json={"ok": True}),
    )
    assert _client(home, transport).send("s", "/v1/works", {}).storage == "DAEMON"


def test_조회는_실패해도_spool_하지_않는다(home):
    transport = FakeTransport(httpx.ConnectError("연결 불가"),
                              httpx.ConnectError("연결 불가"))
    outcome = _client(home, transport).query("/v1/context", {"date": "2026-07-22"})
    assert outcome.storage == "NONE"
    assert outcome.body is None
    assert spool.read_envelopes(spool.spool_path(home, CLIENT)) == []


def test_기동은_한_번만_시도한다(home):
    transport = FakeTransport(
        httpx.ConnectError("x"), httpx.ConnectError("x"),
        httpx.ConnectError("x"), httpx.ConnectError("x"),
    )
    spawned = []
    made = _client(home, transport, spawned=lambda: (spawned.append(1), True)[1])
    made.send("s", "/v1/works", {})
    made.send("s", "/v1/works", {})
    assert len(spawned) == 1


def test_닫기는_client_closed_봉투를_남긴다(home):
    transport = FakeTransport(httpx.ConnectError("x"), httpx.ConnectError("x"))
    _client(home, transport).close()
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert envelopes[0]["kind"] == "client_closed"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_mcp_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'warruru_local.mcp'`

- [ ] **Step 3: `mcp/__init__.py`와 `mcp/client.py`를 쓴다**

`local/src/warruru_local/mcp/__init__.py`:

```python
```

(빈 파일이다.)

`local/src/warruru_local/mcp/client.py`:

```python
"""데몬 HTTP 클라이언트. 어댑터가 하는 유일한 판단은 '데몬에 닿았는가'다."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass

import httpx

from warruru_local import spool
from warruru_local.clock import Clock, to_iso
from warruru_local.config import Settings
from warruru_local.ids import new_id

SPAWN_WAIT_SECONDS = 3.0
SPAWN_POLL_SECONDS = 0.1
_NO_SPOOL_STATUSES = {400, 401, 404, 422}


@dataclass(frozen=True)
class Outcome:
    body: dict | None
    storage: str
    message: str


class _HttpxTransport:
    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        return httpx.request(
            method, url, json=json, params=params, headers=headers, timeout=timeout
        )


class DaemonClient:
    def __init__(
        self,
        settings: Settings,
        client_instance_id: str,
        logger: logging.Logger,
        clock: Clock,
        transport=None,
        spawner=None,
    ) -> None:
        self._settings = settings
        self._client_instance_id = client_instance_id
        self._logger = logger
        self._clock = clock
        self._transport = transport or _HttpxTransport()
        self._spawner = spawner or self._spawn_daemon
        self._spawn_tried = False

    # ------------------------------------------------------------------

    @property
    def _base(self) -> str:
        return f"http://{self._settings.host}:{self._settings.port}"

    @property
    def _headers(self) -> dict:
        return {"X-Warruru-Token": self._settings.token}

    def _call(self, method: str, path: str, json=None, params=None):
        return self._transport.request(
            method,
            f"{self._base}{path}",
            json=json,
            params=params,
            headers=self._headers,
            timeout=self._settings.http_timeout_seconds,
        )

    # ------------------------------------------------------------------

    def send(self, kind: str, path: str, payload: dict) -> Outcome:
        """기록 계열. 어떤 경우에도 기록을 잃지 않는다."""
        for attempt in (1, 2):
            try:
                response = self._call("POST", path, json=payload)
            except (httpx.TransportError, httpx.HTTPError) as error:
                self._logger.warning("데몬 호출 실패(%d회차): %s", attempt, error)
                if attempt == 1 and self._settings.autostart_daemon:
                    self._try_spawn()
                    continue
                break

            if response.status_code < 400:
                return Outcome(response.json(), "DAEMON", "기록했습니다.")

            if response.status_code in _NO_SPOOL_STATUSES:
                return Outcome(None, "DAEMON", _error_message(response))

            if response.status_code == 503 and attempt == 1:
                continue
            break

        return self._to_spool(kind, payload)

    def query(self, path: str, params: dict) -> Outcome:
        """조회. 폴백할 대상이 없다."""
        try:
            response = self._call("GET", path, params=params)
        except (httpx.TransportError, httpx.HTTPError):
            if self._settings.autostart_daemon:
                self._try_spawn()
            try:
                response = self._call("GET", path, params=params)
            except (httpx.TransportError, httpx.HTTPError) as error:
                return Outcome(None, "NONE", f"데몬에 연결하지 못했습니다: {error}")

        if response.status_code >= 400:
            return Outcome(None, "NONE", _error_message(response))
        return Outcome(response.json(), "DAEMON", "조회했습니다.")

    def close(self) -> Outcome:
        return self.send(
            "client_closed",
            f"/v1/clients/{self._client_instance_id}/closed",
            {"client_instance_id": self._client_instance_id},
        )

    # ------------------------------------------------------------------

    def _to_spool(self, kind: str, payload: dict) -> Outcome:
        spool.append(
            self._settings.home,
            self._client_instance_id,
            kind,
            payload,
            to_iso(self._clock.now()),
            new_id("evt"),
        )
        return Outcome(None, "SPOOL", "데몬에 닿지 못해 로컬에 보관했습니다. 나중에 반영됩니다.")

    def _try_spawn(self) -> None:
        if self._spawn_tried:
            return
        self._spawn_tried = True
        try:
            self._spawner()
        except Exception:
            self._logger.exception("데몬을 띄우지 못했다")

    def _spawn_daemon(self) -> bool:
        """어댑터와 분리해 띄운다. 에이전트가 종료돼도 데몬이 함께 죽으면 안 된다."""
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if hasattr(subprocess, "DETACHED_PROCESS"):  # Windows
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:  # POSIX
            kwargs["start_new_session"] = True

        subprocess.Popen(
            [sys.executable, "-m", "warruru_local.daemon.app"], **kwargs
        )

        deadline = time.monotonic() + SPAWN_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                if self._call("GET", "/v1/health").status_code == 200:
                    return True
            except (httpx.TransportError, httpx.HTTPError):
                pass
            time.sleep(SPAWN_POLL_SECONDS)
        return False


def _error_message(response) -> str:
    try:
        return response.json()["error"]["message"]
    except Exception:
        return f"데몬이 {response.status_code} 를 돌려주었습니다."
```

- [ ] **Step 4: `daemon/app.py`에 모듈 실행 진입을 더한다**

파일 끝에 붙인다. 어댑터가 `python -m warruru_local.daemon.app` 로 띄운다.

```python
if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_mcp_client.py -v
```

Expected: PASS — 12 passed

- [ ] **Step 6: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/mcp/ src/warruru_local/daemon/app.py tests/test_mcp_client.py
git commit -m "feat: 데몬 HTTP 클라이언트·자동 기동·spool 폴백"
```

---

## Task 16: MCP 서버 — 툴 4개

**Files:**
- Create: `local/src/warruru_local/mcp/server.py`
- Test: `local/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: Task 15의 `DaemonClient`
- Produces:
  - `server.ToolService(client: DaemonClient, tool: str, clock)` — 툴 4개의 순수 구현
  - `ToolService.start_work(title, goal=None, repo_path=None) -> dict`
  - `ToolService.record_checkpoint(type, title, body=None, work_id=None, files=None, error_excerpt=None, tags=None, occurred_at=None, repo_path=None) -> dict`
  - `ToolService.finish_work(work_id=None, result=None, limitations=None, next_steps=None) -> dict`
  - `ToolService.get_today_context(date=None, tool=None, limit=10) -> dict`
  - `server.build_server() -> FastMCP` — 서버 이름 `warruru-local`
  - `server.main() -> None`
- 모든 툴은 **예외를 던지지 않는다.** 공통 필드 `ok` / `storage` / `message` 를 반드시 담는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_mcp_tools.py`:

```python
from datetime import datetime, timezone

import pytest

from warruru_local.clock import FixedClock
from warruru_local.mcp.client import Outcome
from warruru_local.mcp.server import ToolService

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.sent = []
        self.queried = []

    def send(self, kind, path, payload):
        self.sent.append((kind, path, payload))
        return self.outcomes.pop(0) if self.outcomes else Outcome({}, "DAEMON", "ok")

    def query(self, path, params):
        self.queried.append((path, params))
        return self.outcomes.pop(0) if self.outcomes else Outcome({}, "DAEMON", "ok")


def _service(*outcomes):
    client = FakeClient(*outcomes)
    return ToolService(client, "codex", FixedClock(START)), client


def test_작업_시작은_식별자를_먼저_만든다():
    service, client = _service(
        Outcome({"work_id": "무시됨", "git": None}, "DAEMON", "ok")
    )
    result = service.start_work(title="제목", goal="목표")
    sent_payload = client.sent[0][2]
    assert result["work_id"] == sent_payload["work_id"]
    assert result["work_id"].startswith("wrk_")


def test_작업_시작_응답에_공통_필드가_있다():
    service, _ = _service()
    result = service.start_work(title="제목")
    assert result["ok"] is True
    assert result["storage"] == "DAEMON"
    assert isinstance(result["message"], str)


def test_데몬이_없으면_spool_이라고_알린다():
    service, _ = _service(Outcome(None, "SPOOL", "보관했습니다"))
    result = service.start_work(title="제목")
    assert result["ok"] is True
    assert result["storage"] == "SPOOL"
    assert result["work_id"].startswith("wrk_")


def test_잘못된_요청은_ok_가_False_다():
    service, _ = _service(Outcome(None, "DAEMON", "type 은 필수입니다"))
    result = service.record_checkpoint(type="NOTE", title="제목")
    assert result["ok"] is False
    assert "필수" in result["message"]


def test_체크포인트도_식별자를_먼저_만든다():
    service, client = _service()
    result = service.record_checkpoint(type="PROBLEM", title="제목")
    assert result["checkpoint_id"].startswith("ckp_")
    assert client.sent[0][2]["checkpoint_id"] == result["checkpoint_id"]


def test_체크포인트는_귀속_경로를_그대로_전달한다():
    service, _ = _service(
        Outcome(
            {"checkpoint_id": "ckp_A", "work_id": "wrk_A", "work_origin": "INFERRED",
             "attached_by": "CLIENT_INSTANCE", "git": None},
            "DAEMON", "ok",
        )
    )
    result = service.record_checkpoint(type="PROBLEM", title="제목")
    assert result["attached_by"] == "CLIENT_INSTANCE"
    assert result["work_origin"] == "INFERRED"


def test_발생_시각을_주지_않으면_지금으로_채운다():
    service, client = _service()
    service.record_checkpoint(type="NOTE", title="제목")
    assert client.sent[0][2]["occurred_at"] == "2026-07-22T08:00:00.000Z"


def test_마감은_auto_경로를_쓴다():
    service, client = _service()
    service.finish_work()
    assert client.sent[0][1] == "/v1/works/auto/finish"


def test_식별자를_주면_그_경로로_마감한다():
    service, client = _service()
    service.finish_work(work_id="wrk_A")
    assert client.sent[0][1] == "/v1/works/wrk_A/finish"


def test_마감할_작업이_없어도_ok_다():
    service, _ = _service(
        Outcome(
            {"work_id": None, "reason": "NO_ACTIVE_WORK", "ended_at": None,
             "checkpoint_count": 0, "duration_seconds": 0, "git": None},
            "DAEMON", "ok",
        )
    )
    result = service.finish_work()
    assert result["ok"] is True
    assert result["work_id"] is None
    assert "없" in result["message"]


def test_맥락_조회는_요약과_목록을_준다():
    service, _ = _service(
        Outcome(
            {"date": "2026-07-22", "summary_markdown": "# 요약", "works": []},
            "DAEMON", "ok",
        )
    )
    result = service.get_today_context()
    assert result["summary_markdown"] == "# 요약"
    assert result["works"] == []
    assert result["storage"] == "DAEMON"


def test_맥락_조회가_실패하면_storage_는_NONE_이다():
    service, _ = _service(Outcome(None, "NONE", "연결 실패"))
    result = service.get_today_context()
    assert result["ok"] is False
    assert result["storage"] == "NONE"
    assert result["works"] == []


def test_서버는_툴_네_개를_등록한다():
    import anyio

    from warruru_local.mcp.server import build_server

    server = build_server()
    names = {tool.name for tool in anyio.run(server.list_tools)}
    assert names == {
        "start_work", "record_checkpoint", "finish_work", "get_today_context",
    }
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_mcp_tools.py -v
```

Expected: FAIL — `ImportError: cannot import name 'ToolService'`

- [ ] **Step 3: `mcp/server.py`를 쓴다**

```python
"""MCP stdio 어댑터. 툴은 예외를 밖으로 던지지 않는다."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from warruru_local import config, logging_setup
from warruru_local.clock import Clock, SystemClock, to_iso
from warruru_local.ids import new_id
from warruru_local.mcp.client import DaemonClient, Outcome

SERVER_NAME = "warruru-local"


def _common(outcome: Outcome) -> dict:
    return {
        "ok": outcome.storage != "NONE" and not (
            outcome.storage == "DAEMON" and outcome.body is None
        ),
        "storage": outcome.storage,
        "message": outcome.message,
    }


class ToolService:
    """툴 4개의 순수 구현. FastMCP 와 분리해 테스트할 수 있게 둔다."""

    def __init__(self, client, tool: str, clock: Clock) -> None:
        self._client = client
        self._tool = tool
        self._clock = clock

    def _base(self, repo_path: str | None = None) -> dict:
        return {
            "client_instance_id": self._client._client_instance_id,  # noqa: SLF001
            "tool": self._tool,
            "cwd": os.getcwd(),
            "repo_path": repo_path,
        }

    def start_work(
        self, title: str, goal: str | None = None, repo_path: str | None = None
    ) -> dict:
        work_id = new_id("wrk")
        now = to_iso(self._clock.now())
        payload = {
            "work_id": work_id,
            "title": title,
            "goal": goal,
            "started_at": now,
            **self._base(repo_path),
        }
        outcome = self._client.send("start_work", "/v1/works", payload)
        body = outcome.body or {}
        return {
            "work_id": work_id,
            "started_at": body.get("started_at", now),
            "git": body.get("git"),
            **_common(outcome),
        }

    def record_checkpoint(
        self,
        type: str,
        title: str,
        body: str | None = None,
        work_id: str | None = None,
        files: list[str] | None = None,
        error_excerpt: str | None = None,
        tags: list[str] | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
    ) -> dict:
        checkpoint_id = new_id("ckp")
        payload = {
            "checkpoint_id": checkpoint_id,
            "work_id": work_id,
            "type": type,
            "title": title,
            "body": body,
            "files": files,
            "error_excerpt": error_excerpt,
            "tags": tags,
            "occurred_at": occurred_at or to_iso(self._clock.now()),
            **self._base(repo_path),
        }
        outcome = self._client.send("record_checkpoint", "/v1/checkpoints", payload)
        result = outcome.body or {}
        return {
            "checkpoint_id": checkpoint_id,
            "work_id": result.get("work_id", work_id),
            "work_origin": result.get("work_origin"),
            "attached_by": result.get("attached_by"),
            "git": result.get("git"),
            **_common(outcome),
        }

    def finish_work(
        self,
        work_id: str | None = None,
        result: str | None = None,
        limitations: str | None = None,
        next_steps: str | None = None,
    ) -> dict:
        payload = {
            "result": result,
            "limitations": limitations,
            "next_steps": next_steps,
            "ended_at": to_iso(self._clock.now()),
            **self._base(),
        }
        path = f"/v1/works/{work_id or 'auto'}/finish"
        outcome = self._client.send("finish_work", path, payload)
        body = outcome.body or {}
        common = _common(outcome)
        if body.get("reason") == "NO_ACTIVE_WORK":
            common["message"] = "마감할 작업이 없었습니다."
        return {
            "work_id": body.get("work_id"),
            "ended_at": body.get("ended_at"),
            "checkpoint_count": body.get("checkpoint_count", 0),
            "duration_seconds": body.get("duration_seconds", 0),
            "git": body.get("git"),
            **common,
        }

    def get_today_context(
        self, date: str | None = None, tool: str | None = None, limit: int = 10
    ) -> dict:
        params = {"limit": limit}
        if date:
            params["date"] = date
        if tool:
            params["tool"] = tool
        outcome = self._client.query("/v1/context", params)
        body = outcome.body or {}
        return {
            "date": body.get("date", date),
            "summary_markdown": body.get("summary_markdown", ""),
            "works": body.get("works", []),
            **_common(outcome),
        }


def _detect_tool(settings: config.Settings) -> str:
    return settings.tool or "unknown"


def build_server(service: ToolService | None = None) -> FastMCP:
    resolved = service or _build_service()
    server = FastMCP(SERVER_NAME)

    @server.tool()
    def start_work(
        title: str, goal: str | None = None, repo_path: str | None = None
    ) -> dict:
        """작업을 시작한다. 무엇을 하려는지 title 에 한 줄로 적는다."""
        try:
            return resolved.start_work(title=title, goal=goal, repo_path=repo_path)
        except Exception as error:  # 툴은 예외를 밖으로 던지지 않는다
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def record_checkpoint(
        type: str,
        title: str,
        body: str | None = None,
        work_id: str | None = None,
        files: list[str] | None = None,
        error_excerpt: str | None = None,
        tags: list[str] | None = None,
        occurred_at: str | None = None,
        repo_path: str | None = None,
    ) -> dict:
        """작업 중 의미 있는 순간을 기록한다.

        type: PROBLEM ATTEMPT FAILED_ATTEMPT ERROR TEST_RESULT
              DECISION RESULT LIMITATION NOTE
        """
        try:
            return resolved.record_checkpoint(
                type=type, title=title, body=body, work_id=work_id, files=files,
                error_excerpt=error_excerpt, tags=tags, occurred_at=occurred_at,
                repo_path=repo_path,
            )
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def finish_work(
        work_id: str | None = None,
        result: str | None = None,
        limitations: str | None = None,
        next_steps: str | None = None,
    ) -> dict:
        """작업을 마감한다. 결과와 남은 한계, 다음 작업을 적는다."""
        try:
            return resolved.finish_work(
                work_id=work_id, result=result, limitations=limitations,
                next_steps=next_steps,
            )
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"기록 실패: {error}"}

    @server.tool()
    def get_today_context(
        date: str | None = None, tool: str | None = None, limit: int = 10
    ) -> dict:
        """이 머신에서 오늘(또는 지정한 날짜) 기록한 작업 요약을 읽는다."""
        try:
            return resolved.get_today_context(date=date, tool=tool, limit=limit)
        except Exception as error:
            return {"ok": False, "storage": "NONE", "message": f"조회 실패: {error}"}

    return server


def _build_service() -> ToolService:
    settings = config.load_settings()
    logger = logging_setup.setup_logging(settings.home, "mcp", settings.log_level)
    clock = SystemClock()
    client = DaemonClient(settings, new_id("cli"), logger, clock)
    return ToolService(client, _detect_tool(settings), clock)


def main() -> None:
    service = _build_service()
    build_server(service).run("stdio")
    # 표준 입력이 닫히면 대화가 끝난 것이다. 진행 중 세션을 마감하게 알린다.
    try:
        service._client.close()  # noqa: SLF001
    except Exception:
        logging.getLogger("warruru.mcp").exception("대화 종료를 알리지 못했다")
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_mcp_tools.py -v
```

Expected: PASS — 13 passed

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/mcp/server.py tests/test_mcp_tools.py
git commit -m "feat: MCP 툴 4개 — start_work·record_checkpoint·finish_work·get_today_context"
```

---

## Task 17: Today 화면

**Files:**
- Create: `local/src/warruru_local/daemon/dayview.py`
- Create: `local/src/warruru_local/daemon/templates/base.html`, `local/src/warruru_local/daemon/templates/day.html`
- Modify: `local/src/warruru_local/daemon/routes_web.py`
- Test: `local/tests/test_web.py`

**Interfaces:**
- Consumes: `Repository`, `clock.local_day_bounds`, `clock.local_date_of`
- Produces:
  - `dayview.build_day(ctx, date_str: str) -> dict` — `date` `prev_date` `next_date` `groups` `empty_hint`
  - `groups`: `[{"tool": str, "works": [work_view, ...]}, ...]`
  - `work_view`: `work_id` `title` `status` `ended_reason` `started_local` `ended_local` `repo_name` `branch` `type_counts` `checkpoints`
  - `checkpoint_view`: `checkpoint_id` `type` `title` `body` `occurred_local` `repo_name` `branch` `commit_short` `dirty` `files` `error_excerpt` `tags`
  - `GET /` → 오늘로 302
  - `GET /d/{date}` → HTML

**표시 규칙(기능 명세 F-10)**
- 날짜 경계는 로컬 시간대. 세션은 **시작 시각** 기준으로 그 날짜에 속한다.
- 도구별로 묶고, 도구 안에서는 시작 시각 내림차순.
- 체크포인트는 발생 시각 오름차순.
- 본문은 **원문 그대로 줄바꿈을 보존**해 표시한다. Markdown 을 렌더링하지 않는다.
- Git 정보가 없으면 없다고 표시한다. 빈칸으로 두지 않는다.
- 기록이 없는 날짜는 문장으로 알리고, 기록이 있는 최근 날짜 링크를 준다.
- 서버 렌더링이며 자바스크립트 프레임워크와 외부 CDN 을 쓰지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_web.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock, local_date_of
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
TODAY = local_date_of("2026-07-22T08:00:00.000Z")
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _seed(client, work_id="wrk_A", tool="codex", title="작업 제목"):
    payload = dict(COMMON, tool=tool)
    client.post("/v1/works", json={"work_id": work_id, "title": title, **payload})
    client.post(
        "/v1/checkpoints",
        json={
            "checkpoint_id": f"ckp_{work_id}",
            "work_id": work_id,
            "type": "FAILED_ATTEMPT",
            "title": "체크포인트 제목",
            "body": "첫 줄\n둘째 줄",
            **payload,
        },
    )


def test_루트는_오늘로_보낸다(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == f"/d/{TODAY}"


def test_날짜_화면이_열린다(client):
    response = client.get(f"/d/{TODAY}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_작업_제목과_상태가_보인다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "작업 제목" in body
    assert "ACTIVE" in body


def test_도구별로_묶여_보인다(client):
    _seed(client, work_id="wrk_A", tool="codex")
    _seed(client, work_id="wrk_B", tool="claude-code")
    body = client.get(f"/d/{TODAY}").text
    assert "codex" in body
    assert "claude-code" in body


def test_체크포인트_유형과_제목이_보인다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "FAILED_ATTEMPT" in body
    assert "체크포인트 제목" in body


def test_본문의_줄바꿈이_보존된다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "첫 줄\n둘째 줄" in body


def test_기록이_없는_날짜는_비어_있다고_알린다(client):
    body = client.get("/d/2020-01-01").text
    assert "기록이 없습니다" in body


def test_기록이_없으면_최근_날짜_링크를_준다(client):
    _seed(client)
    body = client.get("/d/2030-01-01").text
    assert f"/d/{TODAY}" in body


def test_이전과_다음_날짜_링크가_있다(client):
    body = client.get("/d/2026-07-22").text
    assert "/d/2026-07-21" in body
    assert "/d/2026-07-23" in body


def test_Git_정보가_없으면_없다고_표시한다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "Git 정보 없음" in body


def test_잘못된_날짜_형식은_400_이다(client):
    assert client.get("/d/2026-7-22").status_code == 400


def test_화면은_외부_주소를_불러오지_않는다(client):
    _seed(client)
    body = client.get(f"/d/{TODAY}").text
    assert "http://" not in body.replace('http://127.0.0.1', '')
    assert "https://" not in body
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_web.py -v
```

Expected: FAIL — 404 Not Found

- [ ] **Step 3: `daemon/dayview.py`를 쓴다**

```python
"""날짜 화면의 표시 모델. 템플릿은 판단하지 않는다."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from warruru_local.clock import local_date_of, local_day_bounds, parse_iso

DATE_FORMAT = "%Y-%m-%d"


def _local_time(iso: str | None) -> str | None:
    if iso is None:
        return None
    local_zone = datetime.now().astimezone().tzinfo
    return parse_iso(iso).astimezone(local_zone).strftime("%H:%M")


def _loads(raw: str | None) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _checkpoint_view(row: dict) -> dict:
    return {
        "checkpoint_id": row["checkpoint_id"],
        "type": row["type"],
        "title": row["title"],
        "body": row["body"],
        "occurred_local": _local_time(row["occurred_at"]),
        "repo_name": row["repo_name"],
        "branch": row["branch"],
        "commit_short": (row["commit_sha"] or "")[:7] or None,
        "dirty": row["dirty"],
        "files": _loads(row["files_json"]),
        "error_excerpt": row["error_excerpt"],
        "tags": _loads(row["tags_json"]),
    }


def _work_view(ctx, row: dict, include_deleted: bool) -> dict:
    checkpoints = ctx.repo.list_checkpoints(row["work_id"], include_deleted)
    return {
        "work_id": row["work_id"],
        "title": row["title"] or "(제목 없음)",
        "title_origin": row["title_origin"],
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "origin": row["origin"],
        "started_local": _local_time(row["started_at"]),
        "ended_local": _local_time(row["ended_at"]),
        "repo_name": row["start_repo_name"],
        "branch": row["start_branch"],
        "result": row["result"],
        "limitations": row["limitations"],
        "next_steps": row["next_steps"],
        "type_counts": ctx.repo.count_types(row["work_id"]),
        "checkpoints": [_checkpoint_view(item) for item in checkpoints],
    }


def _group(views: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for tool, view in views:
        if tool not in groups:
            groups[tool] = []
            order.append(tool)
        groups[tool].append(view)
    return [{"tool": tool, "works": groups[tool]} for tool in order]


def build_day(ctx, date_str: str, include_deleted: bool = False) -> dict:
    start, end = local_day_bounds(date_str)
    rows = (
        ctx.repo.list_deleted_works_between(start, end)
        if include_deleted
        else ctx.repo.list_works_between(start, end)
    )
    views = [(row["tool"], _work_view(ctx, row, include_deleted)) for row in rows]

    day = datetime.strptime(date_str, DATE_FORMAT).date()
    hint = None
    if not views and not include_deleted:
        latest = ctx.repo.latest_work_started_before(end)
        hint = local_date_of(latest) if latest else None

    return {
        "date": date_str,
        "prev_date": (day - timedelta(days=1)).strftime(DATE_FORMAT),
        "next_date": (day + timedelta(days=1)).strftime(DATE_FORMAT),
        "groups": _group(views),
        "empty_hint": hint,
    }
```

- [ ] **Step 4: 템플릿을 쓴다**

`local/src/warruru_local/daemon/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Warruru Local{% endblock %}</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 1.5rem; line-height: 1.6; }
  header { display: flex; gap: 1rem; align-items: baseline;
           flex-wrap: wrap; margin-bottom: 1.5rem; }
  h1 { font-size: 1.4rem; margin: 0; }
  nav a { margin-right: .75rem; }
  .tool { border: 1px solid currentColor; border-radius: 8px;
          padding: 1rem; margin-bottom: 1.25rem; }
  .tool > h2 { margin: 0 0 .75rem; font-size: 1.1rem; }
  .work { border-top: 1px solid currentColor; padding: .75rem 0; }
  .work:first-of-type { border-top: none; }
  .work-head { display: flex; gap: .5rem; align-items: baseline;
               flex-wrap: wrap; }
  .work-head strong { font-size: 1rem; }
  .badge { font-size: .75rem; border: 1px solid currentColor;
           border-radius: 4px; padding: 0 .35rem; }
  .meta { font-size: .8rem; opacity: .75; }
  ul.checkpoints { list-style: none; margin: .5rem 0 0; padding: 0; }
  ul.checkpoints > li { padding: .4rem 0 .4rem .75rem;
                        border-left: 2px solid currentColor; margin-bottom: .3rem; }
  pre.body { white-space: pre-wrap; word-break: break-word;
             margin: .3rem 0 0; font-size: .85rem; }
  form.inline { display: inline; }
  button { font: inherit; cursor: pointer; }
  .empty { opacity: .8; }
</style>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>
```

`local/src/warruru_local/daemon/templates/day.html`:

```html
{% extends "base.html" %}
{% block title %}{{ view.date }} — Warruru Local{% endblock %}
{% block content %}
<header>
  <h1>{{ view.date }}</h1>
  <nav>
    <a href="/d/{{ view.prev_date }}">◀ 이전</a>
    <a href="/d/{{ view.next_date }}">다음 ▶</a>
    <a href="/d/{{ view.date }}?deleted=1">삭제 항목 보기</a>
  </nav>
</header>

{% if not view.groups %}
  <p class="empty">이 날짜에는 기록이 없습니다.</p>
  {% if view.empty_hint %}
    <p class="empty">가장 최근 기록은
      <a href="/d/{{ view.empty_hint }}">{{ view.empty_hint }}</a>에 있습니다.</p>
  {% endif %}
{% endif %}

{% for group in view.groups %}
<section class="tool">
  <h2>{{ group.tool }}</h2>
  {% for work in group.works %}
  <article class="work">
    <div class="work-head">
      <strong>{{ work.title }}</strong>
      <span class="badge">{{ work.status }}</span>
      {% if work.ended_reason %}<span class="badge">{{ work.ended_reason }}</span>{% endif %}
      {% if work.origin == "INFERRED" %}<span class="badge">자동 연결</span>{% endif %}
      <form class="inline" method="post" action="/web/works/{{ work.work_id }}/delete">
        <input type="hidden" name="_token" value="{{ token }}">
        <input type="hidden" name="date" value="{{ view.date }}">
        <button type="submit">삭제</button>
      </form>
    </div>
    <div class="meta">
      {{ work.started_local }}{% if work.ended_local %} – {{ work.ended_local }}{% endif %}
      ·
      {% if work.repo_name %}{{ work.repo_name }} / {{ work.branch or "-" }}
      {% else %}Git 정보 없음{% endif %}
      {% if work.type_counts %}
        · {% for name, count in work.type_counts.items() %}{{ name }} {{ count }} {% endfor %}
      {% endif %}
    </div>
    {% if work.result %}<div class="meta">결과: {{ work.result }}</div>{% endif %}
    {% if work.limitations %}<div class="meta">한계: {{ work.limitations }}</div>{% endif %}
    {% if work.next_steps %}<div class="meta">다음: {{ work.next_steps }}</div>{% endif %}

    <ul class="checkpoints">
      {% for item in work.checkpoints %}
      <li>
        <div class="work-head">
          <span class="meta">{{ item.occurred_local }}</span>
          <span class="badge">{{ item.type }}</span>
          <span>{{ item.title }}</span>
          <form class="inline" method="post"
                action="/web/checkpoints/{{ item.checkpoint_id }}/delete">
            <input type="hidden" name="_token" value="{{ token }}">
            <input type="hidden" name="date" value="{{ view.date }}">
            <button type="submit">삭제</button>
          </form>
        </div>
        {% if item.body %}<pre class="body">{{ item.body }}</pre>{% endif %}
        {% if item.error_excerpt %}<pre class="body">{{ item.error_excerpt }}</pre>{% endif %}
        <div class="meta">
          {% if item.repo_name %}
            {{ item.repo_name }} / {{ item.branch or "-" }}
            {% if item.commit_short %} @ {{ item.commit_short }}{% endif %}
            {% if item.dirty %} · 미커밋 변경 있음{% endif %}
          {% else %}Git 정보 없음{% endif %}
          {% if item.files %} · {{ item.files | join(", ") }}{% endif %}
          {% if item.tags %} · {{ item.tags | join(" ") }}{% endif %}
        </div>
      </li>
      {% endfor %}
    </ul>
  </article>
  {% endfor %}
</section>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: `daemon/routes_web.py`를 쓴다**

```python
"""화면. 조회는 토큰이 필요 없고, 상태를 바꾸는 요청만 토큰을 요구한다."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from warruru_local.clock import local_date_of, to_iso
from warruru_local.daemon import dayview

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": "날짜는 YYYY-MM-DD 여야 합니다"},
        ) from None
    return value


@router.get("/")
async def index(request: Request) -> RedirectResponse:
    ctx = request.app.state.ctx
    return RedirectResponse(f"/d/{local_date_of(to_iso(ctx.clock.now()))}", status_code=302)


@router.get("/d/{date}")
async def day(request: Request, date: str, deleted: int = 0):
    ctx = request.app.state.ctx
    _validate_date(date)
    view = dayview.build_day(ctx, date, include_deleted=bool(deleted))
    template = "deleted.html" if deleted else "day.html"
    return templates.TemplateResponse(
        request, template, {"view": view, "token": ctx.settings.token}
    )
```

- [ ] **Step 6: `deleted.html` 자리를 임시로 만든다**

Task 18에서 채운다. 지금은 `day.html`을 상속만 한다.

`local/src/warruru_local/daemon/templates/deleted.html`:

```html
{% extends "base.html" %}
{% block content %}<p>준비 중</p>{% endblock %}
```

- [ ] **Step 7: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_web.py -v
```

Expected: PASS — 12 passed

- [ ] **Step 8: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/daemon/dayview.py src/warruru_local/daemon/routes_web.py src/warruru_local/daemon/templates/ tests/test_web.py
git commit -m "feat: 날짜별 Today 화면"
```

---

## Task 18: 삭제와 복구 화면

**Files:**
- Modify: `local/src/warruru_local/daemon/routes_web.py`
- Write: `local/src/warruru_local/daemon/templates/deleted.html`
- Test: `local/tests/test_web_delete.py`

**Interfaces:**
- Consumes: Task 17의 `routes_web`, Task 7의 소프트 삭제 메서드
- Produces:
  - `POST /web/works/{work_id}/delete`, `POST /web/works/{work_id}/restore`
  - `POST /web/checkpoints/{checkpoint_id}/delete`, `POST /web/checkpoints/{checkpoint_id}/restore`
  - 모두 폼 인코딩이며 `_token`과 `date`를 요구한다. 처리 후 `/d/{date}`로 302
  - 토큰이 틀리면 401 `INVALID_TOKEN`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`local/tests/test_web_delete.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local.clock import FixedClock, local_date_of
from warruru_local.config import load_settings
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
TODAY = local_date_of("2026-07-22T08:00:00.000Z")
CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
COMMON = {"client_instance_id": CLIENT, "tool": "codex", "cwd": None}
WORK = "wrk_A"
CKP = "ckp_wrk_A"


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        made.token = settings.token
        yield made


@pytest.fixture
def seeded(client):
    client.post("/v1/works", json={"work_id": WORK, "title": "작업 제목", **COMMON})
    client.post(
        "/v1/checkpoints",
        json={"checkpoint_id": CKP, "work_id": WORK, "type": "NOTE",
              "title": "체크포인트 제목", "body": "본문", **COMMON},
    )
    return client


def _form(client, extra=None):
    data = {"_token": client.token, "date": TODAY}
    data.update(extra or {})
    return data


def test_체크포인트를_삭제하면_화면에서_사라진다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    assert "체크포인트 제목" not in seeded.get(f"/d/{TODAY}").text


def test_삭제하면_날짜_화면으로_돌려보낸다(seeded):
    response = seeded.post(
        f"/web/checkpoints/{CKP}/delete", data=_form(seeded), follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == f"/d/{TODAY}"


def test_삭제한_체크포인트는_삭제_목록에_나온다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}?deleted=1").text


def test_체크포인트를_복구하면_다시_보인다(seeded):
    seeded.post(f"/web/checkpoints/{CKP}/delete", data=_form(seeded))
    seeded.post(f"/web/checkpoints/{CKP}/restore", data=_form(seeded))
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}").text


def test_세션을_삭제하면_하위_체크포인트도_사라진다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}").text
    assert "작업 제목" not in body
    assert "체크포인트 제목" not in body


def test_세션을_복구하면_하위_체크포인트도_돌아온다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    seeded.post(f"/web/works/{WORK}/restore", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}").text
    assert "작업 제목" in body
    assert "체크포인트 제목" in body


def test_삭제한_기록은_맥락_조회에_안_나온다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    payload = seeded.get("/v1/context", params={"date": TODAY}).json()
    assert payload["works"] == []


def test_토큰이_없으면_401_이다(seeded):
    response = seeded.post(
        f"/web/checkpoints/{CKP}/delete", data={"date": TODAY}
    )
    assert response.status_code == 401


def test_토큰이_틀리면_401_이고_삭제되지_않는다(seeded):
    seeded.post(
        f"/web/checkpoints/{CKP}/delete",
        data={"_token": "틀린값", "date": TODAY},
    )
    assert "체크포인트 제목" in seeded.get(f"/d/{TODAY}").text


def test_삭제_화면에_복구_버튼이_있다(seeded):
    seeded.post(f"/web/works/{WORK}/delete", data=_form(seeded))
    body = seeded.get(f"/d/{TODAY}?deleted=1").text
    assert "/restore" in body
    assert "복구" in body


def test_삭제_항목이_없으면_비어_있다고_알린다(client):
    assert "삭제한 기록이 없습니다" in client.get(f"/d/{TODAY}?deleted=1").text
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_web_delete.py -v
```

Expected: FAIL — 405 Method Not Allowed 또는 404

- [ ] **Step 3: `routes_web.py`에 삭제·복구 라우트를 더한다**

파일 끝에 붙인다. 위쪽 import 에 `Form` 을 더한다: `from fastapi import APIRouter, Form, HTTPException, Request`.

```python
def _check_token(request: Request, token: str) -> None:
    """다른 출처의 페이지가 로컬 데몬을 조작하지 못하게 한다."""
    if token != request.app.state.ctx.settings.token:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "토큰이 올바르지 않습니다"},
        )


def _back(date: str) -> RedirectResponse:
    return RedirectResponse(f"/d/{date}", status_code=302)


@router.post("/web/works/{work_id}/delete")
async def delete_work(
    request: Request, work_id: str, _token: str = Form(...), date: str = Form(...)
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, _token)
    ctx.repo.soft_delete_work(work_id, to_iso(ctx.clock.now()))
    return _back(_validate_date(date))


@router.post("/web/works/{work_id}/restore")
async def restore_work(
    request: Request, work_id: str, _token: str = Form(...), date: str = Form(...)
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, _token)
    ctx.repo.restore_work(work_id)
    return _back(_validate_date(date))


@router.post("/web/checkpoints/{checkpoint_id}/delete")
async def delete_checkpoint(
    request: Request,
    checkpoint_id: str,
    _token: str = Form(...),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, _token)
    ctx.repo.soft_delete_checkpoint(checkpoint_id, to_iso(ctx.clock.now()))
    return _back(_validate_date(date))


@router.post("/web/checkpoints/{checkpoint_id}/restore")
async def restore_checkpoint(
    request: Request,
    checkpoint_id: str,
    _token: str = Form(...),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, _token)
    ctx.repo.restore_checkpoint(checkpoint_id)
    return _back(_validate_date(date))
```

- [ ] **Step 4: 삭제된 체크포인트도 목록에 담도록 `dayview.build_day`를 고친다**

세션은 살아 있는데 체크포인트만 삭제된 경우, 삭제 화면에 그 체크포인트가 나와야 한다. `build_day` 끝의 `return` 직전에 다음을 더한다.

```python
    if include_deleted:
        orphans = ctx.repo.list_deleted_checkpoints_between(start, end)
        shown = {
            item["checkpoint_id"]
            for _, view in views
            for item in view["checkpoints"]
        }
        remaining = [row for row in orphans if row["checkpoint_id"] not in shown]
        if remaining:
            grouped: dict[str, list[dict]] = {}
            for row in remaining:
                grouped.setdefault(row["work_id"], []).append(row)
            for work_id, rows in grouped.items():
                parent = ctx.repo.get_work(work_id)
                if parent is None:
                    continue
                view = _work_view(ctx, parent, include_deleted=False)
                view["checkpoints"] = [_checkpoint_view(row) for row in rows]
                views.append((parent["tool"], view))
```

- [ ] **Step 5: `deleted.html`을 쓴다**

```html
{% extends "base.html" %}
{% block title %}{{ view.date }} 삭제 항목 — Warruru Local{% endblock %}
{% block content %}
<header>
  <h1>{{ view.date }} · 삭제 항목</h1>
  <nav><a href="/d/{{ view.date }}">◀ 돌아가기</a></nav>
</header>

{% if not view.groups %}
  <p class="empty">삭제한 기록이 없습니다.</p>
{% endif %}

{% for group in view.groups %}
<section class="tool">
  <h2>{{ group.tool }}</h2>
  {% for work in group.works %}
  <article class="work">
    <div class="work-head">
      <strong>{{ work.title }}</strong>
      <span class="badge">{{ work.status }}</span>
      <form class="inline" method="post" action="/web/works/{{ work.work_id }}/restore">
        <input type="hidden" name="_token" value="{{ token }}">
        <input type="hidden" name="date" value="{{ view.date }}">
        <button type="submit">복구</button>
      </form>
    </div>
    <div class="meta">
      {{ work.started_local }}
      · {% if work.repo_name %}{{ work.repo_name }} / {{ work.branch or "-" }}
        {% else %}Git 정보 없음{% endif %}
    </div>
    <ul class="checkpoints">
      {% for item in work.checkpoints %}
      <li>
        <div class="work-head">
          <span class="meta">{{ item.occurred_local }}</span>
          <span class="badge">{{ item.type }}</span>
          <span>{{ item.title }}</span>
          <form class="inline" method="post"
                action="/web/checkpoints/{{ item.checkpoint_id }}/restore">
            <input type="hidden" name="_token" value="{{ token }}">
            <input type="hidden" name="date" value="{{ view.date }}">
            <button type="submit">복구</button>
          </form>
        </div>
        {% if item.body %}<pre class="body">{{ item.body }}</pre>{% endif %}
      </li>
      {% endfor %}
    </ul>
  </article>
  {% endfor %}
</section>
{% endfor %}
{% endblock %}
```

- [ ] **Step 6: 테스트가 통과하는지 확인한다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_web_delete.py tests/test_web.py -v
```

Expected: PASS — 23 passed

- [ ] **Step 7: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add src/warruru_local/daemon/routes_web.py src/warruru_local/daemon/dayview.py src/warruru_local/daemon/templates/deleted.html tests/test_web_delete.py
git commit -m "feat: 기록 삭제와 복구 화면"
```

---

## Task 19: 인수 테스트와 설치 문서

요구사항 명세서의 AC-01~AC-11을 그대로 테스트로 옮긴다. AC-10(두 머신)은 자동화할 수 없으므로 README의 수동 점검 목록으로 남긴다.

**Files:**
- Create: `local/tests/test_acceptance.py`
- Create: `local/README.md`
- Test: 위 파일 자체

**Interfaces:**
- Consumes: 지금까지의 모든 것
- Produces: 없음 (검증과 문서)

- [ ] **Step 1: 인수 테스트를 쓴다**

`local/tests/test_acceptance.py`:

```python
"""요구사항 명세서 AC-01 ~ AC-11. AC-10 은 README 의 수동 점검 목록에 있다."""

import os
import subprocess
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from warruru_local import paths, spool
from warruru_local.clock import FixedClock, local_date_of
from warruru_local.config import load_settings
from warruru_local.daemon import absorb
from warruru_local.daemon.app import create_app
from warruru_local.mcp.client import DaemonClient
from warruru_local.mcp.server import ToolService

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
TODAY = local_date_of("2026-07-22T08:00:00.000Z")
CODEX = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
CLAUDE = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF5"


@pytest.fixture
def clock():
    return FixedClock(START)


@pytest.fixture
def client(home, clock):
    settings = load_settings(home)
    app = create_app(settings, clock=clock, start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        made.token = settings.token
        yield made


def _common(client_id=CODEX, tool="codex", cwd=None):
    return {"client_instance_id": client_id, "tool": tool, "cwd": cwd}


def _run(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- AC-01

def test_AC01_기본_흐름(client):
    client.post("/v1/works", json={"work_id": "wrk_A", "title": "기본 흐름",
                                   **_common()})
    for index in range(3):
        client.post("/v1/checkpoints", json={
            "checkpoint_id": f"ckp_{index}", "work_id": "wrk_A",
            "type": "ATTEMPT", "title": f"시도 {index}", **_common()})
    client.post("/v1/works/wrk_A/finish",
                json={"result": "됐다", **_common()})

    page = client.get(f"/d/{TODAY}").text
    assert "기본 흐름" in page
    assert "FINISHED" in page
    assert page.count("시도 ") == 3


# ---------------------------------------------------------------- AC-02

def test_AC02_규칙을_안_지켜도_기록된다(client):
    body = client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_A", "type": "PROBLEM",
        "title": "start_work 없이 남긴 기록", **_common()}).json()

    work = client.app.state.ctx.repo.get_work(body["work_id"])
    assert work["origin"] == "INFERRED"
    assert work["title"] == "start_work 없이 남긴 기록"
    assert work["title_origin"] == "DERIVED"
    assert "start_work 없이 남긴 기록" in client.get(f"/d/{TODAY}").text


# ---------------------------------------------------------------- AC-03

def test_AC03_미마감_세션은_자동_마감된다(client, clock):
    client.post("/v1/works", json={"work_id": "wrk_A", "title": "끊긴 작업",
                                   **_common()})
    clock.advance(timedelta(hours=5).total_seconds())
    client.app.state.ctx.sessions.sweep_idle()

    row = client.app.state.ctx.repo.get_work("wrk_A")
    assert row["status"] == "AUTO_CLOSED"
    assert row["ended_reason"] == "IDLE_TIMEOUT"

    page = client.get(f"/d/{TODAY}").text
    assert "AUTO_CLOSED" in page
    assert "IDLE_TIMEOUT" in page


# ---------------------------------------------------------------- AC-04

def test_AC04_데몬이_없어도_기록이_남고_나중에_반영된다(home, clock, client):
    settings = load_settings(home)
    import logging

    class DeadTransport:
        def request(self, *args, **kwargs):
            raise httpx.ConnectError("데몬 없음")

    dead = DaemonClient(settings, CODEX, logging.getLogger("t"), clock,
                        transport=DeadTransport(), spawner=lambda: False)
    service = ToolService(dead, "codex", clock)

    result = service.record_checkpoint(type="PROBLEM", title="데몬 없이 남긴 기록")
    assert result["ok"] is True
    assert result["storage"] == "SPOOL"

    # 데몬이 나중에 떠서 흡수한다
    for path in paths.spool_dir(home).glob("*.jsonl"):
        stamp = time.time() - 60
        os.utime(path, (stamp, stamp))

    assert absorb.absorb_all(client.app.state.ctx) == 1
    assert "데몬 없이 남긴 기록" in client.get(f"/d/{TODAY}").text

    # 여러 번 흡수해도 중복되지 않는다
    absorb.absorb_all(client.app.state.ctx)
    assert client.get(f"/d/{TODAY}").text.count("데몬 없이 남긴 기록") == 1


# ---------------------------------------------------------------- AC-05

def test_AC05_두_에이전트가_동시에_기록해도_섞이지_않는다(client):
    client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_codex", "type": "NOTE", "title": "코덱스 기록",
        **_common(CODEX, "codex")})
    client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_claude", "type": "NOTE", "title": "클로드 기록",
        **_common(CLAUDE, "claude-code")})

    ctx = client.app.state.ctx
    codex_work = ctx.repo.get_checkpoint("ckp_codex")["work_id"]
    claude_work = ctx.repo.get_checkpoint("ckp_claude")["work_id"]
    assert codex_work != claude_work

    page = client.get(f"/d/{TODAY}").text
    assert "codex" in page and "claude-code" in page


# ---------------------------------------------------------------- AC-06

def test_AC06_git_없는_디렉터리에서도_실패하지_않는다(client, tmp_path):
    plain = tmp_path / "저장소아님"
    plain.mkdir()
    body = client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_A", "type": "NOTE", "title": "제목",
        **_common(cwd=str(plain))}).json()

    assert body["git"] is None
    assert "Git 정보 없음" in client.get(f"/d/{TODAY}").text


# ---------------------------------------------------------------- AC-07

def test_AC07_git_저장소면_브랜치와_커밋이_남는다(client, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init", "-b", "main")
    _run(root, "config", "user.email", "t@example.com")
    _run(root, "config", "user.name", "T")
    (root / "a.txt").write_text("x", encoding="utf-8")
    _run(root, "add", "a.txt")
    _run(root, "commit", "-m", "first")

    body = client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_A", "type": "NOTE", "title": "제목",
        **_common(cwd=str(root))}).json()

    assert body["git"]["branch"] == "main"
    assert len(body["git"]["commit"]) == 40
    page = client.get(f"/d/{TODAY}").text
    assert "repo" in page
    assert body["git"]["commit"][:7] in page


# ---------------------------------------------------------------- AC-08

def test_AC08_삭제하면_사라지고_복구하면_돌아온다(client):
    client.post("/v1/works", json={"work_id": "wrk_A", "title": "삭제 대상",
                                   **_common()})
    client.post("/v1/checkpoints", json={
        "checkpoint_id": "ckp_A", "work_id": "wrk_A", "type": "NOTE",
        "title": "하위 기록", **_common()})

    form = {"_token": client.token, "date": TODAY}
    client.post("/web/checkpoints/ckp_A/delete", data=form)
    assert "하위 기록" not in client.get(f"/d/{TODAY}").text
    assert "하위 기록" in client.get(f"/d/{TODAY}?deleted=1").text

    client.post("/web/checkpoints/ckp_A/restore", data=form)
    assert "하위 기록" in client.get(f"/d/{TODAY}").text

    client.post("/web/works/wrk_A/delete", data=form)
    page = client.get(f"/d/{TODAY}").text
    assert "삭제 대상" not in page
    assert "하위 기록" not in page


# ---------------------------------------------------------------- AC-09

def test_AC09_데몬을_다시_띄워도_기록이_남아_있다(home, clock):
    settings = load_settings(home)

    first = create_app(settings, clock=clock, start_background=False)
    with TestClient(first) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        made.post("/v1/works", json={"work_id": "wrk_A", "title": "재기동 전",
                                     **_common()})

    second = create_app(settings, clock=clock, start_background=False)
    with TestClient(second) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        assert "재기동 전" in made.get(f"/d/{TODAY}").text


# ---------------------------------------------------------------- AC-11

def test_AC11_체크포인트_100회의_p95_는_200ms_이하다(client):
    durations = []
    for index in range(100):
        started = time.perf_counter()
        client.post("/v1/checkpoints", json={
            "checkpoint_id": f"ckp_{index}", "type": "NOTE",
            "title": f"기록 {index}", **_common()})
        durations.append(time.perf_counter() - started)

    durations.sort()
    p95 = durations[94]
    assert p95 < 0.2, f"p95 가 {p95 * 1000:.0f}ms 다"
```

- [ ] **Step 2: 인수 테스트를 돌린다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest tests/test_acceptance.py -v
```

Expected: PASS — 10 passed

- [ ] **Step 3: 전체 테스트를 돌린다**

```bash
cd D:/project_univ/warruru-lab/local
python -m pytest -q
```

Expected: PASS — 224 passed

- [ ] **Step 4: `README.md`를 쓴다**

`local/README.md`:

````markdown
# Warruru Local

여러 AI 에이전트가 MCP 로 남긴 개발 기록을 개인 머신에 유실 없이 저장하고, 날짜별로 되돌아보게 한다.

WarruruLab 의 네 번째 축이며, 유일하게 서버가 아닌 사용자의 머신에서 돈다.
명세서는 통합 docs 의 `docs/local/specs/` 에 있다.

## 구성

```text
Codex / Claude Code / Antigravity
        │  stdio (에이전트마다 1 프로세스)
        ▼
   warruru-mcp  ──HTTP──▶  warruru-daemon  ──▶  ~/.warruru/warruru.db
                                  │
   브라우저  ─────────────────────┘  (날짜별 화면)
```

데몬이 SQLite 의 유일한 writer 다. 데몬에 닿지 못하면 어댑터가 기록을
`~/.warruru/spool/` 에 남기고, 데몬이 나중에 흡수한다. **성공 응답을 받은
기록은 어떤 경우에도 사라지지 않는다.**

## 설치

```bash
cd local
python -m pip install -e .
```

에이전트의 MCP 설정에 다음 한 줄을 넣는다. 데몬은 필요할 때 어댑터가 알아서 띄운다.

```json
{
  "mcpServers": {
    "warruru": {
      "command": "warruru-mcp",
      "env": { "WARRURU_TOOL": "codex" }
    }
  }
}
```

`WARRURU_TOOL` 은 화면에서 기록을 도구별로 나눌 때 쓰는 이름이다.
에이전트마다 다르게 준다: `codex`, `claude-code`, `antigravity`.

화면은 <http://127.0.0.1:8787/> 에서 연다.

## 에이전트 기록 규칙

각 에이전트의 `AGENTS.md` 또는 규칙 파일에 넣는다.

```md
작업을 시작할 때 start_work 를 호출한다.

다음 상황에서 record_checkpoint 를 호출한다.

- 기존 접근 방법을 포기하거나 변경했을 때
- 중요한 오류가 발생했을 때
- 오류의 원인을 확인했을 때
- 중요한 구현 방식이나 아키텍처를 결정했을 때
- 테스트 결과가 작업 방향을 바꿨을 때
- 의미 있는 기능이 완료됐을 때
- 남은 한계가 확인됐을 때

작업이 끝나면 finish_work 를 호출한다.

단순 오타 수정, 포맷팅, 파일 탐색, 반복 테스트, 임시 디버깅 코드는 기록하지 않는다.
```

`start_work` 를 빼먹어도 기록은 남는다. 자동으로 세션이 만들어지고
`INFERRED` 로 표시된다.

## 저장 위치

```text
~/.warruru/
├── warruru.db          기록
├── config/             machine.json, daemon.json(토큰)
├── spool/              데몬에 못 넘긴 기록. absorbed/ 로 옮겨진다
├── logs/               daemon.log, mcp.log
└── run/                daemon.lock
```

`WARRURU_HOME` 으로 위치를 바꿀 수 있다. 설정 목록은 명세서 IF-7 에 있다.

## 개발

```bash
python -m pytest -q          # 전체
python -m pytest tests/test_session_attach.py -v
```

시각과 식별자 생성은 주입할 수 있다. 귀속 규칙과 자동 마감을 검증할 때
실제 대기를 쓰지 않는다.

## 두 머신 점검 (AC-10, 수동)

자동화할 수 없어 손으로 확인한다. Windows 와 macOS 각각에서:

- [ ] `python -m pip install -e .` 가 끝난다
- [ ] 에이전트에서 `start_work` → `record_checkpoint` → `finish_work` 가 동작한다
- [ ] <http://127.0.0.1:8787/> 에 그 기록이 보인다
- [ ] `~/.warruru/config/machine.json` 의 `machine_id` 가 두 머신에서 서로 다르다
- [ ] 데몬을 강제 종료한 뒤 기록해도 툴이 성공을 반환하고, 데몬을 다시 띄우면 반영된다
- [ ] 에이전트를 종료하면 진행 중 세션이 `AUTO_CLOSED` / `CLIENT_EXIT` 이 된다

## 하지 않는 일

Git Diff·Patch·핵심 Symbol 추출, 오류/테스트 로그 수집, 서버 전송,
LLM 요약, 블로그 초안 생성은 전부 후속 단계다. 이 축은 기록만 한다.
````

- [ ] **Step 5: 커밋한다**

```bash
cd D:/project_univ/warruru-lab/local
git add tests/test_acceptance.py README.md
git commit -m "test: 인수 테스트 AC-01~AC-11 과 설치 문서"
```

---

## 자체 점검

계획을 다 쓰고 명세서와 맞춰 본 결과다.

### 명세서 요구사항 대응

| 요구사항 | 태스크 |
| --- | --- |
| FR-01 작업 시작 | T12, T16 |
| FR-02 체크포인트 | T12, T16 |
| FR-03 작업 종료 | T10, T12, T16 |
| FR-04 오늘 맥락 조회 | T13, T16 |
| FR-05 세션 자동 귀속 | T9 |
| FR-06 세션 자동 마감 | T10 |
| FR-07 세션 제목 파생 | T9 |
| FR-08 Git 스냅샷 | T8 |
| FR-09 출처 식별 | T2(`WARRURU_TOOL`), T16 |
| FR-10 머신 식별 | T2, T11 |
| FR-11 오프라인 폴백 | T14, T15 |
| FR-12 Spool 흡수 | T14 |
| FR-13 멱등 기록 | T5, T6 |
| FR-14 날짜별 조회 화면 | T17 |
| FR-15 도구별 구분 | T17 |
| FR-16 세션 상세 | T17 |
| FR-17 삭제와 복구 | T7, T18 |
| FR-18 날짜 이동 | T17 |
| NFR-01 무손실 | T14, T15, AC-04 |
| NFR-02 지연 | T8(예산·캐시), AC-11 |
| NFR-03 크로스 플랫폼 | T2, T11(잠금), T15(기동) |
| NFR-04 로컬 우선 | 외부 호출 없음 |
| NFR-05 설치 단순성 | T15 자동 기동, T19 README |
| NFR-06 동시성 | T11 단일 writer, AC-05 |
| NFR-07 관측 가능성 | T2 회전 로그 |
| NFR-08 이식성 | T3 SQLite, T14 JSONL |
| NFR-09 접근 통제 | T11 토큰, T18 폼 토큰 |
| NFR-10 스키마 진화 | T3 |
| NFR-11 시간 표기 | T1, T13 |

빠진 요구사항은 없다.

### 남은 주의점

**1. T12가 `recording.py`를 만든다.** 라우터에 기록 로직을 두지 않는다. T14의 spool 흡수가 HTTP를 거치지 않고 같은 함수를 불러야 하기 때문이다. 라우터가 두꺼워 보이면 배치가 잘못된 것이다.

**2. 테스트 개수는 어림이다.** 각 태스크의 "Expected: PASS — N passed"는 그 파일의 테스트 수를 센 것이고, 전체 합계(56, 105, 154, 224)는 누적 추정이다. 숫자가 다르면 테스트가 실제로 통과하는지만 보고 넘어간다.

**3. `FixedClock`을 쓰는 API 테스트에서 `duration_seconds`는 0이다.** 시각이 고정돼 있기 때문이다. 의도한 것이며, 실제 소요 시간 계산은 T10의 `test_마감하면_결과와_종료_커밋이_남는다`에서 `clock.advance` 로 검증한다.

**4. Windows 파일 잠금.** `msvcrt.locking`은 파일 오프셋 기준이라 잠글 때와 풀 때 모두 `seek(0)`이 필요하다. T11 Step 3의 주의 문구를 지킨다.

**5. AC-11은 환경을 탄다.** `TestClient` 위에서 재는 값이라 디스크가 느리면 흔들릴 수 있다. 실패하면 먼저 `PRAGMA journal_mode=WAL`이 실제로 켜져 있는지 확인한다.

