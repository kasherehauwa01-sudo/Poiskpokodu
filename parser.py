"""Модуль парсинга сайта volgorost.ru по коду товара."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


@dataclass
class ParserConfig:
    """Настройки запросов парсера."""

    base_url: str = "https://volgorost.ru/"
    timeout: int = 20
    request_delay: float = 0.7


class ProductParser:
    """Ищет карточки товара, где значение поля «Код» совпадает с исходным кодом."""

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )

    def _get_soup(self, url: str) -> tuple[BeautifulSoup | None, int]:
        """Безопасно загружает HTML и возвращает BeautifulSoup + HTTP статус."""
        try:
            response = self.session.get(url, timeout=self.config.timeout)
            status_code = response.status_code
            if status_code == 404:
                logger.warning("Страница 404: %s", url)
                return None, status_code
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return soup, status_code
        except requests.RequestException as exc:
            logger.exception("Ошибка запроса %s: %s", url, exc)
            return None, 0

    def _search_urls(self, code: str) -> list[str]:
        """Формирует несколько URL поиска, чтобы поддержать разные шаблоны CMS."""
        search_patterns = [
            f"?s={code}",
            f"search/?q={code}",
            f"catalog/?q={code}",
        ]
        return [urljoin(self.config.base_url, pattern) for pattern in search_patterns]

    def _extract_product_links(self, soup: BeautifulSoup) -> list[str]:
        """Извлекает ссылки на карточки из HTML поиска."""
        links: dict[str, None] = {}

        for tag in soup.select("a[href]"):
            href = tag.get("href", "").strip()
            if not href:
                continue
            abs_url = urljoin(self.config.base_url, href)
            if self._looks_like_product_url(abs_url):
                links[abs_url] = None

        return list(links.keys())

    @staticmethod
    def _looks_like_product_url(url: str) -> bool:
        """Простая эвристика: ссылка похожа на карточку товара, а не на служебную страницу."""
        lowered = url.lower()
        blocked_parts = ["/cart", "/login", "/account", "/search", "#", "mailto:"]
        if any(part in lowered for part in blocked_parts):
            return False
        return lowered.startswith("http")

    def _extract_code_from_product_page(self, soup: BeautifulSoup) -> str:
        """Пытается найти поле «Код» разными способами в карточке товара."""
        # 1) Типовой вариант: таблица характеристик.
        for row in soup.select("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            if "код" in label:
                return cells[1].get_text(" ", strip=True)

        # 2) Вариант: блоки label/value.
        for container in soup.select("li, div, p"):
            text = container.get_text(" ", strip=True)
            lower_text = text.lower()
            if lower_text.startswith("код:") or " код:" in lower_text:
                return text.split(":", 1)[-1].strip()

        return ""

    @staticmethod
    def _normalize_code(code: str) -> str:
        """Нормализует код для сравнения."""
        return "".join(code.strip().split()).lower()

    def _find_matches_in_search(self, code: str, search_url: str) -> list[dict[str, str]]:
        """Проверяет все карточки из одного URL поиска на совпадение кода."""
        soup, status_code = self._get_soup(search_url)
        if not soup or status_code == 404:
            return []

        matches: list[dict[str, str]] = []
        links = self._extract_product_links(soup)
        expected_code = self._normalize_code(code)

        for link in links:
            time.sleep(self.config.request_delay)
            product_soup, product_status = self._get_soup(link)
            if not product_soup or product_status == 404:
                continue

            found_code = self._extract_code_from_product_page(product_soup)
            if not found_code:
                continue

            if self._normalize_code(found_code) == expected_code:
                matches.append({"Код": code, "Ссылка на карточку товара": link})

        return matches

    def check_code(self, code: str) -> list[dict[str, str]]:
        """Ищет совпадения по одному коду."""
        all_matches: dict[tuple[str, str], dict[str, str]] = {}
        for search_url in self._search_urls(code):
            time.sleep(self.config.request_delay)
            matches = self._find_matches_in_search(code, search_url)
            for match in matches:
                key = (match["Код"], match["Ссылка на карточку товара"])
                all_matches[key] = match

        return list(all_matches.values())

    def check_codes(
        self,
        codes: Iterable[str],
        progress_callback: callable | None = None,
    ) -> list[dict[str, str]]:
        """Проверяет список кодов и возвращает все найденные совпадения."""
        results: list[dict[str, str]] = []
        codes_list = list(codes)
        total = len(codes_list)

        for index, code in enumerate(codes_list, start=1):
            try:
                matches = self.check_code(code)
                results.extend(matches)
            except Exception as exc:  # noqa: BLE001
                # Защита от падения программы при любой непредвиденной ошибке на одном коде.
                logger.exception("Критическая ошибка при обработке кода %s: %s", code, exc)

            if progress_callback:
                progress_callback(processed=index, total=total, found=len(results))

        return results
