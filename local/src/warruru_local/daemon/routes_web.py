"""화면. 조회는 토큰이 필요 없고, 상태를 바꾸는 요청만 토큰을 요구한다."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from warruru_local.clock import local_date_of, local_day_bounds, to_iso
from warruru_local.daemon import dayview, drafting, publishing, topicview
from warruru_local.daemon.validation import validate_date_param as _validate_date

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/")
async def index(request: Request) -> RedirectResponse:
    ctx = request.app.state.ctx
    return RedirectResponse(f"/d/{local_date_of(to_iso(ctx.clock.now()))}", status_code=302)


@router.get("/d/{date}")
async def day(request: Request, date: str, deleted: int = 0):
    ctx = request.app.state.ctx
    _validate_date(date)
    view = dayview.build_day(ctx, date, include_deleted=bool(deleted))
    template = "deleted.html" if deleted else "day.html"
    return templates.TemplateResponse(
        request, template, {"view": view, "token": ctx.settings.token}
    )


@router.get("/t")
async def topics_index(request: Request):
    """오늘 자정~자정 구간의 주제별 요약. 조회이므로 토큰이 필요 없다."""
    ctx = request.app.state.ctx
    today = local_date_of(to_iso(ctx.clock.now()))
    view = topicview.build_index(ctx, today)
    return templates.TemplateResponse(
        request, "topics.html", {"view": view, "today": today}
    )


@router.get("/t/{topic_slug}")
async def topic_detail(request: Request, topic_slug: str):
    ctx = request.app.state.ctx
    view = topicview.build_detail(ctx, topic_slug)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그 주제의 기록이 없습니다"},
        )
    today = local_date_of(to_iso(ctx.clock.now()))
    return templates.TemplateResponse(
        request, "topic.html",
        {"view": view, "today": today, "token": ctx.settings.token}
    )


@router.get("/drafts/{draft_id}")
async def draft_detail(request: Request, draft_id: str):
    ctx = request.app.state.ctx
    view = topicview.build_draft(ctx, draft_id)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        )
    today = local_date_of(to_iso(ctx.clock.now()))
    return templates.TemplateResponse(
        request, "draft.html",
        {"view": view, "today": today, "token": ctx.settings.token},
    )


def _check_token(request: Request, token: str | None) -> None:
    """다른 출처의 페이지가 로컬 데몬을 조작하지 못하게 한다.

    `/web/*` 는 `/v1/*` 인증 미들웨어 바깥이므로 이 폼 토큰이 유일한
    방어선이다.
    """
    if token != request.app.state.ctx.settings.token:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "토큰이 올바르지 않습니다"},
        )


def _back(date: str) -> RedirectResponse:
    return RedirectResponse(f"/d/{date}", status_code=302)


@router.post("/web/drafts/{draft_id}/published")
async def mark_published_form(
    request: Request,
    draft_id: str,
    form_token: str | None = Form(None, alias="_token"),
    published_url: str = Form(...),
) -> RedirectResponse:
    """붙여넣고 돌아와 URL 을 적는 자리. 상태를 바꾸므로 토큰을 요구한다."""
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    try:
        publishing.mark_published(ctx, draft_id, published_url)
    except publishing.DraftNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        ) from None
    return RedirectResponse(f"/drafts/{draft_id}", status_code=302)


@router.post("/web/topics/{topic_slug}/draft")
async def create_draft_form(
    request: Request,
    topic_slug: str,
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """[초안 만들기] 버튼. 상태를 바꾸므로 폼 토큰을 요구한다.

    API 와 **같은 함수**를 부른다. 갈라지면 두 경로의 동작이 조용히 달라진다.
    """
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    try:
        result = drafting.create(ctx, topic_slug)
    except drafting.NoRecordsError:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그 주제의 기록이 없습니다"},
        ) from None
    return RedirectResponse(f"/drafts/{result['draft_id']}", status_code=302)


@router.post("/web/works/{work_id}/delete")
async def delete_work(
    request: Request,
    work_id: str,
    form_token: str | None = Form(None, alias="_token"),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    ctx.repo.soft_delete_work(work_id, to_iso(ctx.clock.now()))
    return _back(_validate_date(date))


@router.post("/web/works/{work_id}/restore")
async def restore_work(
    request: Request,
    work_id: str,
    form_token: str | None = Form(None, alias="_token"),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    ctx.repo.restore_work(work_id)
    return _back(_validate_date(date))


@router.post("/web/checkpoints/{checkpoint_id}/delete")
async def delete_checkpoint(
    request: Request,
    checkpoint_id: str,
    form_token: str | None = Form(None, alias="_token"),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    ctx.repo.soft_delete_checkpoint(checkpoint_id, to_iso(ctx.clock.now()))
    return _back(_validate_date(date))


@router.post("/web/checkpoints/{checkpoint_id}/restore")
async def restore_checkpoint(
    request: Request,
    checkpoint_id: str,
    form_token: str | None = Form(None, alias="_token"),
    date: str = Form(...),
) -> RedirectResponse:
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    ctx.repo.restore_checkpoint(checkpoint_id)
    return _back(_validate_date(date))
