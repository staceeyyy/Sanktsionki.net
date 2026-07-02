from __future__ import annotations

from urllib.parse import quote_plus

from sanktsionki import config
from sanktsionki.models import ProductOffer, SearchQuery
from sanktsionki.scrapers.base import BaseScraper
from sanktsionki.utils import absolute_url, parse_price


class LamodaScraper(BaseScraper):
    source_name = "Lamoda"
    source_type = "static"

    def search(self, query: SearchQuery, limit: int = 10) -> list[ProductOffer]:
        url = f"{config.LAMODA_BASE_URL}/catalogsearch/result/?q={quote_plus(query.label)}"
        soup = self._get_soup(url)
        offers: list[ProductOffer] = []

        for card in soup.select(".x-product-card__card"):
            brand = card.select_one(".x-product-card-description__brand-name")
            product_name = card.select_one(".x-product-card-description__product-name")
            current_price = (
                card.select_one(".x-product-card-description__price-new")
                or card.select_one(".x-product-card-description__price-single")
            )
            old_price = card.select_one(".x-product-card-description__price-old")
            image = card.select_one("img")

            title = " ".join(
                part.get_text(" ", strip=True)
                for part in (brand, product_name)
                if part is not None
            )
            price_rub = parse_price(current_price.get_text(" ", strip=True) if current_price else "")
            old_price_rub = parse_price(old_price.get_text(" ", strip=True) if old_price else "")
            score = self._is_relevant(query, title)

            if not title or price_rub is None or score < 0.5:
                continue

            offers.append(
                self._offer(
                    query,
                    title=title,
                    price_rub=price_rub,
                    old_price_rub=old_price_rub,
                    listing_url=url,
                    image_url=absolute_url(config.LAMODA_BASE_URL, image.get("src") if image else None),
                    raw_snippet=card.get_text(" ", strip=True),
                    brand=brand.get_text(" ", strip=True) if brand else query.brand,
                    match_override=score,
                    market_scope="local",
                    source_domain="lamoda.ru",
                )
            )
            if len(offers) >= limit:
                break

        return offers
