"""요청 경계 공통 검증. 잘못된 입력은 여기서 표준 400 으로 바꾼다.

파싱 실패를 저장소 오류와 구분하려면 "입력이 이상하다"는 판단을 입력을
받는 경계(라우트)에서 내려야 한다 — 앱 전역 `ValueError` 핸들러로 뭉뚱그리면
저장소 계층에서 우연히 난 `ValueError`까지 클라이언트 잘못으로 오보된다.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

_INVALID_DATE_DETAIL = {
    "code": "INVALID_REQUEST",
    "message": "날짜는 YYYY-MM-DD 여야 합니다",
}

_INVALID_MONTH_DETAIL = {
    "code": "INVALID_REQUEST",
    "message": "달은 YYYY-MM 여야 합니다",
}


def validate_date_param(value: str) -> str:
    """`%Y-%m-%d`는 자릿수를 강제하지 않는다(예: "2026-7-22"도 통과시킨다).

    요청으로 받는 날짜는 항상 자릿수가 맞아야 하므로 형태부터 정규식으로
    거른 뒤, 존재하지 않는 날짜(예: 2026-02-30)는 strptime 으로 한 번 더
    걸러낸다. 실패하면 표준 400 봉투를 담은 `HTTPException` 을 낸다.
    """
    if not _DATE_RE.match(value):
        raise HTTPException(status_code=400, detail=dict(_INVALID_DATE_DETAIL))
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=dict(_INVALID_DATE_DETAIL)) from None
    return value


def validate_month_param(value: str) -> str:
    """`YYYY-MM`. 날짜와 같은 이유로 정규식이 먼저다.

    `2026-13` 은 형태가 맞아도 달이 아니다. 통과시키면 달력이 다음 해
    1월을 13월이라 부르며 그린다. `-01` 을 붙여 실재하는 날인지 확인한다.
    """
    if not _MONTH_RE.match(value):
        raise HTTPException(status_code=400, detail=dict(_INVALID_MONTH_DETAIL))
    try:
        datetime.strptime(value + "-01", "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=dict(_INVALID_MONTH_DETAIL)) from None
    return value
