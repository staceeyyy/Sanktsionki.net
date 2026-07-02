
# создали утилиты для обработки текста и данных в проекте.
# - clean_whitespace, normalize_text и query_tokens очищают строки от лишних пробелов, приводят к нижнему регистру и извлекают значимые токены.
# - parse_price извлекает числовое значение цены из строки, отфильтровывает нецифровые символы. 
# - match_score вычисляет степень релевантности товара поисковому запросу на основе совпадения токенов, с требованием к наличию числовых токенов. 
# - slugify_query и infer_brand генерируют URL-совместимый идентификатор запроса и определяют бренд по словарям псевдонимов и подсказкам моделей. 
# - offer_link_markdown преобразует ссылку в нужный формат для отображения в дашборде. 

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin


BRAND_ALIASES = {
    "nike": "Nike",
    "adidas": "Adidas",
    "new balance": "New Balance",
    "reebok": "Reebok",
    "asics": "ASICS",
    "puma": "Puma",
    "converse": "Converse",
    "vans": "Vans",
    "salomon": "Salomon",
    "ugg": "UGG",
}

MODEL_BRAND_HINTS = {
    "air force": "Nike",
    "air max": "Nike",
    "jordan": "Nike",
    "dunk": "Nike",
    "samba": "Adidas",
    "gazelle": "Adidas",
    "superstar": "Adidas",
    "new balance 530": "New Balance",
    "new balance 574": "New Balance",
    "new balance 990": "New Balance",
    "530": "New Balance",
    "574": "New Balance",
    "990": "New Balance",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    cleaned = clean_whitespace(value).lower().replace("ё", "е")
    cleaned = re.sub(r"[^0-9a-zа-я\s]", " ", cleaned, flags=re.IGNORECASE)
    return clean_whitespace(cleaned)


def parse_price(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.findall(r"\d+", value.replace("\xa0", " "))
    if not digits:
        return None
    return int("".join(digits))


def absolute_url(base_url: str, url: str | None) -> str:
    if not url:
        return base_url
    return urljoin(base_url, url)


def query_tokens(value: str) -> list[str]:
    normalized = normalize_text(value)
    tokens = []
    for token in normalized.split():
        if token.isdigit() or len(token) > 1:
            tokens.append(token)
    return tokens


def match_score(query: str, *texts: str | None) -> float:
    tokens = query_tokens(query)
    if not tokens:
        return 0.0
    haystack = normalize_text(" ".join(text or "" for text in texts))
    if not haystack:
        return 0.0
    numeric_tokens = [token for token in tokens if token.isdigit()]
    if numeric_tokens and any(token not in haystack for token in numeric_tokens):
        return 0.0
    matched = sum(1 for token in tokens if token in haystack)
    return round(matched / len(tokens), 3)


def slugify_query(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return "custom-query"
    return normalized.replace(" ", "-")


def infer_brand(value: str) -> str:
    normalized = normalize_text(value)
    for alias, brand in BRAND_ALIASES.items():
        if normalized.startswith(alias):
            return brand
    for hint, brand in MODEL_BRAND_HINTS.items():
        if hint in normalized:
            return brand
    first_token = normalized.split(" ", 1)[0] if normalized else ""
    return first_token.title() if first_token else "Unknown"


def offer_link_markdown(url: str) -> str:
    return f"[open]({url})" if url else ""
