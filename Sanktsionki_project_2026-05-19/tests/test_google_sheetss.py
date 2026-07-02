# Тест проверяет метод frame_to_rows(), который преобразует pandas DataFrame в список списков для загрузки в Google Sheets, с правильной обработкой пустых значений (None/NaN).

from __future__ import annotations

import pandas as pd

from sanktsionki.services.google_sheets import GoogleSheetsExporter


def test_frame_to_rows_replaces_nan_with_empty_strings() -> None:
    frame = pd.DataFrame(
        [
            {"source_name": "Lamoda", "price_rub": 15999, "seller": None},
        ]
    )

    rows = GoogleSheetsExporter.frame_to_rows(frame)

    assert rows[0] == ["source_name", "price_rub", "seller"]
    assert rows[1] == ["Lamoda", 15999, ""]
