from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.features.commands.export import LotteryExcelExporter
from app.repositories.command_repository import LotteryExportQueueRepository

logger = get_logger(__name__)


class LotteryExportWorker:
    """Continuously drains the durable lottery export outbox.

    Excel I/O is synchronous, so it is moved to a worker thread to avoid
    blocking the Telegram/FastAPI event loop. Failed jobs remain in SQLite
    and are retried with repository-controlled exponential backoff.
    """

    def __init__(self, queue: LotteryExportQueueRepository,
                 exporter: LotteryExcelExporter,
                 poll_interval_seconds: float = 5.0,
                 batch_size: int = 20) -> None:
        self._queue = queue
        self._exporter = exporter
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="lottery-export-worker")

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while not self._stopping:
            processed = await self.process_pending_once()
            if processed == 0:
                await asyncio.sleep(self._poll_interval)

    async def process_pending_once(self) -> int:
        try:
            jobs = await self._queue.get_pending_exports(self._batch_size)
        except Exception:
            logger.exception("lottery_export_queue_read_failed")
            return 0

        for job in jobs:
            try:
                await asyncio.to_thread(self._exporter.upsert, job)
            except Exception as exc:
                logger.exception(
                    "lottery_export_failed",
                    extra={"telegram_user_id": job.telegram_user_id, "attempts": job.attempts},
                )
                try:
                    await self._queue.mark_export_failed(job.telegram_user_id, str(exc))
                except Exception:
                    logger.exception(
                        "lottery_export_retry_schedule_failed",
                        extra={"telegram_user_id": job.telegram_user_id},
                    )
            else:
                try:
                    await self._queue.mark_export_succeeded(job.telegram_user_id)
                except Exception:
                    # The Excel write is idempotent, so the same job can safely
                    # be exported again on the next worker cycle.
                    logger.exception(
                        "lottery_export_ack_failed",
                        extra={"telegram_user_id": job.telegram_user_id},
                    )
        return len(jobs)
