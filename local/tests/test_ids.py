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
