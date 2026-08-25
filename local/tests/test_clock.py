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


def test_local_day_bounds는_시스템_시계를_읽지_않는다(monkeypatch):
    """라이브러리 코드는 시스템 시계를 직접 읽지 않는다.

    이전 구현은 `datetime.now().astimezone().tzinfo`로 오프셋을 구했다 —
    "지금"과 대상 날짜가 서머타임 경계 반대편에 있으면 하루 경계가
    한 시간 어긋나는 잠재 버그였다. 이제는 대상 날짜 자체에서 오프셋을
    구하므로 `datetime.now()`를 전혀 부르지 않아야 한다.
    """
    import warruru_local.clock as clock_module

    class NoNow(clock_module.datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError("local_day_bounds는 datetime.now()를 부르면 안 된다")

    monkeypatch.setattr(clock_module, "datetime", NoNow)

    start, end = clock_module.local_day_bounds("2026-07-22")
    assert start < end
    assert clock_module.local_date_of(start) == "2026-07-22"


# ── local_month_bounds (Task 12) ──────────────────────────────────

def test_달_경계는_다음_달_1일의_시작이다():
    from warruru_local.clock import local_date_of, local_month_bounds

    start, end = local_month_bounds("2026-07")
    assert local_date_of(start) == "2026-07-01"
    # 끝은 배타적이다. 7월 31일이 아니라 8월 1일 자정이어야
    # 31일 하루가 통째로 달력에서 빠지지 않는다.
    assert local_date_of(end) == "2026-08-01"


def test_12월은_다음_해_1월로_넘어간다():
    from warruru_local.clock import local_date_of, local_month_bounds

    assert local_date_of(local_month_bounds("2026-12")[1]) == "2027-01-01"


def test_윤년_2월도_말일_계산_없이_맞는다():
    """말일을 구해 하루를 더하는 방식이었다면 여기서 틀린다."""
    from warruru_local.clock import local_date_of, local_month_bounds

    assert local_date_of(local_month_bounds("2028-02")[1]) == "2028-03-01"
    assert local_date_of(local_month_bounds("2026-02")[1]) == "2026-03-01"


def test_달_경계도_시스템_시계를_읽지_않는다(monkeypatch):
    import warruru_local.clock as clock_module

    class NoNow(clock_module.datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError("local_month_bounds는 datetime.now()를 부르면 안 된다")

    monkeypatch.setattr(clock_module, "datetime", NoNow)
    start, end = clock_module.local_month_bounds("2026-07")
    assert start < end
