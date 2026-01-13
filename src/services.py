import logging
from typing import List, Optional

from src.db import Database
from src.oxylabs_client import (
    scrape_product_details,
    search_competitors,
    scrape_multiple_products,
)

logger = logging.getLogger(__name__)


def scrape_and_store_product(
    asin: str,
    geo_location: Optional[str],
    domain: str,
    db: Optional[Database] = None,
) -> dict:
    """
    Scrape a single Amazon product and upsert it into the database.
    Safe to call multiple times (idempotent).
    """
    db = db or Database()

    logger.info("Scraping product ASIN=%s", asin)

    data = scrape_product_details(
        asin=asin,
        geo_location=geo_location,
        domain=domain,
    )

    if not data:
        raise ValueError(f"No data returned for ASIN {asin}")

    data.update(
        {
            "asin": asin,
            "geo_location": geo_location,
            "amazon_domain": domain,
            "type": "product",
        }
    )

    if not data.get("title"):
        raise ValueError("Scraped product missing title")

    db.upsert_product(data)

    logger.info("Product stored (upserted): %s", asin)
    return data


def fetch_and_store_competitors(
    parent_asin: str,
    domain: Optional[str] = None,
    geo_location: Optional[str] = None,
    pages: int = 2,
    limit: int = 20,
    db: Optional[Database] = None,
) -> List[dict]:
    """
    Discover competitor ASINs, scrape them, and store as competitors.
    Safe to re-run; competitors are upserted.
    """
    db = db or Database()

    parent = db.get_product(parent_asin)
    if not parent:
        raise ValueError(f"Parent product not found: {parent_asin}")

    search_domain = parent.get("amazon_domain") or domain or "com"
    search_geo = parent.get("geo_location") or geo_location or ""

    logger.info(
        "Searching competitors | parent=%s | domain=%s | geo=%s",
        parent_asin,
        search_domain,
        search_geo,
    )

    # Extract up to 3 relevant categories
    search_categories = set()
    for field in ("categories", "category_path"):
        for cat in parent.get(field, []) or []:
            if isinstance(cat, str) and cat.strip():
                search_categories.add(cat.strip())

    categories = list(search_categories)[:3] or [None]

    all_results = []
    for category in categories:
        results = search_competitors(
            query_title=parent.get("title"),
            domain=search_domain,
            categories=[category] if category else [],
            pages=pages,
            geo_location=search_geo,
        )
        all_results.extend(results)

    competitor_asins = list(
        {
            r["asin"]
            for r in all_results
            if r.get("asin") and r.get("title") and r["asin"] != parent_asin
        }
    )

    if not competitor_asins:
        logger.warning("No competitors found for %s", parent_asin)
        return []

    logger.info("Found %d competitor ASINs", len(competitor_asins))

    scraped_products = scrape_multiple_products(
        asins=competitor_asins[:limit],
        geo_location=search_geo,
        domain=search_domain,
    )

    stored: List[dict] = []

    for product in scraped_products:
        asin = product.get("asin")
        if not asin:
            continue

        product.update(
            {
                "type": "competitor",
                "parent_asin": parent_asin,
                "amazon_domain": search_domain,
                "geo_location": search_geo,
            }
        )

        db.upsert_product(product)
        stored.append(product)

    logger.info(
        "Stored %d competitors for parent ASIN %s",
        len(stored),
        parent_asin,
    )

    return stored


def clear_competitors(
    parent_asin: str,
    db: Optional[Database] = None,
) -> None:
    """
    Delete all competitors linked to a parent ASIN.
    """
    db = db or Database()
    db.delete_competitors(parent_asin)
    logger.info("Competitors cleared for %s", parent_asin)


def clear_all_products(db: Optional[Database] = None) -> None:
    """
    Delete all products and competitors.
    """
    db = db or Database()
    db.clear_all()
    logger.warning("All products cleared from database")
