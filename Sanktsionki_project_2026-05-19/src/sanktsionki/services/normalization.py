# Получаем сырые данные от парсеров. Этот кодик очищает и структурирует данные, рассчитывает скидки для пользователя, сортирует от лучших предложений к худшим, 
# готовит данные для отображения в дашборде.

from __future__ import annotations

import pandas as pd

from sanktsionki.utils import offer_link_markdown


def offers_to_frame(records: list[dict[str, object]]) -> pd.DataFrame: #список словарей (каждый словарь - одно предложение от парсера)
    if not records:
        return pd.DataFrame() #на выходе получим табличку

    frame = pd.DataFrame(records)
    defaults: dict[str, object] = {
        "old_price_rub": None,
        "location": None,
        "seller": None,
        "image_url": None,
        "availability_note": None,
        "raw_snippet": None,
        "country_name": None,
        "market_scope": "local",
        "source_domain": None,
    }
    for column_name, default_value in defaults.items(): #проходим по всем дефолтным колонкам, проверяем, есть ли такая колонка в DataFrame, если нет, то создаем колонку и заполняем дефолтным значением
        if column_name not in frame:
            frame[column_name] = default_value

    frame = frame.drop_duplicates(
        subset=["query_slug", "source_name", "title", "price_rub", "listing_url"], #проверяем уникальность только по этим колонкам 
        keep="first", #оставляем первое вхождение, остальные удаляем
    )
    frame["discount_rub"] = (
        frame["old_price_rub"].fillna(frame["price_rub"]) - frame["price_rub"]
    ).clip(lower=0) #считаем скидку
    frame["has_discount"] = frame["discount_rub"] > 0
    frame["offer_link"] = frame["listing_url"].apply(offer_link_markdown)
    frame = frame.sort_values(
        ["query_label", "source_name", "price_rub", "match_score"],
        ascending=[True, True, True, False], #создаем сортировку (при равной цене - более релевантные выше (чем больше, тем лучше))
    )
    frame.reset_index(drop=True, inplace=True) #после удаления дубликатов и сортировки индексы становятся не последовательными (5, 12, 0...), поэтому cбрасываем для красивого вывода.
    return frame
