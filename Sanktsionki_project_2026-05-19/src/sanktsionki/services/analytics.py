from __future__ import annotations

import pandas as pd


def build_market_summary(offers: pd.DataFrame) -> pd.DataFrame: #группируем предложения по запросам и источникам, вычисляем статистику цен и метрики эффективности.
    if offers.empty:
        return pd.DataFrame()

    summary = (
        offers.groupby(["query_slug", "query_label", "source_name", "source_type"], as_index=False) #через groupby группируем строки по уникальным комбинациям указанных колонок
        .agg(
            offer_count=("title", "count"),
            min_price_rub=("price_rub", "min"),
            median_price_rub=("price_rub", "median"),
            mean_price_rub=("price_rub", "mean"),
            max_price_rub=("price_rub", "max"),
            avg_match_score=("match_score", "mean"),
            discount_share=("has_discount", "mean"),
        )
        .sort_values(["query_label", "min_price_rub", "source_name"]) #сортировка по трем уровням (query_label - сначала группируем по товарам (iPhone 13, iPhone 14...); min_price_rub - внутри товара: от самых дешевых источников к дорогим; source_name - при равной цене - по алфавиту (Avito, Ozon...)
    )
    summary["price_spread_rub"] = summary["max_price_rub"] - summary["min_price_rub"] #расчет разброса цен
    summary["discount_share"] = (summary["discount_share"] * 100).round(1) #форматирование процентов
    summary["mean_price_rub"] = summary["mean_price_rub"].round(1) #округление чисел 
    summary["median_price_rub"] = summary["median_price_rub"].round(1) #округление чисел
    summary["avg_match_score"] = summary["avg_match_score"].round(3) #округление чисел
    summary["query_best_source"] = (
        summary.groupby("query_slug")["min_price_rub"].transform("min") == summary["min_price_rub"]
    ) #определение лучшего источника
    return summary.reset_index(drop=True)


def build_best_offers(offers: pd.DataFrame, top_n: int = 3) -> pd.DataFrame: #выбираем топ N самых интересных предложений для каждого товара
    if offers.empty:
        return pd.DataFrame()

    ranked = offers.sort_values(["query_label", "price_rub", "match_score"], ascending=[True, True, False]).copy()
    ranked["rank_inside_query"] = ranked.groupby("query_slug").cumcount() + 1
    return ranked[ranked["rank_inside_query"] <= top_n].reset_index(drop=True)
