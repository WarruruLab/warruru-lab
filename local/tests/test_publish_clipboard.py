"""`TistoryClipboardTarget` — 마지막 10초만 사람이 한다.

티스토리 공식 Open API 는 2024년 2월에 죽었다. 존재하지 않는 것에 일정을
묶을 수 없어, 붙여넣기용 HTML 을 만들어 주고 저장은 사람이 한다.

**마크다운 정본은 언제나 로컬이다.** 발행하면 원본이 HTML 로 정규화되어
복원되지 않으므로 이 순서는 뒤집을 수 없다.
"""

import inspect

from warruru_local.publish.tistory_clipboard import TistoryClipboardTarget

MARKDOWN = """# 커넥션 풀

## 문제

대기가 병목이었다.

- 첫째
- 둘째

## 측정

`p95` 가 **90ms** 로 내려갔다.
"""


def test_마크다운이_붙여넣기용_HTML_로_바뀐다():
    result = TistoryClipboardTarget().publish(title="커넥션 풀", markdown=MARKDOWN)
    html = result.body
    assert "<h1>커넥션 풀</h1>" in html
    assert "<h2>문제</h2>" in html
    assert "<li>첫째</li>" in html
    assert "<code>p95</code>" in html
    assert "<strong>90ms</strong>" in html


def test_문단이_p_로_감싸인다():
    html = TistoryClipboardTarget().publish(title="t", markdown="한 문단.\n").body
    assert "<p>한 문단.</p>" in html


def test_HTML_특수문자가_escape_된다():
    """본문에 <script> 가 있으면 붙여넣는 순간 글이 깨진다."""
    html = TistoryClipboardTarget().publish(
        title="t", markdown="a < b & c > d\n"
    ).body
    assert "&lt;" in html and "&amp;" in html
    assert "<b>" not in html


def test_코드블록은_pre_로_남는다():
    markdown = "```\nSELECT 1;\n```\n"
    html = TistoryClipboardTarget().publish(title="t", markdown=markdown).body
    assert "<pre>" in html and "SELECT 1;" in html


def test_기본_visibility_는_private_이다():
    """공개는 사람이 명시해야만 일어난다."""
    signature = inspect.signature(TistoryClipboardTarget.publish)
    assert signature.parameters["visibility"].default == "private"


def test_파일을_쓰지_않는다(tmp_path, monkeypatch):
    """이 어댑터는 화면에 띄울 문자열만 만든다. 정본은 마크다운 파일이다."""
    monkeypatch.chdir(tmp_path)
    TistoryClipboardTarget().publish(title="t", markdown=MARKDOWN)
    assert list(tmp_path.iterdir()) == []


def test_결과에_경로가_없다():
    result = TistoryClipboardTarget().publish(title="t", markdown=MARKDOWN)
    assert result.path is None
    assert result.target == "tistory_clipboard"
