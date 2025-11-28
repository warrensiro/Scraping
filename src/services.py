import streamlit as st
from src.db import Database
from src.oxylabs_client import (
    scrape_product_details,
    search_competitors,
    scrape_multiple_products,
)
from src.llm import analyze_competitors


def scrape_and_store_product(asin, geo_location, domain):
    """
    Scrape a single product and store it in the database.
    """
    data = scrape_product_details(asin, geo_location, domain)
    db = Database()
    db.insert_products(data)
    return data


def fetch_and_store_competitors(parent_asin, domain=None, geo_location=None, pages=2):
    """
    Fetch competitors for a parent ASIN, scrape their details, and store in DB.
    Returns a list of competitor products.
    """
    db = Database()
    parent = db.get_product(parent_asin)
    if not parent:
        st.warning("Parent product not found in database.")
        return []

    search_domain = parent.get("amazon_domain") or domain or "com"
    search_geo = parent.get("geo_location") or geo_location or ""
    st.write(f"🌍 Using domain: {search_domain} | Geo Location: {search_geo}")

    # Build categories to search (optional)
    search_categories = []
    if parent.get("categories"):
        search_categories.extend(str(cat) for cat in parent["categories"] if cat)
    if parent.get("category_path"):
        search_categories.extend(str(cat) for cat in parent["category_path"] if cat)

    # Remove duplicates and empty strings
    search_categories = list(
        set(cat.strip() for cat in search_categories if cat and cat.strip())
    )
    st.write(f"Searching in categories: {search_categories or 'All categories'}")

    all_results = []

    # If no categories, search without category filter
    categories_to_search = search_categories[:3] if search_categories else [None]

    for category in categories_to_search:
        search_results = search_competitors(
            query_title=parent.get("title"),
            domain=search_domain,
            categories=[category] if category else [],
            pages=pages,
            geo_location=search_geo,
        )
        all_results.extend(search_results)

    # Filter unique ASINs excluding the parent
    competitor_asins = list(
        set(
            r.get("asin")
            for r in all_results
            if r.get("asin") and r.get("asin") != parent_asin and r.get("title")
        )
    )

    if not competitor_asins:
        st.warning("No competitors found. Try increasing pages or check domain/geo.")
        return []

    st.write(f"🔹 Found {len(competitor_asins)} unique competitor ASINs")

    # Scrape competitor details using the parent's domain
    product_details = scrape_multiple_products(
        competitor_asins[:20], search_geo, search_domain
    )

    stored_comps = []
    for comp in product_details:
        comp["parent_asin"] = parent_asin
        db.insert_products(comp)
        stored_comps.append(comp)

    st.success("✅ Competitors scraped & stored successfully!")

    st.write("🤖 Running AI analysis...")
    try:
        analysis_text = analyze_competitors(parent_asin)
        st.text_area("AI Analysis", analysis_text, height=500)
        return analysis_text
    except Exception as e:
        st.error(f"LLM Analysis failed: {e}")
        return stored_comps


def clear_competitors(parent_asin):
    """
    Deletes all competitors for a given parent ASIN.
    """
    db = Database()
    competitors = db.search_products({"parent_asin": parent_asin})
    for comp in competitors:
        db.delete_product(comp["asin"])


def clear_all_products():
    db = Database()
    db.clear_all_products()
