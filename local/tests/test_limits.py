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
