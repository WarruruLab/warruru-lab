"""붙여넣기용 HTML 을 만든다. 마지막 10초만 사람이 한다.

티스토리 공식 Open API 는 2023-12-22 종료 공지 후 2024년 2월에 순차 종료됐고,
2026-08-18 직접 확인 기준 앱 등록 · `/oauth/authorize` · `/apis/post/write` 가
전부 404 다. 존재하지 않는 것에 일정을 묶을 수 없어, 이 어댑터는 붙여넣을
문자열만 만들고 저장은 사람이 한다
(`local/docs/adr/2026-08-18-publish-target.md`).

**마크다운 정본은 언제나 로컬이다.** 티스토리에 붙여넣으면 원본이 HTML 로
정규화되어 복원되지 않는다. 그래서 이 어댑터는 파일을 쓰지 않는다 —
정본은 `MarkdownFileTarget` 이 이미 남겼다.

변환은 **최소한만** 한다. 완전한 마크다운 처리기를 만들 이유가 없다 —
초안은 이 프로젝트의 조립기가 만든 것이라 문법이 좁고, 넓히면 그 범위를
유지해야 한다. 여기서 못 다루는 문법이 나오면 조립기 쪽을 좁히는 편이 맞다.
"""

from __future__ import annotations

import html
import re

from warruru_local.publish.base import PublishResult, PublishTarget

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_FENCE = "```"

# 굵게 → 인라인 코드 순서로 처리한다. 코드 안의 별표를 굵게로 오인하지 않게,
# 코드부터 자리표시자로 빼 두고 마지막에 되돌린다.
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_PLACEHOLDER = "\x00CODE{}\x00"


def _inline(text: str) -> str:
    """이스케이프 먼저, 그다음 인라인 문법. 순서를 바꾸면 태그가 새어 나간다."""
    codes: list[str] = []

    def _stash(match: re.Match) -> str:
        codes.append(match.group(1))
        return _PLACEHOLDER.format(len(codes) - 1)

    stashed = _CODE.sub(_stash, text)
    escaped = html.escape(stashed, quote=False)
    bolded = _BOLD.sub(r"<strong>\1</strong>", escaped)
    for index, code in enumerate(codes):
        bolded = bolded.replace(
            _PLACEHOLDER.format(index), f"<code>{html.escape(code, quote=False)}</code>"
        )
    return bolded


def to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    bullets: list[str] = []
    fenced: list[str] | None = None

    def _flush_bullets() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for line in lines:
        if line.strip().startswith(_FENCE):
            if fenced is None:
                _flush_bullets()
                fenced = []
            else:
                body = html.escape("\n".join(fenced), quote=False)
                out.append(f"<pre><code>{body}</code></pre>")
                fenced = None
            continue

        if fenced is not None:
            fenced.append(line)
            continue

        heading = _HEADING.match(line)
        if heading:
            _flush_bullets()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        bullet = _BULLET.match(line)
        if bullet:
            bullets.append(_inline(bullet.group(1)))
            continue

        _flush_bullets()
        if line.strip():
            out.append(f"<p>{_inline(line.strip())}</p>")

    _flush_bullets()
    if fenced is not None:      # 닫히지 않은 코드블록도 버리지 않는다
        body = html.escape("\n".join(fenced), quote=False)
        out.append(f"<pre><code>{body}</code></pre>")
    return "\n".join(out)


class TistoryClipboardTarget(PublishTarget):
    name = "tistory_clipboard"

    def publish(
        self,
        title: str,
        markdown: str,
        tags: list[str] | None = None,
        visibility: str = "private",
    ) -> PublishResult:
        return PublishResult(target=self.name, body=to_html(markdown))
