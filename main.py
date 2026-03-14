"""Streamlit-приложение для проверки наличия товаров по кодам."""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from parser import ParserConfig, ProductParser
from utils import (
    codes_from_dataframe,
    dataframe_to_xlsx_bytes,
    merge_unique_codes,
    result_to_dataframe,
    split_codes_from_text,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


st.set_page_config(page_title="Проверка кодов товаров", page_icon="🔎", layout="wide")
st.title("🔎 Проверка товаров на сайте volgorost.ru")
st.write(
    "Загрузите XLSX с кодами, добавьте коды вручную (по одному на строку) и запустите проверку."
)

uploaded_file = st.file_uploader("Загрузите XLSX файл с кодами", type=["xlsx"])
manual_codes_input = st.text_area(
    "Введите коды товаров (каждый с новой строки)",
    height=160,
    placeholder="12345\n87654\nA3456\nZX001",
)

start_button = st.button("Начать проверку", type="primary")

if start_button:
    file_codes: list[str] = []

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file, header=None)
            file_codes = codes_from_dataframe(df)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Не удалось прочитать XLSX файл: {exc}")

    manual_codes = split_codes_from_text(manual_codes_input)
    codes = merge_unique_codes(file_codes, manual_codes)

    if not codes:
        st.warning("Не найдено ни одного корректного кода для обработки.")
    else:
        st.info(f"К обработке подготовлено кодов: **{len(codes)}**")

        parser = ProductParser(ParserConfig())
        progress_bar = st.progress(0)
        status_placeholder = st.empty()

        def on_progress(processed: int, total: int, found: int) -> None:
            percent = int((processed / total) * 100) if total else 0
            progress_bar.progress(percent)
            status_placeholder.write(
                f"Обработано: **{processed}/{total}** | Найдено совпадений: **{found}**"
            )

        with st.spinner("Идет проверка кодов, пожалуйста подождите..."):
            results = parser.check_codes(codes, progress_callback=on_progress)

        result_df = result_to_dataframe(results)

        st.subheader("Результаты")
        st.dataframe(result_df, use_container_width=True)

        if result_df.empty:
            st.warning("Совпадения не найдены. Отчет не сформирован.")
        else:
            report_bytes = dataframe_to_xlsx_bytes(result_df)
            st.download_button(
                label="Скачать XLSX отчет",
                data=report_bytes,
                file_name="volgorost_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
