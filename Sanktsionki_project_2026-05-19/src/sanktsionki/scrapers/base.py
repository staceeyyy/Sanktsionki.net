#создаем фреймворк для веб-скраппинга с двумя подходами к загрузке страниц: Static (BaseScraper) - использует requests для обычных HTML-страниц, Dynamic (SeleniumEdgeScraper) - запускает настоящий браузер Edge, видит Java
from __future__ import annotations #можно использовать классы в аннотациях, даже если они еще не определены

import shutil #модуль для операций с файлами(удаление директорий)
import tempfile #создание временных папок(для профиля браузера)
from abc import ABC, abstractmethod
from time import sleep

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options

from sanktsionki import config
from sanktsionki.models import ProductOffer, SearchQuery
from sanktsionki.utils import clean_whitespace, match_score


class BaseScraper(ABC):
    source_name = "base"
    source_type = "static"

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session() #переиспользуем соединение для нескольких запросов (так быстрее)
        self.session.headers.update(config.DEFAULT_HEADERS) #добавляем стандартные заголовки, чтобы не заблокировали

    @abstractmethod #обязательный метод для всех наследников, каждый скрапер по-свооему ищет товары
    def search(self, query: SearchQuery, limit: int = 10) -> list[ProductOffer]:
        raise NotImplementedError

    def close(self) -> None:
        self.session.close() #закрываем HTTP-сессию

    def _is_relevant(self, query: SearchQuery, *texts: str | None) -> float:
        return match_score(query.label, query.brand, *texts) #оценка релевантности
#создаем объект предложения
    def _offer(
        self,
        query: SearchQuery,
        *,
        title: str,
        price_rub: int,
        old_price_rub: int | None = None,
        location: str | None = None,
        seller: str | None = None,
        listing_url: str,
        image_url: str | None = None,
        availability_note: str | None = None,
        raw_snippet: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        match_override: float | None = None,
        country_name: str | None = None,
        market_scope: str | None = None,
        source_domain: str | None = None,
    ) -> ProductOffer: 
        score = match_override if match_override is not None else self._is_relevant(query, title, raw_snippet)
        return ProductOffer(
            query_slug=query.slug,
            query_label=query.label,
            source_name=self.source_name,
            source_type=self.source_type,
            title=clean_whitespace(title),
            brand=brand or query.brand,
            category=category or query.category,
            price_rub=price_rub,
            old_price_rub=old_price_rub,
            location=clean_whitespace(location) or None,
            seller=clean_whitespace(seller) or None,
            listing_url=listing_url,
            image_url=image_url,
            availability_note=clean_whitespace(availability_note) or None,
            match_score=score,
            collected_at=ProductOffer.timestamp(),
            raw_snippet=clean_whitespace(raw_snippet) or None,
            country_name=clean_whitespace(country_name) or None,
            market_scope=clean_whitespace(market_scope) or "local",
            source_domain=clean_whitespace(source_domain) or None,
        )

    def _get_soup(self, url: str) -> BeautifulSoup: #получаем HTML-страницу
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")


class SeleniumEdgeScraper(BaseScraper):
    source_type = "dynamic"

    def __init__(self, timeout: int = 30, page_wait_seconds: int = 5) -> None:
        super().__init__(timeout=timeout)
        self.page_wait_seconds = page_wait_seconds
        self._driver: webdriver.Edge | None = None #экземпляр браузера Edge
        self._profile_dir: str | None = None #временная папка для профиля браузера

    def _get_driver(self) -> webdriver.Edge:
        if self._driver is not None:
            return self._driver

        self._profile_dir = tempfile.mkdtemp(prefix="edge-profile-") #создаем уникальную временную папку
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1600,1200")
        options.add_argument(f"--user-data-dir={self._profile_dir}")
        options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        self._driver = webdriver.Edge(options=options)
        self._driver.set_page_load_timeout(self.timeout)
        return self._driver

    def _render_html(self, url: str) -> str:
        driver = self._get_driver() #Получаем или создаем браузер  
        driver.get(url) #Загружаем URL
        sleep(self.page_wait_seconds)  #Ждем выполнения JavaScript
        return driver.page_source  #Получаем итоговый HTML
#закрытие ресурсов
    def close(self) -> None:
        super().close()
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
        if self._profile_dir:
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None
