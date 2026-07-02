# Полноценное аналитическое веб-приложение на Dash, которое показывает цены на одежду из разных источников (Lamoda, Avito, CDEK.Shopping), 
# позволяет искать товары в реальном времени, 
# визуализирует данные на графиках,
# включает аналитику по комиссиям байеров из Telegram-чатов.

    
from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate

from sanktsionki import config
from sanktsionki.models import SearchQuery
from sanktsionki.services.analytics import build_market_summary
from sanktsionki.services.pipeline import OfferPipeline
from sanktsionki.utils import clean_whitespace


PAPER_BG = "#f6efe6"
CARD_BG = "#fffaf2"
INK = "#1d1a16"
MUTED = "#756c61"
ACCENT = "#d16a3d"
ACCENT_2 = "#2f6f66"
GRID = "#e7dac8"
SOURCE_ORDER = ["Lamoda", "Sneakerhead", "Avito", "CDEK.Shopping"]
SOURCE_COLORS = {
    "Lamoda": "#d16a3d",
    "Sneakerhead": "#2f6f66",
    "Avito": "#a76d1f",
    "CDEK.Shopping": "#2d5e9b",
}
MARKET_SCOPE_LABELS = {
    "local": "Локальный retail",
    "marketplace": "Маркетплейс / ресейл",
    "cross-border": "Международный канал",
}
BUYER_METRIC_LABELS = {
    "commission": "Комиссия байера",
    "delivery": "Доставка",
    "customs": "Таможня",
    "total": "Итог под ключ",
    "price_talk": "Общие обсуждения цены",
}


def load_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{int(round(float(value))):,} ₽".replace(",", " ")


def market_scope_label(value: str | None) -> str:
    return MARKET_SCOPE_LABELS.get(str(value or "local"), "Локальный retail")


def frame_to_store(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    return frame.to_json(orient="split", date_format="iso", force_ascii=False)


def frame_from_store(payload: str | None) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    return pd.read_json(StringIO(payload), orient="split")


def ordered_sources(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "source_name" not in frame:
        return SOURCE_ORDER.copy()
    current_sources = frame["source_name"].dropna().astype(str).unique().tolist()
    ordered = [source for source in SOURCE_ORDER if source in current_sources]
    ordered.extend(sorted(source for source in current_sources if source not in ordered))
    return ordered


def empty_figure(title: str, note: str) -> object:
    fig = px.scatter()
    fig.update_layout(
        template=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Bahnschrift, Segoe UI, sans-serif", "color": INK},
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        text=note,
        font={"size": 15, "color": MUTED},
    )
    return fig


def style_figure(fig: object, *, showlegend: bool = True) -> object:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Bahnschrift, Segoe UI, sans-serif", "color": INK},
        legend_title_text="",
        showlegend=showlegend,
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def build_price_chart(summary: pd.DataFrame, title: str) -> object:
    if summary.empty:
        return empty_figure("Нет данных по площадкам", "Для этого запроса пока не удалось собрать офферы.")

    fig = px.bar(
        summary.sort_values(["min_price_rub", "source_name"]),
        x="source_name",
        y=["min_price_rub", "median_price_rub"],
        barmode="group",
        title=title,
        text_auto=True,
        color_discrete_sequence=[ACCENT, ACCENT_2],
    )
    fig.update_layout(xaxis_title="Площадка", yaxis_title="Цена, ₽")
    return style_figure(fig)


def build_distribution_chart(offers: pd.DataFrame, title: str) -> object:
    if offers.empty:
        return empty_figure("Нет распределения цен", "Сначала выберите модель с доступными офферами.")

    fig = px.box(
        offers,
        x="source_name",
        y="price_rub",
        color="source_name",
        points="all",
        title=title,
        hover_data=["title", "country_name", "seller"],
        color_discrete_map=SOURCE_COLORS,
        category_orders={"source_name": ordered_sources(offers)},
    )
    fig.update_layout(xaxis_title="Площадка", yaxis_title="Цена, ₽")
    return style_figure(fig, showlegend=False)


def build_heatmap(offers: pd.DataFrame, selected_sources: list[str]) -> object:
    if offers.empty:
        return empty_figure("Тепловая карта недоступна", "Запустите сбор данных, чтобы построить общую картину рынка.")

    filtered = offers[offers["source_name"].isin(selected_sources)].copy()
    summary = build_market_summary(filtered)
    if summary.empty:
        return empty_figure("Нет данных для heatmap", "Выбранные площадки не содержат подходящих офферов.")

    heatmap = summary.pivot_table(
        index="query_label",
        columns="source_name",
        values="min_price_rub",
        aggfunc="min",
    )
    heatmap = heatmap.reindex(columns=[source for source in ordered_sources(filtered) if source in heatmap.columns])
    fig = px.imshow(
        heatmap,
        text_auto=True,
        aspect="auto",
        color_continuous_scale=["#fff5e8", "#f6c98e", "#d16a3d"],
        title="Минимальные цены по всем сохраненным запросам",
    )
    fig.update_layout(xaxis_title="Площадка", yaxis_title="Поисковый запрос")
    return style_figure(fig)


def build_live_scope_chart(offers: pd.DataFrame, query_label: str) -> object:
    if offers.empty:
        return empty_figure("Живой поиск пуст", "Введите модель или артикул и запустите поиск.")

    plot_frame = offers.copy()
    plot_frame["market_scope_label"] = plot_frame["market_scope"].apply(market_scope_label)
    fig = px.scatter(
        plot_frame,
        x="source_name",
        y="price_rub",
        color="market_scope_label",
        hover_data=["title", "country_name", "seller"],
        title=f"Живой поиск: {query_label}",
        category_orders={"source_name": ordered_sources(plot_frame)},
        color_discrete_map={
            "Локальный retail": ACCENT,
            "Маркетплейс / ресейл": "#a76d1f",
            "Международный канал": "#2d5e9b",
        },
    )
    fig.update_layout(xaxis_title="Площадка", yaxis_title="Цена, ₽")
    return style_figure(fig)


def offer_rows(offers: pd.DataFrame, limit: int = 12) -> list[dict[str, object]]:
    if offers.empty:
        return []

    ranked = offers.sort_values(["price_rub", "match_score"], ascending=[True, False]).head(limit).copy()
    ranked["price_rub"] = ranked["price_rub"].apply(money)
    ranked["old_price_rub"] = ranked["old_price_rub"].apply(money)
    ranked["market_scope_label"] = ranked["market_scope"].apply(market_scope_label)
    ranked["country_display"] = ranked["country_name"].fillna(ranked["location"]).fillna("Россия")
    ranked["seller"] = ranked["seller"].fillna("n/a")
    return ranked[
        [
            "source_name",
            "market_scope_label",
            "title",
            "price_rub",
            "old_price_rub",
            "country_display",
            "seller",
            "offer_link",
        ]
    ].to_dict("records")


def build_offer_table(table_id: str, page_size: int = 12) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=[
            {"name": "Площадка", "id": "source_name"},
            {"name": "Канал", "id": "market_scope_label"},
            {"name": "Название", "id": "title"},
            {"name": "Цена", "id": "price_rub"},
            {"name": "Старая цена", "id": "old_price_rub"},
            {"name": "Страна / город", "id": "country_display"},
            {"name": "Продавец", "id": "seller"},
            {"name": "Ссылка", "id": "offer_link", "presentation": "markdown"},
        ],
        markdown_options={"link_target": "_blank"},
        page_size=page_size,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": CARD_BG,
            "color": INK,
            "fontWeight": "600",
            "border": f"1px solid {GRID}",
        },
        style_cell={
            "backgroundColor": "#fffefb",
            "color": INK,
            "border": f"1px solid {GRID}",
            "textAlign": "left",
            "padding": "10px",
            "fontFamily": "Bahnschrift, Segoe UI, sans-serif",
            "whiteSpace": "normal",
            "height": "auto",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": "{source_name} = 'Avito'"},
                "backgroundColor": "#fff6f0",
            },
            {
                "if": {"filter_query": "{source_name} = 'CDEK.Shopping'"},
                "backgroundColor": "#f3f7ff",
            },
        ],
    )


def buyer_metric_value(summary: pd.DataFrame, metric: str) -> str:
    if summary.empty:
        return "n/a"
    row = summary.loc[summary["metric"] == metric]
    if row.empty:
        return "n/a"
    return money(row["median_rub"].iloc[0])


def buyer_top_country(mentions: pd.DataFrame) -> str:
    if mentions.empty or "country_name" not in mentions:
        return "n/a"
    country_counts = (
        mentions.dropna(subset=["country_name"])
        .groupby("country_name", as_index=False)
        .size()
        .sort_values(["size", "country_name"], ascending=[False, True])
    )
    if country_counts.empty:
        return "n/a"
    top_row = country_counts.iloc[0]
    return f"{top_row['country_name']} ({int(top_row['size'])})"


def build_buyer_metric_chart(summary: pd.DataFrame) -> object:
    if summary.empty:
        return empty_figure("Нет аналитики по чатам", "Запустите analyze_buyer_chats.py или используйте sample JSON.")

    plot_frame = summary.copy()
    plot_frame["metric_label"] = plot_frame["metric"].map(BUYER_METRIC_LABELS).fillna(plot_frame["metric"])
    fig = px.bar(
        plot_frame.sort_values(["median_rub", "metric_label"]),
        x="metric_label",
        y="median_rub",
        text_auto=True,
        title="Медианные расходы по услугам байеров",
        color="metric_label",
        color_discrete_sequence=[ACCENT, ACCENT_2, "#2d5e9b", "#a76d1f", "#9a7a59"],
    )
    fig.update_layout(xaxis_title="Метрика", yaxis_title="Медианная сумма, ₽")
    return style_figure(fig, showlegend=False)


def build_buyer_country_chart(mentions: pd.DataFrame) -> object:
    if mentions.empty or "country_name" not in mentions:
        return empty_figure("Нет страновых маршрутов", "Добавьте экспорт Telegram-чата, чтобы увидеть географию байеров.")

    plot_frame = (
        mentions.dropna(subset=["country_name"])
        .groupby("country_name", as_index=False)
        .agg(mention_count=("amount_rub", "count"), median_rub=("amount_rub", "median"))
        .sort_values(["mention_count", "median_rub"], ascending=[False, True])
    )
    if plot_frame.empty:
        return empty_figure("Нет страновых маршрутов", "В сообщениях пока не встретились страны отправления.")

    fig = px.bar(
        plot_frame,
        x="country_name",
        y="mention_count",
        text_auto=True,
        color="median_rub",
        color_continuous_scale=["#fff5e8", "#f6c98e", "#2d5e9b"],
        title="Какие страны чаще всего встречаются в чатах байеров",
    )
    fig.update_layout(xaxis_title="Страна", yaxis_title="Число упоминаний")
    return style_figure(fig)


def buyer_summary_rows(summary: pd.DataFrame) -> list[dict[str, object]]:
    if summary.empty:
        return []
    rows = summary.copy()
    rows["metric_label"] = rows["metric"].map(BUYER_METRIC_LABELS).fillna(rows["metric"])
    rows["min_rub"] = rows["min_rub"].apply(money)
    rows["median_rub"] = rows["median_rub"].apply(money)
    rows["mean_rub"] = rows["mean_rub"].apply(money)
    rows["max_rub"] = rows["max_rub"].apply(money)
    rows["top_country"] = rows["top_country"].fillna("n/a")
    rows["top_country_mentions"] = rows["top_country_mentions"].fillna(0).astype(int)
    return rows[
        [
            "metric_label",
            "mention_count",
            "min_rub",
            "median_rub",
            "mean_rub",
            "max_rub",
            "top_country",
            "top_country_mentions",
        ]
    ].to_dict("records")


def build_buyer_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="buyer-chat-table",
        columns=[
            {"name": "Метрика", "id": "metric_label"},
            {"name": "Упоминаний", "id": "mention_count"},
            {"name": "Минимум", "id": "min_rub"},
            {"name": "Медиана", "id": "median_rub"},
            {"name": "Среднее", "id": "mean_rub"},
            {"name": "Максимум", "id": "max_rub"},
            {"name": "Топ-страна", "id": "top_country"},
            {"name": "Упоминаний страны", "id": "top_country_mentions"},
        ],
        data=[],
        page_size=8,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": CARD_BG,
            "color": INK,
            "fontWeight": "600",
            "border": f"1px solid {GRID}",
        },
        style_cell={
            "backgroundColor": "#fffefb",
            "color": INK,
            "border": f"1px solid {GRID}",
            "textAlign": "left",
            "padding": "10px",
            "fontFamily": "Bahnschrift, Segoe UI, sans-serif",
        },
    )


def build_app(data_path: Path = config.OFFERS_CSV) -> Dash:
    app = Dash(
        __name__,
        title="Sanktsionki Dashboard",
        assets_folder=str(config.ASSETS_DIR),
    )

    offers = load_frame(data_path)
    buyer_summary = load_frame(config.BUYER_CHAT_SUMMARY_CSV)
    buyer_mentions = load_frame(config.BUYER_CHAT_MESSAGES_CSV)
    query_options = []
    if not offers.empty:
        query_options = [
            {"label": label.title(), "value": slug}
            for slug, label in offers[["query_slug", "query_label"]].drop_duplicates().sort_values("query_label").values
        ]
    default_query = query_options[0]["value"] if query_options else None
    source_values = ordered_sources(offers)

    buyer_metric_chart = build_buyer_metric_chart(buyer_summary)
    buyer_country_chart = build_buyer_country_chart(buyer_mentions)
    buyer_rows = buyer_summary_rows(buyer_summary)
    saved_snapshot_note = (
        f"Сохранено {len(offers)} офферов по {len(query_options)} моделям."
        if not offers.empty
        else "Сначала выполните `py -3 scripts/collect_offers.py --limit 6`, чтобы наполнить сохраненный срез рынка."
    )

    app.layout = html.Div(
        className="page-shell",
        children=[
            html.Div(
                className="hero-card",
                children=[
                    html.P("Sanktsionki.net", className="eyebrow"),
                    html.H1("Платформа для поиска выгодных sneaker-предложений в России и за рубежом"),
                    html.P(
                        "Проект закрывает обе части исходной идеи: российский рынок, живой поиск модели, "
                        "международный канал через CDEK.Shopping, Telegram-чаты байеров и экспорт в Google Sheets."
                    ),
                    html.Div(
                        className="pill-row",
                        children=[
                            html.Span("ООП-архитектура", className="pill"),
                            html.Span("Selenium + Edge", className="pill"),
                            html.Span("Dash dashboard", className="pill"),
                            html.Span("Google Sheets API", className="pill"),
                            html.Span("Telegram buyer chats", className="pill"),
                        ],
                    ),
                    html.Div(
                        className="insight-grid",
                        children=[
                            html.Div(
                                className="insight-card",
                                children=[
                                    html.H3("Российский срез"),
                                    html.P("Lamoda, Sneakerhead и Avito используются для сравнения локальных цен."),
                                ],
                            ),
                            html.Div(
                                className="insight-card",
                                children=[
                                    html.H3("Международный канал"),
                                    html.P("CDEK.Shopping показывает зарубежные предложения по тем же моделям."),
                                ],
                            ),
                            html.Div(
                                className="insight-card",
                                children=[
                                    html.H3("Интеграции"),
                                    html.P("CSV выгрузки можно отправить в Google Sheets и дополнять аналитикой по чатам байеров."),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card",
                children=[
                    html.Div(
                        className="section-head",
                        children=[
                            html.P("Секция 1", className="section-eyebrow"),
                            html.H2("Сохраненный срез рынка"),
                            html.P(saved_snapshot_note, className="section-note"),
                        ],
                    ),
                    html.Div(
                        className="control-row",
                        children=[
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Label("Выбрать модель из сохраненного набора"),
                                    dcc.Dropdown(
                                        id="query-dropdown",
                                        options=query_options,
                                        value=default_query,
                                        clearable=False,
                                        placeholder="Сначала соберите данные",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Label("Показывать площадки"),
                                    dcc.Checklist(
                                        id="source-filter",
                                        options=[{"label": source, "value": source} for source in source_values],
                                        value=source_values,
                                        inline=True,
                                        className="source-checklist",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="kpi-grid",
                        children=[
                            html.Div([html.P("Всего офферов", className="kpi-label"), html.H2(id="kpi-offers")], className="kpi-card"),
                            html.Div([html.P("Лучшая цена", className="kpi-label"), html.H2(id="kpi-best-price")], className="kpi-card"),
                            html.Div([html.P("Лучшая площадка", className="kpi-label"), html.H2(id="kpi-best-source")], className="kpi-card"),
                            html.Div([html.P("Разброс цен", className="kpi-label"), html.H2(id="kpi-spread")], className="kpi-card"),
                        ],
                    ),
                    html.Div(
                        className="chart-grid",
                        children=[
                            html.Div(dcc.Graph(id="source-price-chart"), className="chart-card"),
                            html.Div(dcc.Graph(id="price-distribution-chart"), className="chart-card"),
                        ],
                    ),
                    html.Div(className="chart-card full-width", children=[dcc.Graph(id="market-heatmap")]),
                    html.Div(
                        className="table-card",
                        children=[
                            html.H3("Лучшие офферы по выбранной модели"),
                            build_offer_table("offers-table"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card",
                children=[
                    html.Div(
                        className="section-head",
                        children=[
                            html.P("Секция 2", className="section-eyebrow"),
                            html.H2("Живой поиск модели или артикула"),
                            html.P(
                                "Введите свободный запрос. Дашборд соберет локальные и международные предложения прямо во время показа.",
                                className="section-note",
                            ),
                        ],
                    ),
                    html.Div(
                        className="live-search-row",
                        children=[
                            dcc.Input(
                                id="live-query-input",
                                type="text",
                                className="text-input",
                                placeholder="Например: Nike Air Force 1 07 white",
                            ),
                            html.Button("Запустить поиск", id="run-live-search", className="button-primary", n_clicks=0),
                        ],
                    ),
                    dcc.Store(id="live-search-store"),
                    dcc.Loading(
                        type="default",
                        children=html.Div(
                            id="live-search-status",
                            className="status-text",
                            children="Введите запрос и запустите поиск по площадкам.",
                        ),
                    ),
                    html.Div(
                        className="kpi-grid",
                        children=[
                            html.Div([html.P("Живых офферов", className="kpi-label"), html.H2(id="live-kpi-offers")], className="kpi-card"),
                            html.Div([html.P("Лучшая цена", className="kpi-label"), html.H2(id="live-kpi-best-price")], className="kpi-card"),
                            html.Div([html.P("Лучшая площадка", className="kpi-label"), html.H2(id="live-kpi-best-source")], className="kpi-card"),
                            html.Div([html.P("Лучший канал", className="kpi-label"), html.H2(id="live-kpi-scope")], className="kpi-card"),
                        ],
                    ),
                    html.Div(
                        className="chart-grid",
                        children=[
                            html.Div(dcc.Graph(id="live-price-chart"), className="chart-card"),
                            html.Div(dcc.Graph(id="live-scope-chart"), className="chart-card"),
                        ],
                    ),
                    html.Div(
                        className="table-card",
                        children=[
                            html.H3("Результаты живого поиска"),
                            build_offer_table("live-offers-table", page_size=10),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card",
                children=[
                    html.Div(
                        className="section-head",
                        children=[
                            html.P("Секция 3", className="section-eyebrow"),
                            html.H2("Аналитика по чатам байеров"),
                            html.P(
                                "Эта часть закрывает расширение исходной идеи: оцениваем комиссии, логистику и географию закупки через Telegram-экспорт.",
                                className="section-note",
                            ),
                        ],
                    ),
                    html.Div(
                        className="kpi-grid",
                        children=[
                            html.Div([html.P("Медиана комиссии", className="kpi-label"), html.H2(buyer_metric_value(buyer_summary, "commission"))], className="kpi-card"),
                            html.Div([html.P("Медиана доставки", className="kpi-label"), html.H2(buyer_metric_value(buyer_summary, "delivery"))], className="kpi-card"),
                            html.Div([html.P("Медиана total", className="kpi-label"), html.H2(buyer_metric_value(buyer_summary, "total"))], className="kpi-card"),
                            html.Div([html.P("Топ-страна", className="kpi-label"), html.H2(buyer_top_country(buyer_mentions))], className="kpi-card"),
                        ],
                    ),
                    html.Div(
                        className="chart-grid",
                        children=[
                            html.Div(dcc.Graph(figure=buyer_metric_chart), className="chart-card"),
                            html.Div(dcc.Graph(figure=buyer_country_chart), className="chart-card"),
                        ],
                    ),
                    html.Div(
                        className="table-card",
                        children=[
                            html.H3("Сводка по метрикам чатов"),
                            build_buyer_table(),
                        ],
                    ),
                    html.Div(
                        className="callout-card",
                        children=[
                            html.H3("Google Sheets API"),
                            html.P(
                                "Для выгрузки результатов в общую таблицу используйте команду "
                                "`py -3 scripts/export_google_sheets.py --spreadsheet-id <ID>` "
                                "и укажите `GOOGLE_SERVICE_ACCOUNT_FILE` с ключом сервисного аккаунта."
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    @app.callback(
        Output("kpi-offers", "children"),
        Output("kpi-best-price", "children"),
        Output("kpi-best-source", "children"),
        Output("kpi-spread", "children"),
        Output("source-price-chart", "figure"),
        Output("price-distribution-chart", "figure"),
        Output("market-heatmap", "figure"),
        Output("offers-table", "data"),
        Input("query-dropdown", "value"),
        Input("source-filter", "value"),
    )
    def update_saved_market(query_slug: str | None, selected_sources: list[str] | None):
        if offers.empty or not query_slug:
            empty_fig = empty_figure("Нет сохраненных данных", "Сначала соберите CSV с офферами.")
            return ("0", "n/a", "n/a", "n/a", empty_fig, empty_fig, empty_fig, [])

        chosen_sources = selected_sources or ordered_sources(offers)
        filtered = offers[
            (offers["query_slug"] == query_slug)
            & (offers["source_name"].isin(chosen_sources))
        ].copy()
        if filtered.empty:
            empty_fig = empty_figure("Нет данных по фильтру", "Снимите часть фильтров или выберите другую модель.")
            return ("0", "n/a", "n/a", "n/a", empty_fig, empty_fig, empty_fig, [])

        local_summary = build_market_summary(filtered)
        best_row = filtered.sort_values(["price_rub", "match_score"], ascending=[True, False]).iloc[0]
        spread = filtered["price_rub"].max() - filtered["price_rub"].min()
        query_label = str(filtered["query_label"].iloc[0]).title()

        return (
            str(len(filtered)),
            money(best_row["price_rub"]),
            str(best_row["source_name"]),
            money(spread),
            build_price_chart(local_summary, f"Минимальная и медианная цена: {query_label}"),
            build_distribution_chart(filtered, "Распределение цен по площадкам"),
            build_heatmap(offers, chosen_sources),
            offer_rows(filtered, limit=12),
        )

    @app.callback(
        Output("live-search-store", "data"),
        Output("live-search-status", "children"),
        Input("run-live-search", "n_clicks"),
        State("live-query-input", "value"),
        prevent_initial_call=True,
    )
    def run_live_search(n_clicks: int, raw_query: str | None):
        del n_clicks
        query_text = clean_whitespace(raw_query)
        if not query_text:
            return no_update, "Введите модель или артикул перед запуском поиска."

        pipeline = OfferPipeline(queries=[SearchQuery.from_text(query_text)])
        artifacts = pipeline.run(limit_per_source=6)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if artifacts.offers.empty:
            return (
                {"query_text": query_text, "offers": "", "summary": ""},
                f"{timestamp}: по запросу “{query_text}” подходящих офферов не найдено.",
            )

        found_sources = ", ".join(ordered_sources(artifacts.offers))
        return (
            {
                "query_text": query_text,
                "offers": frame_to_store(artifacts.offers),
                "summary": frame_to_store(artifacts.summary),
            },
            f"{timestamp}: найдено {len(artifacts.offers)} офферов. Источники: {found_sources}.",
        )

    @app.callback(
        Output("live-kpi-offers", "children"),
        Output("live-kpi-best-price", "children"),
        Output("live-kpi-best-source", "children"),
        Output("live-kpi-scope", "children"),
        Output("live-price-chart", "figure"),
        Output("live-scope-chart", "figure"),
        Output("live-offers-table", "data"),
        Input("live-search-store", "data"),
    )
    def update_live_market(store_data: dict[str, str] | None):
        if not store_data:
            empty_fig = empty_figure("Живой поиск еще не запускался", "Введите модель в поле выше.")
            return ("0", "n/a", "n/a", "n/a", empty_fig, empty_fig, [])

        live_offers = frame_from_store(store_data.get("offers"))
        live_summary = frame_from_store(store_data.get("summary"))
        query_text = str(store_data.get("query_text") or "модель")
        if live_offers.empty:
            empty_fig = empty_figure("Нет результатов", "Попробуйте переформулировать запрос или использовать артикул.")
            return ("0", "n/a", "n/a", "n/a", empty_fig, empty_fig, [])

        if live_summary.empty:
            live_summary = build_market_summary(live_offers)

        best_row = live_offers.sort_values(["price_rub", "match_score"], ascending=[True, False]).iloc[0]
        return (
            str(len(live_offers)),
            money(best_row["price_rub"]),
            str(best_row["source_name"]),
            market_scope_label(best_row.get("market_scope")),
            build_price_chart(live_summary, f"Живой поиск: {query_text}"),
            build_live_scope_chart(live_offers, query_text),
            offer_rows(live_offers, limit=10),
        )

    @app.callback(
        Output("buyer-chat-table", "data"),
        Input("buyer-chat-table", "id"),
    )
    def hydrate_buyer_table(_: str):
        return buyer_rows

    return app


def main() -> None:
    app = build_app()
    app.run(debug=False)


if __name__ == "__main__":
    main()
