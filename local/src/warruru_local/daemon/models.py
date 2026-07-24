"""요청·응답 스키마. 상한을 넘는 값은 거절하지 않고 라우터에서 자른다."""

from __future__ import annotations

from pydantic import BaseModel

CHECKPOINT_TYPES = {
    "PROBLEM",
    "ATTEMPT",
    "FAILED_ATTEMPT",
    "ERROR",
    "TEST_RESULT",
    "DECISION",
    "RESULT",
    "LIMITATION",
    "NOTE",
}


class CommonFields(BaseModel):
    client_instance_id: str | None = None
    tool: str = "unknown"
    cwd: str | None = None
    client_name: str | None = None
    client_version: str | None = None


class StartWorkRequest(CommonFields):
    work_id: str
    title: str | None = None
    goal: str | None = None
    started_at: str | None = None
    repo_path: str | None = None


class CheckpointRequest(CommonFields):
    checkpoint_id: str
    work_id: str | None = None
    type: str
    title: str
    body: str | None = None
    files: list[str] | None = None
    error_excerpt: str | None = None
    tags: list[str] | None = None
    occurred_at: str | None = None
    repo_path: str | None = None


class FinishWorkRequest(CommonFields):
    result: str | None = None
    limitations: str | None = None
    next_steps: str | None = None
    ended_at: str | None = None
    repo_path: str | None = None
