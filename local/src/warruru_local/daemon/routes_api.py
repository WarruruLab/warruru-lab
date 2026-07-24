"""기록 API. 얇게 두고 판단은 recording 과 SessionService 에 맡긴다."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from warruru_local.daemon import context, recording
from warruru_local.daemon.auth import require_token
from warruru_local.daemon.models import (
    CheckpointRequest,
    FinishWorkRequest,
    StartWorkRequest,
)
from warruru_local.daemon.validation import validate_date_param

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


@router.post("/works")
async def start_work(request: Request, payload: StartWorkRequest) -> dict:
    return recording.start_work(request.app.state.ctx, payload.model_dump())


@router.post("/checkpoints")
async def record_checkpoint(request: Request, payload: CheckpointRequest) -> dict:
    return recording.record_checkpoint(request.app.state.ctx, payload.model_dump())


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
        date = validate_date_param(date)
    return context.build_context(request.app.state.ctx, date, tool, limit)
