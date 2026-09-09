import pytest

from app.features.commands.export_worker import LotteryExportWorker
from app.repositories.command_repository import LotteryExportJob


JOB = LotteryExportJob(
    telegram_user_id=42,
    full_name="John Doe",
    company_a_email="a@example.com",
    company_b_email="b@example.com",
    telegram_username="john",
    registered_at="2026-09-09 12:00:00",
    attempts=0,
)


class FakeQueue:
    def __init__(self):
        self.jobs = [JOB]
        self.failed = []
        self.succeeded = []

    async def get_pending_exports(self, limit=20):
        return self.jobs[:limit]

    async def mark_export_failed(self, telegram_user_id, error):
        self.failed.append((telegram_user_id, error))

    async def mark_export_succeeded(self, telegram_user_id):
        self.succeeded.append(telegram_user_id)


class FakeExporter:
    def __init__(self, fail=False):
        self.fail = fail
        self.exported = []

    def upsert(self, job):
        if self.fail:
            raise OSError("disk unavailable")
        self.exported.append(job.telegram_user_id)


@pytest.mark.asyncio
async def test_worker_acknowledges_successful_export():
    queue = FakeQueue()
    exporter = FakeExporter()
    worker = LotteryExportWorker(queue, exporter)

    assert await worker.process_pending_once() == 1
    assert exporter.exported == [42]
    assert queue.succeeded == [42]
    assert queue.failed == []


@pytest.mark.asyncio
async def test_worker_keeps_failed_export_for_retry():
    queue = FakeQueue()
    exporter = FakeExporter(fail=True)
    worker = LotteryExportWorker(queue, exporter)

    assert await worker.process_pending_once() == 1
    assert queue.succeeded == []
    assert queue.failed == [(42, "disk unavailable")]
