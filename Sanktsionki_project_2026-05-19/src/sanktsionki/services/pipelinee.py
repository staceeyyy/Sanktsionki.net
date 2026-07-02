# Собираем сырые данные, нормализует данные через offers_to_frame(), строит сводку по рынку (build_market_summary) и находим лучшие предложения (build_best_offers).
# Кодик возвращает три таблицы: offers — все предложения, summary — агрегированная статистика, best_offers — топовые предложения

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sanktsionki import config
from sanktsionki.models import SearchQuery
from sanktsionki.scrapers import AvitoScraper, CdekShoppingScraper, LamodaScraper, SneakerheadScraper
from sanktsionki.services.analytics import build_best_offers, build_market_summary
from sanktsionki.services.normalization import offers_to_frame
from sanktsionki.utils import ensure_dir


@dataclass(slots=True)
class PipelineArtifacts:
    offers: pd.DataFrame
    summary: pd.DataFrame
    best_offers: pd.DataFrame


def load_queries(path: Path | None = None) -> list[SearchQuery]:
    query_path = path or config.QUERIES_PATH
    data = json.loads(query_path.read_text(encoding="utf-8"))
    return [SearchQuery(**row) for row in data]


class OfferPipeline:
    def __init__(self, queries: list[SearchQuery] | None = None) -> None:
        self.queries = queries or load_queries()
        self.scrapers = [
            LamodaScraper(),
            SneakerheadScraper(),
            AvitoScraper(page_wait_seconds=5),
            CdekShoppingScraper(),
        ]

    def collect(self, limit_per_source: int = 10) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for query in self.queries:
            for scraper in self.scrapers:
                try:
                    offers = scraper.search(query, limit=limit_per_source)
                except Exception as exc:
                    print(f"[warn] {scraper.source_name} failed for '{query.label}': {exc}")
                    continue
                records.extend(offer.to_dict() for offer in offers)
        return records

    def run(self, limit_per_source: int = 10) -> PipelineArtifacts:
        try:
            raw_records = self.collect(limit_per_source=limit_per_source)
        finally:
            self.close()

        offers = offers_to_frame(raw_records)
        summary = build_market_summary(offers)
        best_offers = build_best_offers(offers)
        return PipelineArtifacts(offers=offers, summary=summary, best_offers=best_offers)

    def persist(self, artifacts: PipelineArtifacts) -> None:
        ensure_dir(config.RAW_DATA_DIR)
        ensure_dir(config.PROCESSED_DATA_DIR)

        artifacts.offers.to_csv(config.OFFERS_CSV, index=False, encoding="utf-8-sig")
        artifacts.summary.to_csv(config.SUMMARY_CSV, index=False, encoding="utf-8-sig")
        artifacts.best_offers.to_csv(config.BEST_OFFERS_CSV, index=False, encoding="utf-8-sig")
        self._append_history(artifacts.offers)

        for source_name, source_frame in artifacts.offers.groupby("source_name"):
            safe_name = source_name.lower().replace(".", "_").replace(" ", "_")
            out_path = config.RAW_DATA_DIR / f"{safe_name}.csv"
            source_frame.to_csv(out_path, index=False, encoding="utf-8-sig")

    def _append_history(self, offers: pd.DataFrame) -> None:
        if offers.empty:
            return
        history = offers.copy()
        if config.OFFERS_HISTORY_CSV.exists():
            existing = pd.read_csv(config.OFFERS_HISTORY_CSV)
            history = pd.concat([existing, history], ignore_index=True)
            history = history.drop_duplicates(
                subset=["query_slug", "source_name", "title", "price_rub", "listing_url", "collected_at"],
                keep="last",
            )
        history.to_csv(config.OFFERS_HISTORY_CSV, index=False, encoding="utf-8-sig")

    def close(self) -> None:
        for scraper in self.scrapers:
            scraper.close()
