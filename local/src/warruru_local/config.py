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
    # 초안이 앉는 자리. `None` 은 "정해진 자리"(`~/.warruru/drafts`)를 뜻한다.
    # 해석은 `paths.drafts_dir` 한 곳에서 하므로 여기서는 덮어쓴 값만 담는다.
    drafts_root: Path | None = None
    # 이 경로 안에는 초안을 쓰지 않는다. 저장소가 public 이라 사고 방지 장치다.
    # `None` 이면 검사하지 않는다 — 저장소 밖에서 데몬을 돌리는 경우다.
    repo_root: Path | None = None


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
        drafts_root=(
            Path(os.environ["WARRURU_DRAFTS_ROOT"]).expanduser()
            if os.environ.get("WARRURU_DRAFTS_ROOT")
            else None
        ),
        repo_root=_repo_root(),
    )


def _repo_root() -> Path | None:
    """초안을 쓰면 안 되는 경로. 없으면 검사하지 않는다.

    기본값을 두지 않는 이유는, 데몬이 어느 저장소 안에서 도는지 모르기 때문이다.
    `WARRURU_REPO_ROOT` 로 알려 준 경우에만 막는다.
    """
    override = os.environ.get("WARRURU_REPO_ROOT")
    return Path(override).expanduser().resolve() if override else None
