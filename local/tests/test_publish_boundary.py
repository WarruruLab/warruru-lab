"""`publish/` 는 DB 를 모른다. **관례가 아니라 실행되는 테스트로 강제한다.**

지키는 것은 발행 코드의 청결이 아니라 **'데몬이 SQLite 의 유일한 writer'**
라는 전제다. 그 전제는 문서 관례로는 못 지킨다 —
'데몬 API 한 번 더 부르느니 커서 하나 열자' 는 유혹이 반드시 오고,
그때 전제가 조용히 깨진다.
"""

import ast
import pathlib

import pytest

import warruru_local.publish as publish_package

PACKAGE_ROOT = pathlib.Path(publish_package.__file__).parent
FORBIDDEN_TOP_LEVEL = {"sqlite3"}
FORBIDDEN_PREFIX = "warruru_local.store"


def _modules():
    files = sorted(PACKAGE_ROOT.glob("*.py"))
    assert files, "publish 패키지에 파일이 없다 — 경계 테스트가 헛돌고 있다"
    return files


def _imports(path: pathlib.Path) -> set[str]:
    """`from . import x` 같은 상대 임포트도 잡는다.

    `ast.ImportFrom` 은 상대 임포트에서 패키지 이름을 담지 않으므로
    `node.level` 을 함께 봐야 한다. 안 보면 경계가 뚫려도 초록이다.
    """
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                found.add("." * node.level + (node.module or ""))
            elif node.module:
                found.add(node.module)
    return found


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.name)
def test_publish_패키지는_sqlite3_를_임포트하지_않는다(path):
    assert not (FORBIDDEN_TOP_LEVEL & {name.split(".")[0] for name in _imports(path)})


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.name)
def test_publish_패키지는_store_를_임포트하지_않는다(path):
    offenders = {n for n in _imports(path) if n.startswith(FORBIDDEN_PREFIX)}
    assert offenders == set(), f"{path.name} 이 저장소 계층을 임포트한다: {offenders}"


def test_위반을_실제로_잡는다(tmp_path):
    """테스트가 있는데 위반을 못 잡으면 없는 것과 같다.

    임시 파일로 위반을 만들어 검출 로직 자체를 검증한다 —
    실제 패키지를 더럽히지 않고 확인할 수 있어야 한다.
    """
    offender = tmp_path / "bad.py"
    offender.write_text(
        "import sqlite3\nfrom warruru_local.store.records import RecordRepository\n",
        encoding="utf-8",
    )
    names = _imports(offender)
    assert "sqlite3" in names
    assert any(name.startswith(FORBIDDEN_PREFIX) for name in names)


def test_상대_임포트도_잡는다(tmp_path):
    offender = tmp_path / "bad_relative.py"
    offender.write_text("from . import base\nfrom ..store import records\n",
                        encoding="utf-8")
    names = _imports(offender)
    assert "." in names and "..store" in names
