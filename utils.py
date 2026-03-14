"""Вспомогательные функции для подготовки кодов и формирования отчета."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd


def clean_code(value: object) -> str:
    """Очищает код товара: убирает пробелы и приводит к строке."""
    if value is None:
        return ""
    text = str(value).strip()
    return text


def split_codes_from_text(raw_text: str) -> list[str]:
    """Разбивает ручной ввод на список кодов (по строкам)."""
    if not raw_text:
        return []

    codes = [clean_code(line) for line in raw_text.splitlines()]
    return [code for code in codes if code]


def codes_from_dataframe(df: pd.DataFrame) -> list[str]:
    """Извлекает коды из первой колонки DataFrame."""
    if df.empty:
        return []
    first_column = df.iloc[:, 0]
    codes = [clean_code(value) for value in first_column.tolist()]
    return [code for code in codes if code]


def merge_unique_codes(*code_collections: Iterable[str]) -> list[str]:
    """Объединяет наборы кодов с удалением дубликатов и сохранением порядка."""
    unique_codes: dict[str, None] = {}
    for collection in code_collections:
        for code in collection:
            normalized = clean_code(code)
            if normalized and normalized not in unique_codes:
                unique_codes[normalized] = None
    return list(unique_codes.keys())


def result_to_dataframe(results: list[dict[str, str]]) -> pd.DataFrame:
    """Преобразует результаты парсинга в DataFrame."""
    return pd.DataFrame(results, columns=["Код", "Ссылка на карточку товара"])


def dataframe_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Сохраняет DataFrame в XLSX и возвращает байты файла."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Результаты")

        worksheet = writer.sheets["Результаты"]
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 90)

    return buffer.getvalue()
