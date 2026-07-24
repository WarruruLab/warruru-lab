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
