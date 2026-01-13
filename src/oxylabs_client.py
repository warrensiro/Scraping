import logging
import time
from typing import Any, Dict, List, Optional

import requests

from src.config import OXYLABS_USERNAME, OXYLABS_PASSWORD

logger = logging.getLogger(__name__)

OXYLABS_BASE_URL = "https://realtime.oxylabs.io/v1/queries"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5


def _post_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a POST request to Oxylabs with retries and timeout.
    """
    if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
        raise RuntimeError("Oxylabs credentials are not configured")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                OXYLABS_BASE_URL,
                auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            logger.warning(
                "Oxylabs request failed (attempt %d/%d): %s",
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF * attempt)

    raise RuntimeError("Unreachable Oxylabs request failure")


def _extract_content(payload: Any) -> Dict[str, Any]:
    """
    Normalize Oxylabs response content shape.
    """
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list) and payload["results"]:
            first = payload["results"][0]
            if isinstance(first, dict):
                return first.get("content") or {}
        return payload.get("content") or {}
    return {}


def scrape_product_details(
    asin: str,
    geo_location: Optional[str] = None,
    domain: str = "com",
) -> Dict[str, Any]:
    """
    Scrape a single Amazon product by ASIN.
    """
    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": domain,
        "parse": True,
    }

    if geo_location:
        payload["geo_location"] = geo_location

    raw = _post_query(payload)
    content = _extract_content(raw)

    product = _normalize_product(content)
    product.setdefault("asin", asin)

    product.update(
        {
            "amazon_domain": domain,
            "geo_location": geo_location or "",
        }
    )

    return product


def _normalize_product(content: Dict[str, Any]) -> Dict[str, Any]:
    category_path = [
        c.strip()
        for c in content.get("category_path", [])
        if isinstance(c, str) and c.strip()
    ]

    return {
        "asin": content.get("asin"),
        "url": content.get("url"),
        "brand": content.get("brand"),
        "price": content.get("price"),
        "stock": content.get("stock"),
        "title": content.get("title"),
        "rating": content.get("rating"),
        "images": content.get("images"),
        "categories": content.get("categories", []),
        "category_path": category_path,
        "currency": content.get("currency"),
        "buybox": content.get("buybox", []),
        "product_overview": content.get("product_overview", []),
    }


def search_competitors(
    query_title: str,
    domain: str,
    categories: Optional[List[str]] = None,
    pages: int = 1,
    geo_location: str = "",
) -> List[Dict[str, Any]]:
    """
    Search Amazon for competitor products.
    """
    clean_title = _clean_product_name(query_title)
    results: List[Dict[str, Any]] = []
    seen_asins = set()

    strategies = ["featured", "price_ascending", "price_descending"]

    for sort_by in strategies:
        for page in range(1, max(1, pages) + 1):
            payload = {
                "source": "amazon_search",
                "query": clean_title,
                "parse": True,
                "domain": domain,
                "page": page,
                "sort_by": sort_by,
                "geo_location": geo_location,
            }

            if categories and categories[0]:
                payload["refinements"] = {"category": categories[0]}

            raw = _post_query(payload)
            content = _extract_content(raw)

            for item in _extract_search_items(content):
                normalized = _normalize_search_result(item)
                if not normalized:
                    continue
                asin = normalized["asin"]
                if asin not in seen_asins:
                    seen_asins.add(asin)
                    results.append(normalized)

    logger.info("Found %d competitor candidates", len(results))
    return results


def _extract_search_items(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if isinstance(content.get("results"), dict):
        items.extend(content["results"].get("organic", []))
        items.extend(content["results"].get("paid", []))

    if isinstance(content.get("products"), list):
        items.extend(content["products"])

    return items


def _normalize_search_result(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    asin = item.get("asin") or item.get("product_asin")
    title = item.get("title")

    if not asin or not title:
        return None

    return {
        "asin": asin,
        "title": title,
        "category": item.get("category"),
        "price": item.get("price"),
        "rating": item.get("rating"),
    }


def _clean_product_name(title: str) -> str:
    for sep in ("-", "|"):
        if sep in title:
            title = title.split(sep)[0]
    return title.strip()


def scrape_multiple_products(
    asins: List[str],
    geo_location: str,
    domain: str,
) -> List[Dict[str, Any]]:
    """
    Scrape multiple products safely.
    """
    products: List[Dict[str, Any]] = []

    for asin in asins:
        try:
            product = scrape_product_details(
                asin=asin,
                geo_location=geo_location,
                domain=domain,
            )
            products.append(product)
        except Exception:
            logger.exception("Failed to scrape product %s", asin)

    logger.info("Scraped %d/%d products", len(products), len(asins))
    return products
