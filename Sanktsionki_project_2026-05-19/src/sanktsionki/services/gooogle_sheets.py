# Этот код реализует класс GoogleSheetsExporter, который подключается к Google Sheets API через сервисный аккаунт и экспортирует pandas DataFrame в указанную таблицу. 
# Он автоматически создает недостающие листы, очищает существующие, преобразует None значения в пустые строки и загружает данные вместе с заголовками колонок, начиная с ячейки A1.
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


class GoogleSheetsExporter:
    def __init__(self, credentials_path: str | Path | None = None) -> None:
        raw_path = credentials_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        self.credentials_path = Path(raw_path).expanduser() if raw_path else None

    @staticmethod
    def frame_to_rows(frame: pd.DataFrame) -> list[list[object]]:
        clean = frame.fillna("")
        return [clean.columns.tolist(), *clean.values.tolist()]

    def _client(self):
        if not self.credentials_path or not self.credentials_path.exists():
            raise FileNotFoundError(
                "Google service account file was not found. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE or pass --credentials."
            )

        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            str(self.credentials_path),
            scopes=scopes,
        )
        return gspread.authorize(credentials)

    def export_frames(self, spreadsheet_id: str, worksheets: dict[str, pd.DataFrame]) -> list[str]:
        client = self._client()
        workbook = client.open_by_key(spreadsheet_id)

        import gspread

        exported: list[str] = []
        for title, frame in worksheets.items():
            try:
                worksheet = workbook.worksheet(title)
            except gspread.WorksheetNotFound:
                worksheet = workbook.add_worksheet(
                    title=title,
                    rows=max(len(frame) + 10, 20),
                    cols=max(len(frame.columns) + 3, 8),
                )

            worksheet.clear()
            rows = self.frame_to_rows(frame)
            if rows:
                worksheet.update("A1", rows, value_input_option="RAW")
            exported.append(title)

        return exported
