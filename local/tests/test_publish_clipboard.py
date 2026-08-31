"""`TistoryClipboardTarget` — 마지막 10초만 사람이 한다.

티스토리 공식 Open API 는 2024년 2월에 죽었다. 존재하지 않는 것에 일정을
묶을 수 없어, 붙여넣기용 HTML 을 만들어 주고 저장은 사람이 한다.

**마크다운 정본은 언제나 로컬이다.** 발행하면 원본이 HTML 로 정규화되어
복원되지 않으므로 이 순서는 뒤집을 수 없다.
"""

import inspect

from warruru_local.publish.tistory_clipboard import (
    TistoryClipboardTarget,
    to_html,
    unsupported_syntax,
)

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


# ── 2026-08-31: `/career` 가 두 번째 사용처로 들어오며 넓힌 범위 ──────────

def test_표가_thead_와_tbody_로_나뉜다():
    html = to_html("| 키워드 | 기록 |\n|---|---|\n| Kafka | 0건 |\n")
    assert "<thead><tr><th>키워드</th><th>기록</th></tr></thead>" in html
    assert "<tbody><tr><td>Kafka</td><td>0건</td></tr></tbody>" in html


def test_구분선을_빠뜨린_표도_표로_그린다():
    """파이프가 그대로 문단으로 눕는 것보다 머리 없는 표가 낫다."""
    html = to_html("| a | b |\n| c | d |\n")
    assert "<table>" in html and "<thead>" not in html


def test_표_칸_안에서도_굵게와_코드가_산다():
    html = to_html("| x |\n|---|\n| **0건** `db-index` |\n")
    assert "<strong>0건</strong>" in html
    assert "<code>db-index</code>" in html


def test_인용문과_번호목록과_가로줄():
    html = to_html("> 인용\n\n1. 하나\n2. 둘\n\n---\n")
    assert "<blockquote><p>인용</p></blockquote>" in html
    assert "<ol><li>하나</li><li>둘</li></ol>" in html
    assert "<hr>" in html


def test_링크의_앰퍼샌드가_두_번_escape_되지_않는다():
    """`&amp;amp;` 가 되면 주소가 깨진다. 들어오는 문자열은 이미 escape 된 상태다."""
    html = to_html("[원문](https://e.com/a?b=1&c=2)")
    assert 'href="https://e.com/a?b=1&amp;c=2"' in html
    assert "&amp;amp;" not in html


def test_수상한_주소는_링크를_걸지_않는다():
    """미리보기는 `|safe` 로 그려진다. 공고 원문을 붙여넣는 자리가 생긴 이상
    '내가 쓴 것' 이라는 전제를 세우지 않는다."""
    html = to_html("[누르지마](javascript:alert(1))")
    assert "<a" not in html
    assert "누르지마" in html


def test_주소_안의_따옴표가_속성_밖으로_못_나간다():
    html = to_html('[x](https://e.com/"onmouseover="alert(1))')
    assert "onmouseover=\"alert" not in html
    assert "&quot;" in html


def test_이미지는_여전히_안_그린다():
    assert unsupported_syntax("![그림](./a.png)") == ["이미지"]
    assert unsupported_syntax("| a |\n|---|\n> 인용\n1. 하나\n---\n[링크](/a)") == []
