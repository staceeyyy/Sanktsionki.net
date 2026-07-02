# Этот кодик парсит экспортированные чаты Telegram, находит: 1) Упоминания денег (цены, комиссии, доставка)
# 2) Определяет типы расходов (комиссия, доставка, таможня)
# 3) Выявляет страны и бренды
# 4) Строит сводную статистику
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from sanktsionki import config
from sanktsionki.utils import clean_whitespace, infer_brand, normalize_text


MONEY_PATTERN = re.compile(r"(?<!\d)(\d[\d\s]{2,})(?:\s*(?:руб|р|₽|k|к))?", re.IGNORECASE)
METRIC_HINTS = {
    "commission": ("комис", "fee", "байер", "выкуп"),
    "delivery": ("достав", "shipping", "логист", "карго"),
    "customs": ("тамож", "пошлин"),
    "total": ("итого", "под ключ", "all in", "total"),
}
METRIC_PATTERNS = {
    metric: re.compile(
        rf"(?:{'|'.join(re.escape(hint) for hint in hints)})[^\d]{{0,24}}(\d[\d\s]{{2,}}(?:\s*-\s*\d[\d\s]{{2,}})?)",
        re.IGNORECASE,
    )
    for metric, hints in METRIC_HINTS.items()
}
COUNTRY_HINTS = {
    "Китай": ("кита", "china", "guangzhou", "1688"),
    "Турция": ("турц", "turkey", "istanbul"),
    "США": ("сша", "usa", "united states"),
    "ОАЭ": ("оаэ", "uae", "dubai", "emirates"),
    "Южная Корея": ("коре", "korea", "seoul"),
}
#данная функция нормализует наш текст: если строка → очищает пробелы; если список → склеивает все текстовые части; если словарь → берет поле text; иначе → преобразует в строку
def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_whitespace(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return clean_whitespace(" ".join(parts))
    if isinstance(value, dict):
        return clean_whitespace(str(value.get("text") or ""))
    return clean_whitespace(str(value or ""))


def _detect_metric(text: str) -> str:  #определение типа расхода
    normalized = normalize_text(text)
    for metric, hints in METRIC_HINTS.items():
        if any(hint in normalized for hint in hints):
            return metric
    return "price_talk"


def _detect_country(text: str) -> str | None: #определение страны
    normalized = normalize_text(text)
    for country, hints in COUNTRY_HINTS.items():
        if any(hint in normalized for hint in hints):
            return country
    return None


def load_telegram_export(path: Path) -> pd.DataFrame: #загрузка одного файла
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for message in payload.get("messages", []):
        text = _flatten_text(message.get("text"))
        if not text:
            continue
        rows.append(
            {
                "message_id": message.get("id"),
                "date": message.get("date"),
                "author": clean_whitespace(str(message.get("from") or message.get("actor") or "unknown")),
                "text": text,
                "source_file": path.name,
            }
        )
    return pd.DataFrame(rows)


def load_buyer_chat_messages(chat_dir: Path = config.BUYER_CHAT_DIR) -> pd.DataFrame: #загрузка всех чатов
    if not chat_dir.exists():
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for path in sorted(chat_dir.glob("*.json")):
        frame = load_telegram_export(path)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    messages = pd.concat(frames, ignore_index=True)
    if "date" in messages:
        messages["date"] = pd.to_datetime(messages["date"], errors="coerce")
    return messages


def extract_amount_mentions(messages: pd.DataFrame) -> pd.DataFrame: #извлекаем финансовые упоминания 
    if messages.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for record in messages.to_dict("records"):
        text = str(record.get("text") or "")
        country_name = _detect_country(text)
        brand = infer_brand(text)
        matched_any = False
        for metric, pattern in METRIC_PATTERNS.items():
            for snippet_match in pattern.finditer(text):
                amount_blob = snippet_match.group(1)
                for amount_match in re.finditer(r"\d[\d\s]{2,}", amount_blob):
                    amount_rub = int(re.sub(r"\D", "", amount_match.group(0)))
                    if amount_rub < 100 or amount_rub > 500_000:
                        continue
                    rows.append(
                        {
                            "message_id": record.get("message_id"),
                            "date": record.get("date"),
                            "author": record.get("author"),
                            "source_file": record.get("source_file"),
                            "metric": metric,
                            "amount_rub": amount_rub,
                            "country_name": country_name,
                            "brand": brand,
                            "text_excerpt": text[:220],
                        }
                    )
                    matched_any = True

        if matched_any:
            continue

        for match in MONEY_PATTERN.finditer(text):
            metric = _detect_metric(text)
            if metric == "price_talk" and not re.search(r"(руб|₽|k|к)", match.group(0), re.IGNORECASE):
                continue
            amount_rub = int(re.sub(r"\D", "", match.group(1)))
            if amount_rub < 100 or amount_rub > 500_000:
                continue
            rows.append(
                {
                    "message_id": record.get("message_id"),
                    "date": record.get("date"),
                    "author": record.get("author"),
                    "source_file": record.get("source_file"),
                    "metric": metric,
                    "amount_rub": amount_rub,
                    "country_name": country_name,
                    "brand": brand,
                    "text_excerpt": text[:220],
                }
            )
    mentions = pd.DataFrame(rows)
    if not mentions.empty and "date" in mentions:
        mentions["date"] = pd.to_datetime(mentions["date"], errors="coerce")
    return mentions


def build_buyer_chat_summary(mentions: pd.DataFrame) -> pd.DataFrame: #построение сводки 
    if mentions.empty:
        return pd.DataFrame()
    summary = (
        mentions.groupby("metric", as_index=False)
        .agg(
            mention_count=("amount_rub", "count"),
            min_rub=("amount_rub", "min"),
            median_rub=("amount_rub", "median"),
            mean_rub=("amount_rub", "mean"),
            max_rub=("amount_rub", "max"),
        )
        .sort_values(["mention_count", "median_rub"], ascending=[False, True])
    )
    top_countries = (
        mentions.dropna(subset=["country_name"]) #определение топ-стран для каждой метрики
        .groupby(["metric", "country_name"], as_index=False)
        .size() #считаем упоминания
        .sort_values(["metric", "size"], ascending=[True, False])
        .drop_duplicates("metric") #оставляем топ-1 на метрику
        .rename(columns={"country_name": "top_country", "size": "top_country_mentions"})
    )
    summary = summary.merge(top_countries, on="metric", how="left")
    summary["mean_rub"] = summary["mean_rub"].round(1)
    summary["median_rub"] = summary["median_rub"].round(1)
    return summary


def persist_buyer_chat_outputs( #основная функция сохранения
    messages_path: Path = config.BUYER_CHAT_MESSAGES_CSV,
    summary_path: Path = config.BUYER_CHAT_SUMMARY_CSV,
    chat_dir: Path = config.BUYER_CHAT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    messages = load_buyer_chat_messages(chat_dir) #загружаем все сообщения из чатов
    mentions = extract_amount_mentions(messages) #извлекаем упоминания денег 
    summary = build_buyer_chat_summary(mentions) #строим сводку по метрикам 

    messages_path.parent.mkdir(parents=True, exist_ok=True) #создаем директории (если нет)
    mentions.to_csv(messages_path, index=False, encoding="utf-8-sig") #сохраняем csv
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig") #сохраняем csv
    return mentions, summary
