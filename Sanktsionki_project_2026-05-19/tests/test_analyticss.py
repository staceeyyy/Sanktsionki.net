from __future__ import annotations

import pandas as pd

from sanktsionki.services.analytics import build_best_offers, build_market_summary


def test_build_market_summary_marks_best_source() -> None:
    offers = pd.DataFrame(
        [
            {"query_slug": "q1", "query_label": "air force 1", "source_name": "Lamoda", "source_type": "static", "title": "A", "price_rub": 18000, "match_score": 1.0, "has_discount": True},
            {"query_slug": "q1", "query_label": "air force 1", "source_name": "Avito", "source_type": "dynamic", "title": "B", "price_rub": 9000, "match_score": 1.0, "has_discount": False},
        ]
    )
    summary = build_market_summary(offers)
    best = summary.loc[summary["source_name"] == "Avito", "query_best_source"].iloc[0]
    assert bool(best) is True


def test_build_best_offers_limits_rows() -> None:
    offers = pd.DataFrame(
        [
            {"query_slug": "q1", "query_label": "air force 1", "title": "A", "price_rub": 15000, "match_score": 1.0},
            {"query_slug": "q1", "query_label": "air force 1", "title": "B", "price_rub": 14000, "match_score": 1.0},
            {"query_slug": "q1", "query_label": "air force 1", "title": "C", "price_rub": 13000, "match_score": 1.0},
            {"query_slug": "q1", "query_label": "air force 1", "title": "D", "price_rub": 12000, "match_score": 1.0},
        ]
    )
    best = build_best_offers(offers, top_n=2)
    assert len(best) == 2
    assert best.iloc[0]["price_rub"] == 12000
