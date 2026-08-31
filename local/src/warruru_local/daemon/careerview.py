"""회사별 준비 노트 화면. **파일만 읽는다.**

여기서 데몬이 하는 일은 `~/.warruru/career/*.md` 를 목록으로 보여주고 한 장을
렌더하는 것뿐이다. 노션에는 닿지 않는다 — 공고 원본을 읽는 쪽은 에이전트이고,
데몬이 외부 네트워크에 의존하기 시작하면 비행기 안에서 이 화면이 무너진다.
그래서 새 테이블도 만들지 않는다. 파일이 곧 자료다.
"""

from __future__ import annotations

import re
from pathlib import Path

from warruru_local import paths
from warruru_local.publish import tistory_clipboard

# 파일 이름이 곧 URL 이다. **여기를 느슨하게 두면 경로 탈출이 된다** —
# `/career/..%2f..%2f.ssh%2fid_rsa` 같은 요청이 홈 디렉터리 밖을 읽는다.
# 화이트리스트로 받고, 그 뒤에 실제 경로가 career 디렉터리 안인지 한 번 더 본다.
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _root(ctx) -> Path:
    return paths.career_dir(ctx.settings.home)


def _title_of(text: str, slug: str) -> str:
    """첫 `# ` 제목을 쓴다. 없으면 파일 이름이 제목이다."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or slug
    return slug


def list_companies(ctx) -> list[dict]:
    root = _root(ctx)
    if not root.is_dir():
        return []
    made = []
    for path in root.glob("*.md"):
        if not SLUG.match(path.stem):
            # 사람이 손으로 넣은 파일도 목록에는 보이게 하되 링크는 걸지 않는다.
            made.append({"slug": None, "name": path.name, "title": path.stem})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        made.append({
            "slug": path.stem,
            "name": path.name,
            "title": _title_of(text, path.stem),
        })
    return sorted(made, key=lambda row: row["title"])


def build_company(ctx, slug: str) -> dict | None:
    if not SLUG.match(slug):
        return None
    root = _root(ctx)
    path = root / f"{slug}.md"
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        # 심볼릭 링크로 밖을 가리키는 경우까지 여기서 걸린다.
        return None
    if not resolved.is_file():
        return None
    body = resolved.read_text(encoding="utf-8", errors="replace")
    return {
        "slug": slug,
        "title": _title_of(body, slug),
        "markdown": body,
        "html": tistory_clipboard.to_html(body),
    }
