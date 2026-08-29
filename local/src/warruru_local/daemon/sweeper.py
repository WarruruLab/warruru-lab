"""주기 작업. 유휴 세션을 마감하고, spool 을 흡수하고, 어제를 마감한다."""

from __future__ import annotations

import asyncio

from warruru_local.daemon import absorb, nightly


def start_sweeper(ctx):
    interval = ctx.settings.sweep_interval_seconds

    async def loop() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                closed = ctx.sessions.sweep_idle()
                applied = absorb.absorb_all(ctx)
                if closed or applied:
                    ctx.logger.info("자동 마감 %d건, spool 반영 %d건", len(closed), applied)
                # 날짜가 바뀐 뒤 첫 스위프에서만 실제로 일한다.
                # 나머지 호출은 표식을 보고 바로 돌아간다.
                made = nightly.run(ctx)
                if made["drafted"] or made["failed"]:
                    # 구간을 함께 남긴다. 며칠치를 한꺼번에 마감했는지가
                    # 로그에 없으면 '왜 오늘 다섯 편이 생겼지' 를 되짚을 수 없다.
                    ctx.logger.info(
                        "밤 초안 %d건(실패 %d건), 밀어넣음 %d건 — %s~%s 마감",
                        len(made["drafted"]), len(made["failed"]),
                        len(made.get("pushed", [])),
                        made.get("from"), made.get("to"),
                    )
            except Exception:
                ctx.logger.exception("주기 작업이 실패했다")

    task = asyncio.create_task(loop())

    async def stop() -> None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return stop
