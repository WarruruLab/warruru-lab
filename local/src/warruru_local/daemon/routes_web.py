"""화면. 조회는 토큰이 필요 없고, 상태를 바꾸는 요청만 토큰을 요구한다."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from warruru_local.clock import local_date_of, local_day_bounds, to_iso
from warruru_local.daemon import (
    asking, calendarview, careerview, dayview, drafting, publishing, topicview,
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
        request, "topic_empty.html" if view["empty"] else "topic.html",
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
    """포트폴리오 허브 — **계기판이다**(2026-09-07 재설계).

    먼저 오는 것은 **마감**이다. 자격증과 공고를 섞어 가까운 순으로 세운다.
    그다음이 **0인 것들** — 질문 체크 0, 발행 0 처럼 만들어 두고 안 쓰는
    자리를 숫자로 드러낸다. 안 보이면 계속 0으로 남는다.

    기술스택과 채용공고를 갈라 놓던 구조는 유지한다. 묻는 것이 다르고
    보는 주기도 달라서다 — 다만 **마감만은 위에서 합친다.**
    """
    ctx = request.app.state.ctx
    companies = careerview.list_companies(ctx)
    stack = careerview.build_stack(ctx)
    return templates.TemplateResponse(
        request, "career.html",
        {
            "companies": companies,
            "stack": stack,
            "books": stack["books"],
            "certs": careerview.build_certs(ctx),
            # **마감은 자격증과 공고를 섞어 한 줄로 세운다.** 아침에 묻는 것은
            # "다음에 뭐가 닥치나" 하나여서다.
            "deadlines": careerview.deadlines(ctx),
            "tally": ctx.records.tally(),
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


@router.get("/career/cert/{key}")
async def career_cert(request: Request, key: str):
    ctx = request.app.state.ctx
    view = careerview.build_cert(ctx, key)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 자격증이 없습니다"},
        )
    return templates.TemplateResponse(
        request, "career_cert.html",
        {
            "view": view, "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
        },
    )


@router.get("/career/stack/{key}")
async def career_group(request: Request, key: str):
    ctx = request.app.state.ctx
    view = careerview.build_group(ctx, key)
    # 책은 `/career/book/` 아래다. 두 주소가 같은 것을 열면 어느 쪽인지 모른다.
    if view is not None and view["axis"] == "book":
        view = None
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 묶음이 없습니다"},
        )
    return templates.TemplateResponse(
        request, "career_group.html",
        {
            "view": view, "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
        },
    )


@router.get("/career/book/{key}")
async def career_book(request: Request, key: str):
    """책 한 권이 덮는 주제. 묶음 화면과 같은 모양을 쓴다 —
    "이 책을 읽으면 어느 질문에 답할 수 있게 되는가" 가 같은 질문이라서다.
    """
    ctx = request.app.state.ctx
    view = careerview.build_group(ctx, key)
    if view is None or view["axis"] != "book":
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 책이 없습니다"},
        )
    return templates.TemplateResponse(
        request, "career_group.html",
        {
            "view": view, "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
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


@router.post("/web/topics/{topic_slug}/asks")
async def toggle_ask_form(
    request: Request,
    topic_slug: str,
    ask: str = Form(...),
    text: str = Form(""),
    back: str = Form("/career/stack"),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """면접 질문 하나를 켜고 끈다. 상태를 바꾸므로 토큰을 요구한다.

    **기록과 다른 값이다.** 체크는 "답할 수 있다", 기록은 "내 말로 정리했다".
    3초짜리와 5분짜리를 같은 문턱에 두면 아무것도 안 눌린다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    # 연결이 `isolation_level=None`(자동 커밋)이라 따로 커밋하지 않는다.
    ctx.records.toggle_ask(topic_slug, ask, text, to_iso(ctx.clock.now()))
    # 돌아갈 곳은 폼이 알려준다. 같은 질문이 묶음 화면과 주제 화면 양쪽에
    # 있어서, 어디서 눌렀는지 서버가 짐작하면 다른 화면으로 튕긴다.
    target = back if back.startswith("/") and not back.startswith("//") else "/career/stack"
    return RedirectResponse(target, status_code=302)


# 하루치 대화를 공부 기록으로 접는 프롬프트. **재료가 없으면 지어내지 말라**는
# 한 줄이 이 문장의 핵심이다 — 정리가 창작이 되는 순간 그 파일을 못 믿는다.
SUMMARY_PROMPT = (
    "오늘 이 주제로 나눈 대화를 공부 기록으로 정리해줘. 세 부분이다 — "
    "① 오늘 알게 된 것, ② 아직 막히는 것, ③ 다음에 볼 것. "
    "**대화에 나온 것만 쓴다.** 없으면 그 절을 비우고 비었다고 적어라. "
    "내가 한 말과 네가 설명한 것을 구분해서, 내가 이해했다고 말한 것만 ①에 넣어라. "
    "마크다운으로, 500자 안쪽."
)


@router.post("/web/topics/{topic_slug}/ask")
async def ask_form(
    request: Request,
    topic_slug: str,
    prompt: str = Form(""),
    fresh: int = Form(0),
    cli: str = Form("codex"),
    mode: str = Form("ask"),
    form_token: str | None = Form(None, alias="_token"),
):
    """그 주제에 대해 묻는다. 답은 도착하는 대로 흐른다(명세 §3.7).

    **데몬은 모델을 모른다.** 이미 로그인된 CLI 를 자식 프로세스로 띄우고
    표준출력을 읽을 뿐이다. 상태를 바꾸므로(답 파일이 생긴다) 토큰을 요구한다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx

    # **이 값이 그대로 디렉터리 이름이 된다**(`career/answers/{키}/`).
    # 검사하지 않으면 `..` 하나로 답 파일이 홈 밖에 앉는다. 회사 노트가
    # 같은 이유로 이미 같은 검사를 한다(`careerview.SLUG`).
    if not careerview.SLUG.match(topic_slug):
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 주제가 없습니다"},
        )

    asked = prompt.strip()
    if mode == "summary":
        # **정리 프롬프트는 코드에 둔다.** 화면에서 만들면 버전도 테스트도
        # 안 붙고, 두 화면이 조금씩 다른 문장을 보내기 시작한다.
        asked = SUMMARY_PROMPT
    if not asked:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PROMPT", "message": "물어볼 것을 적어 주세요"},
        )

    if cli not in ("codex", "claude"):
        raise HTTPException(
            status_code=400,
            detail={"code": "UNKNOWN_CLI", "message": "codex 또는 claude 만 됩니다"},
        )
    if fresh:
        ctx.records.forget_thread(topic_slug)
    row = ctx.records.ask_thread(topic_slug)
    # **CLI 를 바꾸면 대화를 잇지 않는다.** 스레드 id 는 그 CLI 안에서만
    # 뜻이 있어서, codex 의 id 를 claude 에 넘기면 조용히 새 대화가 열리거나
    # 실패한다. 갈아탈 때는 새로 시작하는 것이 정직하다.
    이어감 = row is not None and row["cli"] == cli
    ask = asking.Ask(
        topic_slug=topic_slug,
        prompt=asked,
        home=ctx.settings.home,
        cli=cli,
        thread_id=row["thread_id"] if 이어감 else None,
    )

    async def stream():
        thread_id = ask.thread_id
        parts: list[str] = []
        tokens = 0
        async for name, data in asking.run(ask):
            if name == "started":
                thread_id = data["thread_id"]
                yield _sse("started", {"thread_id": thread_id,
                                       "resumed": bool(ask.thread_id)})
                continue
            if name == "usage":
                tokens = data["tokens"]
                continue
            if name == "message":
                parts.append(data["text"])
            yield _sse(name, data)

        # **답을 받았을 때만** 스레드를 붙잡는다. 실패한 왕복까지 세면
        # 다음 질문이 없는 대화를 이어받으려 한다.
        saved = ""
        if parts:
            now = to_iso(ctx.clock.now())
            if thread_id:
                ctx.records.remember_thread(topic_slug, thread_id, ask.cli, now)
            saved = topicview.append_answer(
                ctx, topic_slug,
                "오늘 정리" if mode == "summary" else asked,
                "\n\n".join(parts), local_date_of(now), ask.cli,
            )
        yield _sse("done", {"tokens": tokens, "saved": saved})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # 프록시가 없어도 붙여 둔다. 이 줄이 없으면 어떤 브라우저는
        # 답이 다 올 때까지 아무것도 안 그린다.
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/web/certs/{cert_key}/progress")
async def bump_cert_form(
    request: Request,
    cert_key: str,
    item: str = Form(...),
    text: str = Form(""),
    total: int = Form(0),
    delta: int = Form(1),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """커리큘럼 한 항목의 진도를 올리고 내린다."""
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    ctx.records.bump_cert_item(
        cert_key, item, text, max(-1, min(1, delta)), total,
        to_iso(ctx.clock.now()),
    )
    return RedirectResponse(f"/career/cert/{cert_key}", status_code=302)


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
