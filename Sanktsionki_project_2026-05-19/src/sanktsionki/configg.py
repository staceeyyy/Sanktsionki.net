# это что-то типа конфигурации для всего проекта. Он определяет все пути к директориям и файлам данных: для сырых данных, обработанных CSV, 
# истории цен, аналитики чатов байеров и файла с поисковыми запросами. 
# задаются базовые URL-адреса всех парсимых площадок: Avito, Lamoda, Sneakerhead и CDEK.Shopping. 
# прописали стандартные HTTP-заголовки (User-Agent и Accept-Language) для имитации запросов от реального браузера при парсинге. 
# этот модуль импортируется во все остальные части проекта (парсеры, конвейер, дашборд, CLI) для единой настройки окружения


from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DATA_DIR = DATA_DIR / "input"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
BUYER_CHAT_DIR = INPUT_DATA_DIR / "buyer_chats"
QUERIES_PATH = PROJECT_ROOT / "queries.json"
OFFERS_CSV = PROCESSED_DATA_DIR / "offers.csv"
SUMMARY_CSV = PROCESSED_DATA_DIR / "market_summary.csv"
BEST_OFFERS_CSV = PROCESSED_DATA_DIR / "best_offers.csv"
OFFERS_HISTORY_CSV = PROCESSED_DATA_DIR / "offers_history.csv"
BUYER_CHAT_MESSAGES_CSV = PROCESSED_DATA_DIR / "buyer_chat_messages.csv"
BUYER_CHAT_SUMMARY_CSV = PROCESSED_DATA_DIR / "buyer_chat_summary.csv"
ASSETS_DIR = Path(__file__).resolve().parent / "dashboard" / "assets"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

AVITO_BASE_URL = "https://www.avito.ru"
LAMODA_BASE_URL = "https://www.lamoda.ru"
SNEAKERHEAD_BASE_URL = "https://sneakerhead.ru"
CDEK_BASE_URL = "https://cdek.shopping"
CDEK_SEARCH_API = f"{CDEK_BASE_URL}/api/front-controller/v1/nuxt/search/"
