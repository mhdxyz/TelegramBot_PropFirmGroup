from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from app.features.commands.service import LotteryData


class LotteryExcelExporter:
    """Best-effort durable Excel mirror for committed lottery registrations.

    SQLite remains the source of truth. The exporter writes to a temporary
    file and atomically replaces the target, so a failed write cannot leave
    a partially-written workbook.
    """

    HEADERS = [
        "Telegram User ID",
        "Name and Family Name",
        "Company A Registration Email",
        "Company B Registration Email",
        "Telegram ID",
        "Registered At",
    ]

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def append(self, *, telegram_user_id: int, data: LotteryData,
               telegram_username: str | None, registered_at: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            if self._path.exists():
                workbook = load_workbook(self._path)
                sheet = workbook.active
            else:
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Lottery Registrations"
                sheet.append(self.HEADERS)

            sheet.append([
                telegram_user_id,
                data.full_name,
                data.company_a_email,
                data.company_b_email,
                f"@{telegram_username}" if telegram_username else "",
                registered_at,
            ])
            workbook.save(temp)
            workbook.close()
            temp.replace(self._path)
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)
