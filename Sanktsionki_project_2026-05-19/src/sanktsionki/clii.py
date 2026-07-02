# создаем 4 команды для управления проектом. 
# - collect_main запускает сбор данных: загружает поисковые запросы, запускает парсеры через OfferPipeline и сохраняет результаты в CSV. 
# - export_sheets_main экспортирует собранные данные (предложения, сводки по рынку, аналитику чатов) в Google Sheets через экспортер. 
# - analyze_buyer_chats_main обрабатывает экспорты Telegram-чатов байеров, извлекая упоминания денег и формируя аналитику по комиссиям, доставке и географии. 
# - dashboard_main запускает веб-дашборд на Dash для визуального анализа цен.  

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from sanktsionki import config
from sanktsionki.models import SearchQuery
from sanktsionki.services.buyer_chat_analytics import persist_buyer_chat_outputs
from sanktsionki.services.google_sheets import GoogleSheetsExporter
from sanktsionki.services.pipeline import OfferPipeline, load_queries


def collect_main() -> None:
    parser = argparse.ArgumentParser(description="Collect offers for Sanktsionki.")
    parser.add_argument("--limit", type=int, default=10, help="Offers per source and query.")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Optional query slug to collect. Can be passed multiple times.",
    )
    parser.add_argument(
        "--text-query",
        action="append",
        dest="text_queries",
        help="Optional free-form model or article request for ad hoc collection.",
    )
    args = parser.parse_args()

    queries = load_queries()
    if args.queries:
        allowed = set(args.queries)
        queries = [query for query in queries if query.slug in allowed]
    if args.text_queries:
        queries.extend(SearchQuery.from_text(text) for text in args.text_queries)

    pipeline = OfferPipeline(queries=queries)
    artifacts = pipeline.run(limit_per_source=args.limit)
    pipeline.persist(artifacts)
    print(f"Collected {len(artifacts.offers)} offers across {len(queries)} queries.")


def export_sheets_main() -> None:
    parser = argparse.ArgumentParser(description="Export Sanktsionki outputs to Google Sheets.")
    parser.add_argument("--spreadsheet-id", default=os.getenv("GOOGLE_SPREADSHEET_ID"))
    parser.add_argument("--credentials")
    args = parser.parse_args()

    if not args.spreadsheet_id:
        raise SystemExit("Pass --spreadsheet-id or set GOOGLE_SPREADSHEET_ID.")

    frames = {
        "offers": _read_csv_or_empty(config.OFFERS_CSV),
        "market_summary": _read_csv_or_empty(config.SUMMARY_CSV),
        "best_offers": _read_csv_or_empty(config.BEST_OFFERS_CSV),
        "buyer_chat_summary": _read_csv_or_empty(config.BUYER_CHAT_SUMMARY_CSV),
    }
    exporter = GoogleSheetsExporter(credentials_path=args.credentials)
    exported = exporter.export_frames(args.spreadsheet_id, frames)
    print(f"Exported worksheets: {', '.join(exported)}")


def analyze_buyer_chats_main() -> None:
    parser = argparse.ArgumentParser(description="Build buyer chat analytics from Telegram exports.")
    parser.add_argument("--chat-dir", default=str(config.BUYER_CHAT_DIR))
    args = parser.parse_args()

    mentions, summary = persist_buyer_chat_outputs(chat_dir=Path(args.chat_dir))
    print(f"Extracted {len(mentions)} money mentions across {len(summary)} metrics.")


def dashboard_main() -> None:
    from sanktsionki.dashboard.app import main as dashboard_main_impl

    dashboard_main_impl()


def _read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)
