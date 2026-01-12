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
    Scrape a single product and store it in the database.
    Returns the scraped product data.
    """
    db = db or Database()

    data = scrape_product_details(
        asin=asin,
        geo_location=geo_location,
        domain=domain,
    )

    if not data:
        raise ValueError(f"No data returned for ASIN {asin}")

    db.insert_products(data)
    logger.info("Product scraped and stored: %s", asin)

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
    Fetch competitor ASINs, scrape their details, and store them in the DB.
    Returns a list of stored competitor product dicts.
    """
    db = db or Database()

    parent = db.get_product(parent_asin)
    if not parent:
        raise ValueError(f"Parent product not found: {parent_asin}")

    search_domain = parent.get("amazon_domain") or domain or "com"
    search_geo = parent.get("geo_location") or geo_location or ""

    logger.info(
        "Searching competitors | ASIN=%s | domain=%s | geo=%s",
        parent_asin,
        search_domain,
        search_geo,
    )

    # Build category filters
    search_categories = set()

    for field in ("categories", "category_path"):
        for cat in parent.get(field, []) or []:
            if isinstance(cat, str) and cat.strip():
                search_categories.add(cat.strip())

    categories_to_search = list(search_categories)[:3] or [None]

    all_results = []

    for category in categories_to_search:
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
            r.get("asin")
            for r in all_results
            if r.get("asin") and r.get("asin") != parent_asin and r.get("title")
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

    stored_competitors: List[dict] = []

    for product in scraped_products:
        if not product.get("asin"):
            continue

        product["parent_asin"] = parent_asin

        # Optional deduplication
        if db.get_product(product["asin"]):
            logger.info("Skipping existing product: %s", product["asin"])
            continue

        db.insert_products(product)
        stored_competitors.append(product)

    logger.info(
        "Stored %d competitors for parent ASIN %s",
        len(stored_competitors),
        parent_asin,
    )

    return stored_competitors


def clear_competitors(
    parent_asin: str,
    db: Optional[Database] = None,
) -> int:
    """
    Delete all competitors linked to a parent ASIN.
    Returns number of deleted products.
    """
    db = db or Database()

    competitors = db.search_products({"parent_asin": parent_asin})
    deleted = 0

    for comp in competitors:
        db.delete_product(comp["asin"])
        deleted += 1

    logger.info("Deleted %d competitors for %s", deleted, parent_asin)
    return deleted


def clear_all_products(db: Optional[Database] = None) -> None:
    """
    Delete all products from the database.
    """
    db = db or Database()
    db.clear_all_products()
    logger.warning("All products cleared from database")
