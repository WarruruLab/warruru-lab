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


class RecordRequest(CommonFields):
    """학습 기록. **필수 필드를 여기서 강제하지 않는다.**

    pydantic 이 거절하면 그 기록은 사라지고, 거절은 '기록 안 하기'를 가장
    안전한 선택으로 만든다(명세 §4.1). 비어 있는 값은 응답의 `missing_fields`
    로 알린다. 그래서 `kind`·`topic`·`title`·`body` 도 기본값을 갖는다.
    """

    record_id: str
    work_id: str | None = None
    kind: str = ""
    topic: str = ""
    title: str = ""
    body: str = ""
    rationale: str | None = None
    outcome: str | None = None
    limitation: str | None = None
    interview: str | None = None
    occurred_at: str | None = None
    repo_path: str | None = None


class DraftRequest(BaseModel):
    """초안 만들기 또는 덮어쓰기.

    `markdown` 이 없으면 조립기가 기록에서 만든다(버튼 경로).
    있으면 그것을 그대로 저장한다(`save_draft` — 에이전트가 다듬은 글).
    조립기로 다시 만들어 버리면 다듬은 문장이 통째로 사라진다.

    재료를 고르는 일은 `markdown` 이 없을 때만 서버가 한다 —
    클라이언트가 기록 목록을 골라 보내면 두 곳의 판단이 갈린다.
    """

    topic_slug: str
    title: str | None = None
    markdown: str | None = None
    source_record_ids: list[str] | None = None


class FinishWorkRequest(CommonFields):
    result: str | None = None
    limitations: str | None = None
    next_steps: str | None = None
    ended_at: str | None = None
    repo_path: str | None = None
