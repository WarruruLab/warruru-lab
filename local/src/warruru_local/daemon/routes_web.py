"""화면. 조회는 토큰이 필요 없고, 상태를 바꾸는 요청만 토큰을 요구한다."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from warruru_local import topics
from warruru_local.clock import local_date_of, local_day_bounds, to_iso
from warruru_local.daemon import (
    asking, calendarview, careerview, certs, checking, dayview, drafting,
    learning, publishing, reading, stacking, today as todayview, topicview,
)
from warruru_local.daemon.validation import validate_date_param as _validate_date
from warruru_local.daemon.validation import validate_month_param as _validate_month

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/")
async def index(request: Request, date: str | None = None):
    """홈 — **오늘 뭐 하지**에 답한다(명세 §2.13).

    2026-09-08 까지 이 자리는 `/d/{오늘}` 로 보내는 리다이렉트였다. 아침에
    열면 그날 남긴 것이 없으니 화면이 통째로 비었다 — "이 날짜에는 기록이
    없습니다" 한 줄이 전부였고, 할 일이 하나도 안 보이니 닫고 나갔다.
    **손이 가는 기능이 전부 0건이었던 것과 같은 이야기다.**

    축마다 '오늘'을 이미 만들어 뒀는데 그것을 모으는 자리가 없었다.
    그날 기록은 `/d/{날짜}` 에, 주제 목록은 `/t` 에 그대로 있다.
    """
    ctx = request.app.state.ctx
    now = to_iso(ctx.clock.now())
    today = local_date_of(now)
    # **미래는 없다.** 아직 안 온 날에 "할 것" 도 "한 것" 도 없어서,
    # 그 화면은 무엇을 보여줘도 거짓이 된다. 넘겨받으면 오늘로 당긴다.
    day = _validate_date(date) if date else today
    if day > today:
        day = today
    지난날 = day < today

    start, end = local_day_bounds(day)
    어제 = _shift(day, -1)
    시작2, 끝2 = local_day_bounds(어제)
    처음 = ctx.records.first_record_day()
    return templates.TemplateResponse(
        request, "home.html",
        {
            # 지난날에는 '할 것' 을 세우지 않는다 — 지나간 날에 대한
            # 할 일은 뜻이 없다. 그 자리를 '그날 한 것' 이 받는다.
            "view": todayview.build(ctx, day) if not 지난날 else None,
            "past": todayview.day_summary(ctx, day) if 지난날 else None,
            "is_past": 지난날,
            "day": day,
            "prev_day": 어제 if not 처음 or 어제 >= 처음 else "",
            "next_day": _shift(day, 1) if 지난날 else "",
            "today": today,
            "weekday": _weekday(day),
            # 세는 것이 목적이 아니라 **어제와 견주는 것**이 목적이다.
            # "오늘 0건" 만으로는 그게 이상한 일인지 알 수 없다.
            "made": len(ctx.records.list_records(since=start, until=end, limit=200)),
            "made_before": len(
                ctx.records.list_records(since=시작2, until=끝2, limit=200)),
            "token": ctx.settings.token,
        },
    )


_WEEK = ("월", "화", "수", "목", "금", "토", "일")


def _weekday(day: str) -> str:
    from datetime import date as _date

    return _WEEK[_date.fromisoformat(day).weekday()]


def _shift(day: str, delta: int) -> str:
    from datetime import date as _date, timedelta

    return (_date.fromisoformat(day) + timedelta(days=delta)).isoformat()


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
    """기록 — **그날 와르르랩에 전달된 것**을 읽고, 글로 만들고, 다듬는다
    (명세 §2.14).

    전에 이 화면은 '주제' 였고 슬러그와 숫자만 있었다 —
    `db-index 9건 개념1 실험6 재료 4/4`. **205건이 다 제목을 갖고 있는데
    화면에는 하나도 없었고**, `재료 3/4` 가 무슨 뜻인지는 어디에도 안
    적혀 있지 않았다. 탭은 '기록' 인데 화면 제목은 '주제' 라 같은 곳인지도
    안 보였다.

    날짜 축은 홈과 같은 규칙이다 — 미래는 없고, 왼쪽은 첫 기록에서 멈춘다.
    """
    ctx = request.app.state.ctx
    today = local_date_of(to_iso(ctx.clock.now()))
    day = _validate_date(date) if date else today
    if day > today:
        day = today
    처음 = ctx.records.first_record_day()
    어제 = _shift(day, -1)
    return templates.TemplateResponse(
        request, "topics.html",
        {
            "view": todayview.day_records(ctx, day),
            # **날짜와 무관한 칸.** 그날 것이 없어도 쓸 수 있는 것은 있다 —
            # 그날로만 자르면 0건인 날에 화면이 통째로 빈다.
            "writable": todayview.writable(ctx),
            "day": day,
            "weekday": _weekday(day),
            "prev_day": 어제 if not 처음 or 어제 >= 처음 else "",
            "next_day": _shift(day, 1) if day < today else "",
            "today": today,
            "tally": ctx.records.tally(),
            "token": ctx.settings.token,
        },
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
            "stacks": stacking.build_index(ctx),
            # **마감은 자격증과 공고를 섞어 한 줄로 세운다.** 아침에 묻는 것은
            # "다음에 뭐가 닥치나" 하나여서다.
            "deadlines": careerview.deadlines(ctx),
            "tally": ctx.records.tally(),
            "today": local_date_of(to_iso(ctx.clock.now())),
        },
    )


@router.get("/career/stacks")
async def career_stacks(request: Request):
    """기술스택 목차 — **이력서와 공고에 적히는 말로 가른 축**(명세 §2.12).

    축 셋(로드맵 · CS · AI)은 "만들면서 겪나 / 앉아서 공부하나" 로 갈랐다.
    그 자름은 공부에는 맞지만 **이력서에 적을 때는 안 맞는다** — 공고는
    Java · Spring · RDBMS 라고 쓰지 `spring-di` 라고 쓰지 않는다.
    """
    ctx = request.app.state.ctx
    return templates.TemplateResponse(
        request, "stacks.html",
        {
            "stacks": stacking.build_index(ctx),
            "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
        },
    )


@router.get("/career/s/{key}")
async def career_stack_note(request: Request, key: str):
    """스택 하나의 정리. **목차는 슬러그가 만들고 절은 사람이 쓴다.**

    주소가 `/career/stack/{키}` 와 다르다 — 저쪽은 묶음(주제 모음)이고
    이쪽은 정리 문서다. 같은 주소를 쓰면 어느 쪽인지 모른다.
    """
    ctx = request.app.state.ctx
    view = stacking.build(ctx, key)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 스택이 없습니다"},
        )
    return templates.TemplateResponse(
        request, "stack_note.html",
        {
            "view": view, "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
        },
    )


@router.get("/career/certs")
async def career_certs(request: Request):
    """자격증 목록 — **여기서 늘리고 내린다**(명세 §2.11 c).

    코드 상수에만 있으면 딴 것도 안 볼 것도 영영 목록에 선다. 다섯 개 중
    넷이 '미시작' 인 채로 서 있는 화면은 아무것도 안 말한다.
    """
    ctx = request.app.state.ctx
    every = careerview.build_certs(ctx)
    return templates.TemplateResponse(
        request, "career_certs.html",
        {
            "certs": [c for c in every if not c["held"] and not c["dropped"]],
            "held": [c for c in every if c["held"]],
            "dropped": [c for c in every if c["dropped"]],
            "today": local_date_of(to_iso(ctx.clock.now())),
            "token": ctx.settings.token,
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


@router.get("/career/book/{key}/today")
async def book_today(request: Request, key: str, day: str | None = None):
    """책 하나의 '오늘 읽기'(명세 §2.9 b). 노트가 화면의 대부분이다."""
    ctx = request.app.state.ctx
    view = careerview.build_group(ctx, key)
    if view is None or view["axis"] != "book":
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 책이 없습니다"},
        )
    today = local_date_of(to_iso(ctx.clock.now()))
    when = day if day and reading.DAY.match(day) else today
    view["day"] = when
    view["today"] = today
    view["note"] = reading.read_note(ctx, key, when)
    view["past_days"] = [d for d in reading.days_of(ctx, key) if d != when]
    view["progress"] = reading.covered(ctx, key)
    view["reading_state"] = careerview.reading_state(view)
    return templates.TemplateResponse(
        request, "book_today.html",
        {"view": view, "today": today, "token": ctx.settings.token},
    )


@router.post("/web/books/{key}/note")
async def save_note_form(
    request: Request,
    key: str,
    day: str = Form(...),
    text: str = Form(""),
    form_token: str | None = Form(None, alias="_token"),
) -> dict:
    """자동 저장. **입력이 멈췄을 때 한 번**만 온다(명세 §2.9 b).

    돌려주는 것은 화면이 아니라 저장 시각이다 — 페이지를 다시 그리면
    커서가 튄다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not reading.write_note(ctx, key, day, text):
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 책이 없습니다"},
        )
    return {"saved_at": to_iso(ctx.clock.now())}


@router.post("/web/books/{key}/promote")
async def promote_note_form(
    request: Request,
    key: str,
    day: str = Form(...),
    cli: str = Form("codex"),
    form_token: str | None = Form(None, alias="_token"),
):
    """노트를 읽고 **바로 기록으로 올린다**(명세 §2.9 c). 확인 단계가 없다.

    되돌릴 길이 있어서 뺄 수 있다 — `/d/{날짜}` 에서 지우고 `?deleted=1`
    에서 되살린다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if cli not in ("codex", "claude"):
        raise HTTPException(status_code=400, detail={
            "code": "UNKNOWN_CLI", "message": "codex 또는 claude 만 됩니다"})
    note = reading.read_note(ctx, key, day)
    진도 = reading.covered(ctx, key)
    if not note["text"].strip():
        raise HTTPException(status_code=400, detail={
            "code": "EMPTY_NOTE", "message": "노트가 비어 있습니다"})

    ask = asking.Ask(
        topic_slug=f"book-{key}",
        prompt=reading.promote_prompt(note["text"], 진도["slugs"]),
        home=ctx.settings.home,
        cli=cli,
    )

    async def stream():
        모은글 = ""
        async for name, data in asking.run(ask):
            if name == "message":
                모은글 += data["text"]
            elif name == "error":
                yield _sse("error", data)
        made = reading.parse_candidates(모은글, 진도["slugs"])
        if made["broken"]:
            yield _sse("error", {"message": "정리한 결과를 읽지 못했습니다.",
                                 "fix": "다시 눌러 보세요."})
            yield _sse("done", {"added": [], "skipped": [], "before": 진도, "after": 진도})
            return

        now = to_iso(ctx.clock.now())
        올린것, ids = [], list(note["records"])
        for row in made["records"]:
            got = learning.record(ctx, {
                "record_id": f"rec_{uuid4().hex[:24]}",
                "client_instance_id": "web", "tool": "web",
                "kind": row["kind"], "topic": row["topic"],
                "title": row["title"], "body": row["body"],
                # **그날 날짜로 들어간다.** 지난 노트를 나중에 올려도
                # 그때 공부한 것으로 남아야 한다(명세 §2.9 e).
                "occurred_at": f"{day}T12:00:00.000Z",
            })
            ids.append(got["record_id"])
            올린것.append({"title": row["title"], "slug": got.get("topic_slug"),
                          "label": topics.label_of(got.get("topic_slug") or "")})
        reading.write_note(ctx, key, day, note["text"], records=ids)
        yield _sse("done", {
            "added": 올린것, "skipped": made["skipped"],
            "before": {"covered": 진도["covered"], "total": 진도["total"]},
            "after": {"covered": reading.covered(ctx, key)["covered"],
                      "total": 진도["total"]},
        })

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store",
                                      "X-Accel-Buffering": "no"})


@router.post("/web/books/{key}/state")
async def book_state_form(
    request: Request,
    key: str,
    state: str = Form(...),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """읽는 중 · 다음에 · 중단 · 다 읽음. **노트 파일은 안 건드린다** —
    앞머리만 고쳐서 옵시디언과 섞일 여지를 줄인다."""
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not reading.SLUG.match(key) or state not in careerview.BOOK_STATES:
        raise HTTPException(status_code=400, detail={
            "code": "BAD_STATE", "message": "그런 상태가 없습니다"})
    careerview.set_book_state(ctx, key, state)
    return RedirectResponse(f"/career/book/{quote(key)}/today", status_code=303)


@router.get("/career/books")
async def books_index(request: Request):
    """책 목록(명세 §2.9 f). 읽는 중이 맨 위, 다음에 읽을 것은
    **공고가 요구하는 주제를 많이 덮는 순**이다."""
    ctx = request.app.state.ctx
    return templates.TemplateResponse(
        request, "books.html",
        {"view": careerview.build_books(ctx), "token": ctx.settings.token,
         "today": local_date_of(to_iso(ctx.clock.now()))},
    )


@router.get("/notes/{day}")
async def notes_day(request: Request, day: str):
    """노트 전용 날짜 화면(명세 §2.9 e). **여기서 보는 것은 원문이다** —
    정리된 기록(`/d/{날짜}`)도 챗봇 답도 아니다."""
    ctx = request.app.state.ctx
    _validate_date(day)
    ctx_day = local_date_of(to_iso(ctx.clock.now()))
    return templates.TemplateResponse(
        request, "notes_day.html",
        {
            "view": {
                "day": day,
                "notes": (오늘노트 := reading.notes_on(ctx, day)),
                "promoted": sum(len(n["records"]) for n in 오늘노트),
                "strip": _recent_days(ctx, ctx_day),
                "records": dayview.build_day(ctx, day)["learnings"],
            },
            "today": ctx_day, "token": ctx.settings.token,
        },
    )


def _recent_days(ctx, today: str) -> list[dict]:
    """최근 7일 띠. 점이 있으면 그날 노트가 있다."""
    from datetime import date as _date, timedelta

    끝 = _date.fromisoformat(today)
    made = []
    for n in range(6, -1, -1):
        d = (끝 - timedelta(days=n)).isoformat()
        made.append({"day": d, "num": d[8:], "has": bool(reading.notes_on(ctx, d)),
                     "today": d == today})
    return made


@router.post("/web/topics/{topic_slug}/promote")
async def promote_form(
    request: Request,
    topic_slug: str,
    topic: str = Form(...),
    kind: str = Form("CONCEPT"),
    title: str = Form(...),
    body: str = Form(...),
    interview: str = Form(""),
    back: str = Form("/t"),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """정리를 **기록으로 올린다**(명세 §2.8).

    물어서 받은 답은 참고 자료이고 기록은 *내 말로 정리했다* 인데,
    그 사이를 건너는 다리가 없어서 답이 203건 쌓이는 동안 기록은 따로
    남겨야 했다. 이 버튼이 그 다리다.

    **`learning.record` 를 그대로 쓴다.** MCP 가 부르는 것과 같은 함수라
    슬러그 정규화도 힌트도 멱등도 한 곳에만 있다 — 여기서 따로 INSERT 하면
    두 경로가 조금씩 다른 기록을 만들기 시작한다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not title.strip() or not body.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_RECORD", "message": "제목과 본문을 적어 주세요"},
        )
    made = learning.record(ctx, {
        # 화면에서 온 것도 같은 봉투를 쓴다. `source` 만 다르다.
        "record_id": f"rec_{uuid4().hex[:24]}",
        "client_instance_id": "web",
        "tool": "web",
        "kind": kind,
        "topic": topic.strip() or topic_slug,
        "title": title.strip(),
        "body": body.strip(),
        "interview": interview.strip() or None,
        "occurred_at": to_iso(ctx.clock.now()),
    })
    슬러그 = made.get("topic_slug") or topic_slug
    return RedirectResponse(f"/t/{quote(슬러그)}", status_code=303)


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


# 답해보기의 프롬프트. **점수는 안 매기되 설명은 한다**(명세 §2.10 d,
# 2026-09-08 개정).
#
# 처음에는 빠진 것만 짚게 했다. 베껴 쓸 문장을 주지 않으려던 것인데,
# 사용자가 곧바로 뒤집었다 — **"빠진 것을 알려면 그것이 무엇인지 알아야
# 한다."** 맞는 말이다. "ISN 교환이 빠졌다" 는 이미 아는 사람에게만
# 정보이고, 모르는 사람에게는 검색어 하나가 늘 뿐이다.
#
# 사본이 되는 것을 막는 자리는 프롬프트가 아니라 **파일과 기록 쪽**이다.
# 짚어준 것은 `> ` 로 접혀 내 문장과 갈라져 저장되고, [기록으로 올리기] 의
# 본문은 언제나 내가 쓴 답이다. 설명은 읽는 것이고 기록되는 것은 내 말이다.
REVIEW_PROMPT = (
    "면접 질문에 대한 내 답을 보고 셋을 순서대로 써줘. 점수는 매기지 마라.\n"
    "① 제대로 짚은 것 — 한 줄.\n"
    "② 빠진 것 — 많아야 셋, 각각 한 줄. 없으면 없다고 말해라.\n"
    "③ 그래서 답은 — 이 질문의 답을 처음부터 짧게 설명해라. "
    "**빠진 것이 무엇인지 모르면 ②는 아무 소용이 없다.** "
    "면접에서 말할 분량으로 다섯 줄 안쪽, 용어를 쓰면 그 자리에서 한 마디로 풀어라.\n"
    "500자 안쪽, 마크다운 없이.\n\n"
    "질문: {question}\n"
    "내 답: {answer}"
)


@router.post("/web/topics/{topic_slug}/answer")
async def answer_form(
    request: Request,
    topic_slug: str,
    ask: str = Form(...),
    text: str = Form(...),
    question: str = Form(""),
    cli: str = Form("codex"),
    form_token: str | None = Form(None, alias="_token"),
):
    """질문 하나에 **말로 답해 본다**(명세 §2.10 d).

    체크는 "알고 있나" 를 3초에 묻고, 이 라우트는 "말할 수 있나" 를 묻는다.
    체크만 있으면 안다고 생각했는데 입이 안 떨어지는 자리가 안 걸리는데,
    면접에서 터지는 곳이 정확히 거기다.

    **내 답을 먼저 저장하고 그다음 묻는다.** 순서가 뒤바뀌면 자식 프로세스가
    죽거나 창을 닫는 순간 내가 쓴 문장이 통째로 없어진다. 짚어준 것은 다시
    받을 수 있지만 내 문장은 아니다.

    **대화 스레드를 쓰지 않는다.** 이건 한 번의 판정이라 이어 물을 것이
    없고, 공부 대화에 끼워 넣으면 그 대화가 판정문으로 더럽혀진다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx

    # 슬러그도 해시도 그대로 디렉터리·파일 이름이 된다. `answer_path` 가
    # 둘 다 검사하고 `None` 을 주므로, 그 값을 관문으로 쓴다.
    if not careerview.SLUG.match(topic_slug) or \
            checking.answer_path(ctx, topic_slug, ask) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 질문이 없습니다"},
        )
    답 = text.strip()
    if not 답:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_ANSWER", "message": "답을 적어 주세요"},
        )
    if cli not in ("codex", "claude"):
        raise HTTPException(
            status_code=400,
            detail={"code": "UNKNOWN_CLI", "message": "codex 또는 claude 만 됩니다"},
        )

    today = local_date_of(to_iso(ctx.clock.now()))
    checking.save_answer(ctx, topic_slug, ask, today, 답)

    물음 = asking.Ask(
        topic_slug=topic_slug,
        prompt=REVIEW_PROMPT.format(question=question.strip() or "(질문 없음)",
                                    answer=답),
        home=ctx.settings.home,
        cli=cli,
    )

    async def stream():
        parts: list[str] = []
        # 저장은 이미 끝났다. 여기서 나오는 것은 덤이다.
        yield _sse("saved", {"day": today})
        async for name, data in asking.run(물음):
            if name == "started":
                continue
            if name == "message":
                parts.append(data["text"])
            yield _sse(name, data)
        붙임 = ""
        if parts:
            붙임 = "\n\n".join(parts)
            checking.attach_review(ctx, topic_slug, ask, 붙임)
        yield _sse("done", {"reviewed": bool(붙임)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
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
    return RedirectResponse(f"/career/cert/{quote(cert_key)}", status_code=302)


@router.post("/web/stacks/{key}/section")
async def save_section_form(
    request: Request,
    key: str,
    slug: str = Form(...),
    text: str = Form(""),
    form_token: str | None = Form(None, alias="_token"),
):
    """절 하나를 저장한다. **자동 저장이 부르는 자리**라 HTML 을 안 돌려준다 —
    책 노트와 같은 규약이다. 화면이 통째로 다시 그려지면 쓰던 자리를 잃는다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not stacking.save_section(ctx, key, slug, text):
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 스택이나 주제가 없습니다"},
        )
    return {"saved_at": to_iso(ctx.clock.now())}


@router.post("/web/stacks/add")
async def add_stack_form(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not stacking.add(ctx, key.strip(), name):
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_STACK",
                    "message": "키는 영문 소문자·숫자·붙임표, 이름은 비울 수 없고, "
                               "이미 있는 것은 덮지 않습니다"},
        )
    return RedirectResponse(f"/career/s/{quote(key.strip())}", status_code=303)


@router.post("/web/stacks/{key}/move")
async def move_slug_form(
    request: Request,
    key: str,
    slug: str = Form(...),
    to: str = Form(...),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """주제를 다른 스택으로 옮긴다. **자동 분류를 사람이 고치는 자리다.**"""
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not stacking.move(ctx, slug, key, to):
        raise HTTPException(
            status_code=400,
            detail={"code": "CANNOT_MOVE", "message": "옮길 수 없습니다"},
        )
    return RedirectResponse(f"/career/s/{quote(key)}", status_code=303)


@router.post("/web/certs/add")
async def add_cert_form(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    site: str = Form(""),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """자격증 하나를 늘린다. 노트 파일 한 장이 생긴다 — **저장소 바깥이다.**"""
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not certs.add(ctx, key.strip(), name, site):
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_CERT",
                    "message": "키는 영문 소문자·숫자·붙임표, 이름은 비울 수 없고, "
                               "이미 있는 것은 덮지 않습니다"},
        )
    return RedirectResponse(f"/career/cert/{quote(key.strip())}", status_code=303)


@router.post("/web/certs/{cert_key}/status")
async def cert_status_form(
    request: Request,
    cert_key: str,
    status: str = Form(...),
    back: str = Form("/career/certs"),
    form_token: str | None = Form(None, alias="_token"),
) -> RedirectResponse:
    """볼 것 · 딴 것 · 안 볼 것을 가른다. **파일은 안 지운다** —
    지우면 적어 둔 일정과 커리큘럼이 같이 사라진다."""
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    if not certs.set_status(ctx, cert_key, status):
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 자격증이 없습니다"},
        )
    target = back if back.startswith("/") and not back.startswith("//") else "/career/certs"
    return RedirectResponse(target, status_code=302)


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


# 초안 다듬기 프롬프트. **조립기의 LLM 호출 0 은 그대로다**(명세 §2.4) —
# 6단 골격을 세우는 것은 여전히 결정적이고, 여기는 이미 선 글을 고치는
# 자리다. 자식 프로세스로 도는 것은 묻기 경로와 같다(§3.7).
#
# **재료를 늘리지 말라**는 한 줄이 이 문장의 핵심이다. 다듬다가 없는 수치와
# 없는 이유가 생기면 그 글은 면접에서 무너진다 — TODO 는 채우는 것이 아니라
# 남겨서 "여기가 내가 답 못 하는 곳" 을 표시하는 자리다(AGENTS.md §5).
POLISH_PROMPT = (
    "아래 마크다운 초안을 다듬어라. **재료를 늘리지 마라** — 원문에 없는 수치 ·"
    " 이유 · 링크를 지어내면 안 된다.\n"
    "`TODO:` 로 남은 절은 그대로 둔다. 그 자리는 내가 아직 답 못 하는 곳이라"
    " 표시로 남겨야 한다.\n"
    "고칠 것은 문장이다 — 겹치는 말을 줄이고, 순서를 바로잡고, 제목을 내용에"
    " 맞춘다. 6단 구조(문제 · 선택 · 구현 · 측정 · 결과 · 한계)는 유지한다.\n"
    "마크다운 전문만 답으로 내라. 설명이나 인사말을 붙이지 마라.\n"
)

REWRITE_PROMPT = (
    "아래 마크다운 초안을 **처음부터 다시 써라.** 재료는 원문에 있는 것뿐이다 —"
    " 없는 수치 · 이유 · 링크를 지어내면 안 된다.\n"
    "6단 구조(문제 · 선택 · 구현 · 측정 · 결과 · 한계)를 지키고,"
    " `TODO:` 로 남은 절은 그대로 `TODO:` 로 남긴다.\n"
    "마크다운 전문만 답으로 내라. 설명이나 인사말을 붙이지 마라.\n"
)


@router.post("/web/drafts/{draft_id}/polish")
async def polish_draft_form(
    request: Request,
    draft_id: str,
    mode: str = Form("polish"),
    ask: str = Form(""),
    cli: str = Form("codex"),
    form_token: str | None = Form(None, alias="_token"),
):
    """초안을 **화면에서** 다듬거나 다시 쓴다 (명세 §2.14).

    전에는 `polish topic=… draft=…` 한 줄을 복사해 터미널에 붙여넣었다.
    옮겨 적는 수고가 남아 있으면 그 단계에서 멈추고, 실제로 초안 57건에
    발행이 0건이었다.

    **덮어쓰지 않는다.** 받은 글을 화면에 보여주고, 사람이 [이 글로 바꾸기]
    를 눌러야 저장된다. 다듬은 결과가 원문보다 나쁠 수 있고, 그때 원문이
    이미 사라졌으면 되돌릴 방법이 없다.
    """
    _check_token(request, form_token)
    ctx = request.app.state.ctx
    view = topicview.build_draft(ctx, draft_id)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "그런 초안이 없습니다"},
        )
    if cli not in ("codex", "claude"):
        raise HTTPException(
            status_code=400,
            detail={"code": "UNKNOWN_CLI", "message": "codex 또는 claude 만 됩니다"},
        )

    머리 = REWRITE_PROMPT if mode == "rewrite" else POLISH_PROMPT
    if ask.strip():
        머리 += f"\n특별히 이것을 고쳐라: {ask.strip()}\n"
    물음 = asking.Ask(
        topic_slug=view["topic_slug"],
        prompt=f"{머리}\n---\n{view['markdown']}",
        home=ctx.settings.home,
        cli=cli,
    )

    async def stream():
        async for name, data in asking.run(물음):
            if name == "started":
                continue
            yield _sse(name, data)
        yield _sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


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
