"""붙여넣기용 HTML 을 만든다. 마지막 10초만 사람이 한다.

티스토리 공식 Open API 는 2023-12-22 종료 공지 후 2024년 2월에 순차 종료됐고,
2026-08-18 직접 확인 기준 앱 등록 · `/oauth/authorize` · `/apis/post/write` 가
전부 404 다. 존재하지 않는 것에 일정을 묶을 수 없어, 이 어댑터는 붙여넣을
문자열만 만들고 저장은 사람이 한다
(`local/docs/adr/2026-08-18-publish-target.md`).

**마크다운 정본은 언제나 로컬이다.** 티스토리에 붙여넣으면 원본이 HTML 로
정규화되어 복원되지 않는다. 그래서 이 어댑터는 파일을 쓰지 않는다 —
정본은 `MarkdownFileTarget` 이 이미 남겼다.

변환 범위는 **쓰는 쪽이 실제로 만드는 문법**까지다. 오래 초안 조립기 하나만
있을 때는 다섯 개(제목·불릿·코드펜스·굵게·인라인코드)로 충분했는데,
`/career` 의 회사 노트가 두 번째 사용처로 들어오면서 표·링크·인용문·번호
목록·가로줄이 실제로 쓰이기 시작했다(2026-08-31). 그래서 그만큼 넓혔다.

**이미지는 여전히 안 그린다.** 로컬 파일을 가리키는 이미지는 붙여넣는 순간
깨지고, 외부 호스팅은 이 프로젝트가 하지 않기로 한 일이다.
"""

from __future__ import annotations

import html
import re

from warruru_local.publish.base import PublishResult, PublishTarget

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+\.\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_RULE = re.compile(r"^\s*(---|\*\*\*|___)\s*$")
_ROW = re.compile(r"^\s*\|(.*)\|\s*$")
_DIVIDER_CELL = re.compile(r"^:?-{1,}:?$")
_FENCE = "```"

# 굵게 → 인라인 코드 순서로 처리한다. 코드 안의 별표를 굵게로 오인하지 않게,
# 코드부터 자리표시자로 빼 두고 마지막에 되돌린다.
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_PLACEHOLDER = "\x00CODE{}\x00"

# 미리보기는 `|safe` 로 그려진다. 여기서 거르지 않으면 `javascript:` 가 그대로
# href 에 들어간다. 기록은 본인이 쓴 것이지만, 공고 원문을 붙여넣는 자리가
# 생긴 이상 "내가 쓴 것" 이라는 전제를 더는 세우지 않는다.
_SAFE_SCHEME = re.compile(r"^(https?:|mailto:|#|/|\.{0,2}/)", re.I)


def _link(match: re.Match) -> str:
    """`[글](주소)`. 주소가 수상하면 링크를 걸지 않고 글자만 남긴다.

    **여기 오는 문자열은 이미 escape 된 상태다.** `&` 를 다시 escape 하면
    `?b=1&c=2` 가 `&amp;amp;` 가 되어 링크가 깨진다. 그래서 따옴표만 막는다 —
    앞의 escape 가 `quote=False` 라 따옴표는 아직 살아 있고, 그대로 두면
    href 속성 밖으로 빠져나간다.
    """
    label, href = match.group(1), match.group(2)
    if not _SAFE_SCHEME.match(href):
        return label
    safe = href.replace('"', "&quot;")
    return f'<a href="{safe}">{label}</a>'


def _inline(text: str) -> str:
    """이스케이프 먼저, 그다음 인라인 문법. 순서를 바꾸면 태그가 새어 나간다."""
    codes: list[str] = []

    def _stash(match: re.Match) -> str:
        codes.append(match.group(1))
        return _PLACEHOLDER.format(len(codes) - 1)

    stashed = _CODE.sub(_stash, text)
    escaped = html.escape(stashed, quote=False)
    linked = _LINK.sub(_link, escaped)
    bolded = _BOLD.sub(r"<strong>\1</strong>", linked)
    for index, code in enumerate(codes):
        bolded = bolded.replace(
            _PLACEHOLDER.format(index), f"<code>{html.escape(code, quote=False)}</code>"
        )
    return bolded


def _cells(line: str) -> list[str]:
    """`| a | b |` 의 가운데만 쓴다. 양끝 파이프는 이미 벗겨진 상태로 들어온다."""
    return [cell.strip() for cell in line.split("|")]


def _is_divider(line: str) -> bool:
    row = _ROW.match(line)
    if not row:
        return False
    cells = _cells(row.group(1))
    return bool(cells) and all(_DIVIDER_CELL.match(cell) for cell in cells)


def _table_html(rows: list[str]) -> str:
    """둘째 줄이 구분선이면 첫 줄이 머리다. 아니면 머리 없는 표로 그린다.

    구분선이 없다고 표가 아닌 것으로 되돌리지 않는다 — 손으로 쓰다 구분선을
    빠뜨렸을 때 파이프 문자가 그대로 문단으로 눕는 것이 더 나쁘다.
    """
    head: list[str] | None = None
    body = rows
    if len(rows) >= 2 and _is_divider(rows[1]):
        head = _cells(_ROW.match(rows[0]).group(1))
        body = rows[2:]

    made = ["<table>"]
    if head is not None:
        made.append(
            "<thead><tr>"
            + "".join(f"<th>{_inline(cell)}</th>" for cell in head)
            + "</tr></thead>"
        )
    made.append("<tbody>")
    for row in body:
        if _is_divider(row):
            continue
        cells = _cells(_ROW.match(row).group(1))
        made.append(
            "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in cells) + "</tr>"
        )
    made.append("</tbody></table>")
    return "".join(made)


def to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    bullets: list[str] = []
    ordered: list[str] = []
    quoted: list[str] = []
    table: list[str] = []
    fenced: list[str] | None = None

    def _flush() -> None:
        """열려 있는 블록을 닫는다. **한 곳에서만 닫는다** — 블록 종류마다
        따로 닫으면 새 블록을 더할 때마다 닫는 자리를 다 찾아야 하고,
        하나를 빠뜨리면 목록 안에 표가 끼는 식으로 조용히 어긋난다."""
        if bullets:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in bullets) + "</ul>")
            bullets.clear()
        if ordered:
            out.append("<ol>" + "".join(f"<li>{i}</li>" for i in ordered) + "</ol>")
            ordered.clear()
        if quoted:
            out.append(
                "<blockquote>"
                + "".join(f"<p>{i}</p>" for i in quoted if i)
                + "</blockquote>"
            )
            quoted.clear()
        if table:
            out.append(_table_html(table))
            table.clear()

    for line in lines:
        if line.strip().startswith(_FENCE):
            if fenced is None:
                _flush()
                fenced = []
            else:
                body = html.escape("\n".join(fenced), quote=False)
                out.append(f"<pre><code>{body}</code></pre>")
                fenced = None
            continue

        if fenced is not None:
            fenced.append(line)
            continue

        # 표가 먼저다. `|---|---|` 는 가로줄 규칙에도 걸릴 수 있다.
        if _ROW.match(line):
            if bullets or ordered or quoted:
                _flush()
            table.append(line)
            continue

        heading = _HEADING.match(line)
        if heading:
            _flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        if _RULE.match(line):
            _flush()
            out.append("<hr>")
            continue

        quote = _QUOTE.match(line)
        if quote:
            if bullets or ordered or table:
                _flush()
            quoted.append(_inline(quote.group(1).strip()))
            continue

        bullet = _BULLET.match(line)
        if bullet:
            if ordered or quoted or table:
                _flush()
            bullets.append(_inline(bullet.group(1)))
            continue

        numbered = _ORDERED.match(line)
        if numbered:
            if bullets or quoted or table:
                _flush()
            ordered.append(_inline(numbered.group(1)))
            continue

        _flush()
        if line.strip():
            out.append(f"<p>{_inline(line.strip())}</p>")

    _flush()
    if fenced is not None:      # 닫히지 않은 코드블록도 버리지 않는다
        body = html.escape("\n".join(fenced), quote=False)
        out.append(f"<pre><code>{body}</code></pre>")
    return "\n".join(out)


# 이 변환기가 **다루지 않는** 문법. 미리보기가 조용히 문단으로 눕히는 것들이다.
#
# 목록이 줄어든 만큼 이 경고의 값이 올라간다 — 여섯 개가 늘 떠 있으면
# 아무도 안 읽는다. **모르는 것을 그리지 않는 것보다, 모른다고 말하지 않는
# 것이 나쁘다.**
UNSUPPORTED = (
    (re.compile(r"!\[[^\]]*\]\("), "이미지"),
)


def unsupported_syntax(markdown: str) -> list[str]:
    """미리보기가 못 그리는 문법의 이름들. 코드블록 안은 세지 않는다.

    미리보기는 티스토리를 **재현하지 않는다.** 구조가 맞는지 보는 자리다.
    여기서 걸린 문법은 붙여넣은 뒤 티스토리에서 확인해야 한다 —
    티스토리는 GFM 을 지원하므로 대개 잘 나오지만, **이 화면이 보장하지 않는다.**
    """
    found: list[str] = []
    fenced = False
    for line in markdown.splitlines():
        if line.strip().startswith(_FENCE):
            fenced = not fenced
            continue
        if fenced:
            continue
        for pattern, name in UNSUPPORTED:
            if name not in found and pattern.search(line):
                found.append(name)
    return found


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
