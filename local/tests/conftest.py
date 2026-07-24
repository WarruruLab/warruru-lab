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
