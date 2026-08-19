"""기록 API. 얇게 두고 판단은 recording 과 SessionService 에 맡긴다."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from warruru_local import topics
from warruru_local.clock import local_day_bounds
from warruru_local.daemon import context, learning, recording
from warruru_local.daemon.auth import require_token
from warruru_local.store.records import LIMIT_DEFAULT
from warruru_local.daemon.models import (
    CheckpointRequest,
    FinishWorkRequest,
    RecordRequest,
    StartWorkRequest,
)
from warruru_local.daemon.validation import validate_date_param as _validate_date

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


@router.post("/works")
async def start_work(request: Request, payload: StartWorkRequest) -> dict:
    return recording.start_work(request.app.state.ctx, payload.model_dump())


@router.post("/checkpoints")
async def record_checkpoint(request: Request, payload: CheckpointRequest) -> dict:
    return recording.record_checkpoint(request.app.state.ctx, payload.model_dump())


@router.post("/records")
async def record_learning(request: Request, payload: RecordRequest) -> dict:
    return learning.record(request.app.state.ctx, payload.model_dump())


@router.get("/records")
async def list_records(
    request: Request,
    topic_slug: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = LIMIT_DEFAULT,
) -> dict:
    """`since`/`until` 은 로컬 날짜다. `until` 은 **그날을 포함한다** —
    "18일까지" 라고 적은 사람은 18일 기록을 보고 싶어 한다.
    경계는 예외 없이 `local_day_bounds` 로 만든다. 문자열을 직접 잇지 않는다.
    """
    ctx = request.app.state.ctx
    # 사람이 읽는 주제를 그대로 넘겨도 동작하게 한다. 쓰기 경로가 이미
    # 원문을 슬러그로 바꾸는데 읽기만 정확한 슬러그를 요구하면,
    # 빈 목록이 돌아오고 왜 비었는지 알 방법이 없다.
    slug = topics.slugify(topic_slug) if topic_slug else None
    start = local_day_bounds(_validate_date(since))[0] if since else None
    end = local_day_bounds(_validate_date(until))[1] if until else None
    return {
        "records": ctx.records.list_records(
            topic_slug=slug, since=start, until=end, limit=limit
        )
    }


@router.post("/works/{work_id}/finish")
async def finish_work(
    request: Request, work_id: str, payload: FinishWorkRequest
) -> dict:
    target = None if work_id == "auto" else work_id
    return recording.finish_work(request.app.state.ctx, target, payload.model_dump())


@router.post("/clients/{client_instance_id}/closed")
async def close_client(request: Request, client_instance_id: str) -> dict:
    ctx = request.app.state.ctx
    return {"closed_work_ids": ctx.sessions.close_client(client_instance_id)}


@router.get("/context")
async def get_context(
    request: Request,
    date: str | None = None,
    tool: str | None = None,
    limit: int = 10,
) -> dict:
    if date is not None:
        date = _validate_date(date)
    return context.build_context(request.app.state.ctx, date, tool, limit)
