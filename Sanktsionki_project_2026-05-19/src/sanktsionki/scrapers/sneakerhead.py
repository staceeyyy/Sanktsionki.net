from __future__ import annotations

from urllib.parse import quote_plus

from sanktsionki import config
from sanktsionki.models import ProductOffer, SearchQuery
from sanktsionki.scrapers.base import BaseScraper
from sanktsionki.utils import absolute_url, parse_price


class SneakerheadScraper(BaseScraper):
    source_name = "Sneakerhead"
    source_type = "static"

    def search(self, query: SearchQuery, limit: int = 10) -> list[ProductOffer]:
        url = f"{config.SNEAKERHEAD_BASE_URL}/search/?q={quote_plus(query.label)}"
        soup = self._get_soup(url)
        offers: list[ProductOffer] = []

        for card in soup.select(".product-card"):
            title_link = card.select_one(".product-card__link")
            price_values = card.select(".product-card__price-value")
            meta_price = card.select_one('meta[itemprop="price"]')
            image = card.select_one("noscript img") or card.select_one("img")

            title = title_link.get("title") or title_link.get_text(" ", strip=True) if title_link else ""
            old_price_rub = None
            price_rub = None
            if meta_price and meta_price.get("content"):
                price_rub = parse_price(meta_price["content"])
            if len(price_values) > 1:
                old_price_rub = parse_price(price_values[0].get_text(" ", strip=True))
                price_rub = price_rub or parse_price(price_values[-1].get_text(" ", strip=True))
            elif price_values:
                price_rub = price_rub or parse_price(price_values[0].get_text(" ", strip=True))
            score = self._is_relevant(query, title, card.get_text(" ", strip=True))

            if not title or price_rub is None or score < 0.5:
                continue

            offers.append(
                self._offer(
                    query,
                    title=title,
                    price_rub=price_rub,
                    old_price_rub=old_price_rub,
                    listing_url=absolute_url(
                        config.SNEAKERHEAD_BASE_URL,
                        title_link.get("href") if title_link else None,
                    ),
                    image_url=absolute_url(
                        config.SNEAKERHEAD_BASE_URL,
                        image.get("src") if image else None,
                    ),
                    raw_snippet=card.get_text(" ", strip=True),
                    match_override=score,
                    market_scope="local",
                    source_domain="sneakerhead.ru",
                )
            )
            if len(offers) >= limit:
                break

        return offers
