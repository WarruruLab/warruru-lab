"""주기 작업. 유휴 세션을 마감하고 spool 을 흡수한다."""

from __future__ import annotations

import asyncio

from warruru_local.daemon import absorb


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
