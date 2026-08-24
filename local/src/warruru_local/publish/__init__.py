"""발행 어댑터. **이 패키지는 DB 를 모른다.**

경계는 필요하지만 프로세스는 필요 없다. MVP 에서 발행이 하는 일은 파일 쓰기라
데몬을 오염시킬 실패 모드가 아직 없다. 그러나 나중에 외부를 실제로 때리는
어댑터가 붙을 때 프로세스 분리를 재검토하려면, 그때 이미 임포트 경계가
지켜져 있어야 분리 비용이 싸다.

`sqlite3` 와 `warruru_local.store.*` 임포트는 `tests/test_publish_boundary.py`
가 AST 로 검출한다. 관례로 두면 '데몬 API 한 번 더 부르느니 커서 하나 열자'
는 유혹에 조용히 뚫린다.
"""

from warruru_local.publish.base import PublishResult, PublishTarget
from warruru_local.publish.markdown_file import MarkdownFileTarget

__all__ = ["PublishResult", "PublishTarget", "MarkdownFileTarget"]
