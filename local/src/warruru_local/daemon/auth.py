"""토큰 인증. /v1/health 를 제외한 모든 /v1 요청에 필요하다."""

from __future__ import annotations

from fastapi import HTTPException, Request

HEADER = "X-Warruru-Token"


def require_token(request: Request) -> None:
    expected = request.app.state.ctx.settings.token
    provided = request.headers.get(HEADER)
    if not provided or provided != expected:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "토큰이 없거나 올바르지 않습니다"},
        )
