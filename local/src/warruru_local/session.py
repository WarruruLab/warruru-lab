"""세션 귀속과 마감. 순수 규칙이며 HTTP 와 파일 시스템을 모른다.

귀속 우선순위(기능 명세 F-03)
  1. 요청의 work_id
  2. 같은 대화의 진행 중 세션      <- 대화 하나 = 작업 하나. 가장 믿을 만한 신호
  3. 같은 머신·도구·저장소 + 시간창 <- 어댑터가 재기동되어 대화 식별자가 바뀐 경우
  4. 새 세션
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from warruru_local.clock import Clock, to_iso
from warruru_local.config import Settings
from warruru_local.gitinfo import GitSnapshot
from warruru_local.ids import new_id
from warruru_local.store.repository import Repository


@dataclass(frozen=True)
class Attachment:
    work: dict
    attached_by: str


class SessionService:
    def __init__(
        self,
        repo: Repository,
        clock: Clock,
        settings: Settings,
        id_factory=new_id,
    ) -> None:
        self.repo = repo
        self.clock = clock
        self.settings = settings
        self._id_factory = id_factory

    # ------------------------------------------------------------------

    def start(
        self,
        *,
        work_id: str,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        title: str | None,
        goal: str | None,
        snapshot: GitSnapshot,
        started_at: str | None = None,
    ) -> tuple[dict, bool]:
        now = started_at or to_iso(self.clock.now())
        work, duplicate = self.repo.insert_work(
            work_id=work_id,
            machine_id=machine_id,
            client_instance_id=client_instance_id,
            tool=tool,
            title=title,
            title_origin="USER" if title else None,
            goal=goal,
            origin="EXPLICIT",
            started_at=now,
            repo_path=snapshot.repo_path,
            repo_name=snapshot.repo_name,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )

        # 체크포인트가 start_work 보다 먼저 도착하면 그 식별자로 INFERRED 세션이
        # 먼저 생긴다(F-02). 뒤늦게 온 start_work 를 그냥 중복으로 흘려보내면
        # 사용자가 적은 제목·목표·시작 시각이 사라지고, 확인된 작업이 시스템
        # 추측으로 남는다. 자리를 채워 올린다. 강등은 리포지토리가 막는다.
        if duplicate and work["origin"] == "INFERRED" and work["title_origin"] != "USER":
            work = self.repo.promote_work(
                work_id=work_id,
                title=title,
                goal=goal,
                started_at=now,
                repo_path=snapshot.repo_path,
                repo_name=snapshot.repo_name,
                branch=snapshot.branch,
                commit_sha=snapshot.commit_sha,
                now_iso=now,
            )

        return work, duplicate

    def attach(
        self,
        *,
        work_id: str | None,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        snapshot: GitSnapshot,
    ) -> Attachment:
        now = to_iso(self.clock.now())

        if work_id:
            existing = self.repo.get_work(work_id)
            if existing is None:
                existing = self._create(
                    work_id, client_instance_id, machine_id, tool, snapshot, now
                )
            return Attachment(existing, "REQUEST")

        if client_instance_id:
            found = self.repo.find_active_by_client(client_instance_id)
            if found is not None:
                return Attachment(found, "CLIENT_INSTANCE")

        if snapshot.repo_path:
            since = to_iso(
                self.clock.now()
                - timedelta(minutes=self.settings.attach_window_minutes)
            )
            found = self.repo.find_active_by_repo(
                machine_id, tool, snapshot.repo_path, since
            )
            if found is not None:
                return Attachment(found, "REPO_WINDOW")

        created = self._create(
            self._id_factory("wrk"), client_instance_id, machine_id, tool, snapshot, now
        )
        return Attachment(created, "NEW")

    def promote_title(self, work: dict, title: str) -> None:
        """제목이 없는 세션에만 붙는다. 리포지토리가 조건을 지킨다."""
        if work.get("title") is None:
            self.repo.set_work_title(work["work_id"], title)

    # ------------------------------------------------------------------
    # 마감
    # ------------------------------------------------------------------

    def sweep_idle(self) -> list[str]:
        """유휴 제한을 넘긴 진행 중 세션을 마감한다. 데몬 기동 직후에도 한 번 돈다."""
        now = self.clock.now()
        threshold = to_iso(now - timedelta(hours=self.settings.idle_timeout_hours))
        closed = []
        for row in self.repo.find_stale_active(threshold):
            self.repo.auto_close_work(
                row["work_id"],
                "IDLE_TIMEOUT",
                ended_at=row["last_activity_at"],
                now_iso=to_iso(now),
            )
            closed.append(row["work_id"])
        return closed

    def close_client(self, client_instance_id: str) -> list[str]:
        now = to_iso(self.clock.now())
        closed = []
        for row in self.repo.find_active_by_client_ids(client_instance_id):
            self.repo.auto_close_work(
                row["work_id"],
                "CLIENT_EXIT",
                ended_at=row["last_activity_at"],
                now_iso=now,
            )
            closed.append(row["work_id"])
        self.repo.close_client(client_instance_id, now)
        return closed

    def finish(
        self,
        *,
        work_id: str | None,
        client_instance_id: str | None,
        result: str | None,
        limitations: str | None,
        next_steps: str | None,
        snapshot: GitSnapshot,
        ended_at: str | None = None,
    ) -> dict | None:
        """대상이 없으면 None 이다. 오류가 아니다.

        `ended_at` 은 호출자가 적은 마감 시각이다. `start_work` 는
        `started_at` 을, `record_checkpoint` 는 `occurred_at` 을 이미
        존중하는데 마감만 예외였다(OUTSTANDING I3). 데몬이 꺼진 채 밤 10시에
        닫은 작업이 다음 날 아침에 흡수되면 소요 시간이 열몇 시간으로 찍히고,
        그 숫자는 그대로 화면에 남는다.

        `recorded_at`(`now_iso`)은 여전히 지금이다. **일어난 시각과 기록된
        시각은 다른 것**이고, 흡수 경로가 그 둘이 갈리는 유일한 자리다.
        """
        target = work_id
        if target is None and client_instance_id:
            found = self.repo.find_active_by_client(client_instance_id)
            target = found["work_id"] if found is not None else None
        if target is None or self.repo.get_work(target) is None:
            return None

        now = to_iso(self.clock.now())
        return self.repo.finish_work(
            work_id=target,
            result=result,
            limitations=limitations,
            next_steps=next_steps,
            ended_at=ended_at or now,
            repo_path=snapshot.repo_path,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )

    # ------------------------------------------------------------------

    def _create(
        self,
        work_id: str,
        client_instance_id: str | None,
        machine_id: str,
        tool: str,
        snapshot: GitSnapshot,
        now: str,
    ) -> dict:
        work, _ = self.repo.insert_work(
            work_id=work_id,
            machine_id=machine_id,
            client_instance_id=client_instance_id,
            tool=tool,
            title=None,
            title_origin=None,
            goal=None,
            origin="INFERRED",
            started_at=now,
            repo_path=snapshot.repo_path,
            repo_name=snapshot.repo_name,
            branch=snapshot.branch,
            commit_sha=snapshot.commit_sha,
            now_iso=now,
        )
        return work
