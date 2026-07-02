from __future__ import annotations

from sanktsionki import config
from sanktsionki.models import ProductOffer, SearchQuery
from sanktsionki.scrapers.base import BaseScraper


class CdekShoppingScraper(BaseScraper):
    source_name = "CDEK.Shopping"
    source_type = "api"

    def search(self, query: SearchQuery, limit: int = 10) -> list[ProductOffer]:
        response = self.session.get(
            config.CDEK_SEARCH_API,
            params={"q": query.label},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        offers: list[ProductOffer] = []
        for product in payload.get("products", []):
            title = str(product.get("title") or "").strip()
            description = str(product.get("description") or "").strip()
            brand = (product.get("brand") or {}).get("title") or query.brand
            price_rub = (product.get("price") or {}).get("value")
            old_price_rub = (product.get("oldPrice") or {}).get("value")
            country_name = (product.get("country") or {}).get("name")
            images = product.get("images") or []
            slug = product.get("slug")
            product_id = product.get("id")
            score = self._is_relevant(query, title, description)

            if not title or not isinstance(price_rub, int) or score < 0.45:
                continue

            listing_url = config.CDEK_BASE_URL
            if product_id and slug:
                listing_url = f"{config.CDEK_BASE_URL}/p/{product_id}/{slug}"

            offers.append(
                self._offer(
                    query,
                    title=title,
                    price_rub=price_rub,
                    old_price_rub=old_price_rub if isinstance(old_price_rub, int) else None,
                    location=country_name,
                    seller="CDEK Shopping",
                    listing_url=listing_url,
                    image_url=images[0] if images else None,
                    availability_note="cross-border delivery",
                    raw_snippet=description or title,
                    brand=brand,
                    match_override=score,
                    country_name=country_name,
                    market_scope="cross-border",
                    source_domain="cdek.shopping",
                )
            )
            if len(offers) >= limit:
                break

        return offers
