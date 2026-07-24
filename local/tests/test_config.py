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
