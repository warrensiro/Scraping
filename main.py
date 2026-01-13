import streamlit as st
import pandas as pd
import logging

from src.services import (
    scrape_and_store_product,
    fetch_and_store_competitors,
    clear_all_products,
)
from src.db import Database
from src.llm import analyze_competitors

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Database and caching
# -------------------------
@st.cache_resource(show_spinner=False)
def get_db() -> Database:
    """Return a singleton database instance."""
    return Database()


@st.cache_data(ttl=60, show_spinner=False)
def get_products() -> list:
    """Return all products from DB with caching."""
    return get_db().get_all_products() or []


@st.cache_data(ttl=300, show_spinner=False)
def get_llm_analysis(asin: str) -> str:
    """Run LLM analysis (cached)."""
    try:
        return analyze_competitors(asin)
    except Exception:
        logger.exception("LLM analysis failed for ASIN %s", asin)
        return "LLM analysis failed."


def invalidate_products_cache():
    """Force refresh product cache."""
    get_products.clear()


# -------------------------
# UI Components
# -------------------------
def render_header():
    st.title("Amazon Competitor Analysis")
    st.caption("Scrape products and analyze competitors")


def render_sidebar():
    st.sidebar.header("Product Inputs")

    asin = st.sidebar.text_input("ASIN", placeholder="e.g. B01N1A3BUH").strip()
    geo = st.sidebar.text_input("Zip / Postal Code", placeholder="Optional").strip()
    domain = st.sidebar.selectbox(
        "Amazon Domain", ["com", "ca", "co.uk", "de", "fr", "it", "ae"]
    )

    db = get_db()

    # ----------------- Scrape Product -----------------
    if st.sidebar.button("Scrape Product", disabled=not asin):
        with st.spinner(f"Scraping ASIN {asin}..."):
            try:
                scrape_and_store_product(asin, geo, domain, db=db)
                invalidate_products_cache()  # refresh products
                st.session_state.selected_asin = asin
                st.session_state.page = 1
                st.success(f"Product {asin} scraped successfully!")
            except Exception:
                st.error("Scraping failed. Check logs.")
                logger.exception("Scrape failed for ASIN %s", asin)

    # ----------------- Clear All Products -----------------
    if st.sidebar.button("Clear All Products"):
        with st.spinner("Clearing database..."):
            clear_all_products(db=db)
            invalidate_products_cache()
            st.session_state.selected_asin = None
            st.session_state.page = 1
            st.success("All products cleared!")

    return domain, geo


def render_product_card(product: dict, domain_default: str, geo_default: str):
    """Render a single product card with competitors and LLM button."""
    asin = product.get("asin")
    if not asin:
        return

    title = product.get("title", asin)
    images = product.get("images") or []
    price = product.get("price", "-")
    currency = product.get("currency", "")
    brand = product.get("brand", "-")
    url = product.get("url", "")
    domain = product.get("amazon_domain", domain_default)
    geo = product.get("geo_location", geo_default or "-")

    # ----------------- Product Info -----------------
    with st.container():
        cols = st.columns([1, 2])
        if images:
            cols[0].image(images[0], width=160)
        else:
            cols[0].caption("No image")

        with cols[1]:
            st.subheader(title[:90])
            st.metric("Price", f"{currency} {price}" if currency else price)
            st.write(f"Brand: {brand}")
            st.caption(f"Domain: amazon.{domain} | Geo: {geo}")
            if url:
                st.markdown(f"[View on Amazon]({url})")

            # Show competitors button
            if st.button("Show Competitors", key=f"show_{asin}"):
                st.session_state.selected_asin = asin

    # ----------------- Competitors -----------------
    if st.session_state.get("selected_asin") != asin:
        return

    render_competitors(asin, domain, geo)


def render_competitors(asin: str, domain: str, geo: str):
    """Display competitors and analysis for a product."""
    db = get_db()
    competitors = db.search_products({"parent_asin": asin})

    # Fetch competitors if not already stored
    if not competitors:
        with st.spinner("Fetching competitors..."):
            try:
                competitors = fetch_and_store_competitors(
                    parent_asin=asin, domain=domain, geo_location=geo, db=db
                )
                invalidate_products_cache()
            except Exception:
                st.error("Failed to fetch competitors")
                logger.exception("Competitor fetch failed for ASIN %s", asin)
                return

    if not competitors:
        st.warning("No competitors found")
        return

    # ----------------- Competitor Summary -----------------
    df = pd.DataFrame(competitors)
    df["price"] = pd.to_numeric(df.get("price"), errors="coerce")

    st.markdown("### Competitor Summary")
    st.write(f"Average Price: {df['price'].mean():.2f}")
    st.write(f"Lowest Price: {df['price'].min():.2f}")
    st.write(f"Highest Price: {df['price'].max():.2f}")
    if "rating" in df.columns:
        st.write(f"Average Rating: {df['rating'].mean():.2f}")

    st.download_button(
        "Download Competitors CSV", df.to_csv(index=False), "competitors.csv"
    )

    chart_df = df[["title", "price"]].dropna().set_index("title")
    st.bar_chart(chart_df)

    # ----------------- Competitor List -----------------
    with st.expander("Competitor List"):
        for c in competitors:
            st.write(
                f"- {c.get('asin')} | {c.get('title')} | {c.get('currency', '')} {c.get('price', '-')}"
            )

    # ----------------- LLM Analysis -----------------
    if st.button("Analyze with LLM", key=f"llm_{asin}"):
        with st.spinner("Running LLM analysis..."):
            result = get_llm_analysis(asin)
            st.markdown("### LLM Analysis")
            st.text(result)


# -------------------------
# Main
# -------------------------
def main():
    st.set_page_config(page_title="Amazon Competitor Analysis", layout="wide")

    st.session_state.setdefault("selected_asin", None)
    st.session_state.setdefault("page", 1)

    render_header()
    domain, geo = render_sidebar()

    products = get_products()
    if not products:
        st.info("No products scraped yet.")
        return

    st.divider()
    st.subheader("Scraped Products")

    # ----------------- Pagination -----------------
    items_per_page = 10
    total_pages = max(1, (len(products) + items_per_page - 1) // items_per_page)
    page = st.session_state.page

    col1, _, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Previous", disabled=page <= 1):
            st.session_state.page -= 1
            st.session_state.selected_asin = None
    with col3:
        if st.button("Next", disabled=page >= total_pages):
            st.session_state.page += 1
            st.session_state.selected_asin = None

    start = (page - 1) * items_per_page
    end = min(start + items_per_page, len(products))
    st.caption(f"Showing {start + 1}–{end} of {len(products)}")

    for product in products[start:end]:
        render_product_card(product, domain_default=domain, geo_default=geo)


if __name__ == "__main__":
    main()
