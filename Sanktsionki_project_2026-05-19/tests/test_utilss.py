# Тест проверяет три ключевые утилиты, которые используются во всех скраперах и анализаторах:
# parse_price() - парсинг цен из строк
# match_score() - оценка релевантности товара запросу
# normalize_text() - приведение текста к стандартному виду

from __future__ import annotations
from sanktsionki.utils import match_score, normalize_text, parse_price


def test_parse_price_handles_ruble_strings() -> None:
    assert parse_price("18 999 ₽") == 18999


def test_match_score_counts_query_tokens() -> None:
    score = match_score("air force 1", "Nike Air Force 1 '07")
    assert score >= 0.66


def test_match_score_requires_numeric_tokens_when_present() -> None:
    assert match_score("air max 90", "Nike Air Max SC") == 0.0


def test_normalize_text_supports_cyrillic_and_yo() -> None:
    assert normalize_text("Ёжик, доставка и Air Max 90!") == "ежик доставка и air max 90"
