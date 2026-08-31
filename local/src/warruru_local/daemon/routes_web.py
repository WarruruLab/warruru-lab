"""화면. 조회는 토큰이 필요 없고, 상태를 바꾸는 요청만 토큰을 요구한다."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from warruru_local.clock import local_date_of, local_day_bounds, to_iso
from warruru_local.daemon import (
    calendarview, careerview, dayview, drafting, publishing, topicview,
)
from warruru_local.daemon.validation import validate_date_param as _validate_date
from warruru_local.daemon.validation import validate_month_param as _validate_month

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


@router.get("/c/{year_month}")
async def calendar_month(request: Request, year_month: str):
    """한 달의 격자. 조회이므로 토큰이 필요 없다."""
    ctx = request.app.state.ctx
    _validate_month(year_month)
    today = local_date_of(to_iso(ctx.clock.now()))
    view = calendarview.build_month(ctx, year_month, today)
    return templates.TemplateResponse(
        request, "calendar.html", {"view": view, "today": today}
    )


@router.get("/t")
async def topics_index(request: Request, date: str | None = None):
    """선택한 로컬 날짜의 주제별 요약. 날짜가 없으면 오늘이다."""
    ctx = request.app.state.ctx
    today = local_date_of(to_iso(ctx.clock.now()))
    selected = _validate_date(date) if date else today
    view = topicview.build_index(ctx, selected)
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
async def draft_detail(
    request: Request,
    draft_id: str,
    push: str | None = None,
    push_error: str | None = None,
    ask: str | None = None,
    saved: str | None = None,
):
    ctx = request.app.state.ctx
    view = topicview.build_draft(ctx, draft_id, ask=ask)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        )
    today = local_date_of(to_iso(ctx.clock.now()))
    return templates.TemplateResponse(
        request, "draft.html",
        {
            "view": view, "today": today, "token": ctx.settings.token,
            # 밀어 넣기 결과. 리다이렉트로 돌아오므로 쿼리로 실어 온다.
            "push": push, "push_error": push_error, "saved": saved,
        },
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


@router.get("/career")
async def career_index(request: Request):
    """포트폴리오 허브. **두 갈래로 갈라 놓는다.**

    기술스택은 '무엇을 공부할까' 를, 채용공고는 '어디에 지원할까' 를 묻는다.
    두 축은 묻는 것이 다르고 보는 주기도 다르다 — 한 화면에 섞으면 어느
    쪽도 훑기 어려워진다.
    """
    ctx = request.app.state.ctx
    companies = careerview.list_companies(ctx)
    return templates.TemplateResponse(
        request, "career.html",
        {
            "companies": companies,
            "stack": careerview.build_stack(ctx),
            "today": local_date_of(to_iso(ctx.clock.now())),
        },
    )


@router.get("/career/stack")
async def career_stack(request: Request):
    ctx = request.app.state.ctx
    return templates.TemplateResponse(
        request, "career_stack.html",
        {
            "view": careerview.build_stack(ctx),
            "today": local_date_of(to_iso(ctx.clock.now())),
        },
    )


@router.get("/career/companies")
async def career_companies(request: Request):
    ctx = request.app.state.ctx
    return templates.TemplateResponse(
        request, "career_companies.html",
        {
            "companies": careerview.list_companies(ctx),
            "today": local_date_of(to_iso(ctx.clock.now())),
        },
    )


@router.get("/career/c/{slug}")
async def career_detail(request: Request, slug: str):
    """회사 상세. **`/career/c/` 아래 둔다.**

    `/career/{slug}` 로 두면 `stack` · `companies` 같은 이름의 회사가 생기는
    순간 어느 쪽인지 알 수 없다. 지금은 그런 회사가 없지만, 그 충돌은
    생기고 나서 고치면 이미 링크가 퍼진 뒤다.
    """
    ctx = request.app.state.ctx
    view = careerview.build_company(ctx, slug)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 회사 노트가 없습니다"},
        )
    return templates.TemplateResponse(
        request, "career_detail.html",
        {"view": view, "today": local_date_of(to_iso(ctx.clock.now()))},
    )


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


@router.post("/web/drafts/{draft_id}/edit")
async def edit_draft_form(
    request: Request,
    draft_id: str,
    markdown: str = Form(...),
    form_token: str | None = Form(None, alias="_token"),
):
    """화면에서 고친 본문을 그대로 저장한다.

    `save_draft` 툴과 **같은 함수**로 간다. 두 경로가 갈리면 에이전트가 다듬은
    글과 사람이 다듬은 글이 다른 규칙으로 저장된다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    view = topicview.build_draft(ctx, draft_id)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        )
    made = drafting.create(ctx, view["topic_slug"], markdown=markdown)
    return RedirectResponse(f"/drafts/{made['draft_id']}?saved=1", status_code=302)


@router.post("/web/drafts/{draft_id}/push")
async def push_draft_form(
    request: Request,
    draft_id: str,
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """초안을 비공개 git 저장소에 밀어 넣는다. 상태를 바꾸므로 토큰을 요구한다.

    **비공개 확인에 실패하면 예외가 아니라 화면 메시지로 돌려보낸다.**
    이 실패는 사람이 고칠 수 있는 실패다 — 500 으로 새어 나가면
    무엇을 고쳐야 하는지 알 수 없다.
    """
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    try:
        result = publishing.push_to_repo(ctx, draft_id)
    except publishing.DraftNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        ) from None
    except publishing.PushUnavailableError as error:
        return RedirectResponse(
            f"/drafts/{draft_id}?push_error={quote(str(error))}", status_code=302
        )
    state = "pushed" if result.pushed else "committed"
    return RedirectResponse(f"/drafts/{draft_id}?push={state}", status_code=302)


@router.post("/web/drafts/from-records")
async def create_draft_from_records(
    request: Request,
    record_id: list[str] = Form(default=[]),
    date: str | None = Form(None),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """체크한 기록만으로 초안을 만든다. 상태를 바꾸므로 토큰을 요구한다.

    **나중에 LLM 을 붙일 자리다.** 지금은 결정적 조립기가 재료를 절에 나눠
    담고, 그 자리에 모델 호출이 들어가도 이 라우트는 그대로다 —
    화면이 하는 일은 '무엇을 재료로 쓸지 고르는 것' 하나이기 때문이다.
    """
    ctx = request.app.state.ctx
    _check_token(request, form_token)
    try:
        result = drafting.create_from_records(ctx, record_id)
    except drafting.NoRecordsError:
        # 하나도 안 고르고 눌렀다. 오류 화면 대신 하던 자리로 돌려보낸다 —
        # 고칠 것이 '다시 고르기' 뿐인데 화면을 갈아탈 이유가 없다.
        return _back(date or local_date_of(to_iso(ctx.clock.now())))
    return RedirectResponse(f"/drafts/{result['draft_id']}", status_code=302)


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
