import streamlit as st
import pandas as pd
import traceback

from src.services import (
    scrape_and_store_product,
    fetch_and_store_competitors,
    clear_all_products,
)
from src.db import Database
from src.llm import analyze_competitors


@st.cache_resource
def get_db():
    return Database()


@st.cache_data(ttl=60)
def get_products():
    db = get_db()
    return db.get_all_products()


@st.cache_data(ttl=3600)
def cached_llm_analysis(asin):
    return analyze_competitors(asin)


def render_header():
    st.title("Amazon Competitor Analysis")
    st.caption("Enter your ASIN to get product insights.")


def render_inputs():
    st.sidebar.header("Product Inputs")

    asin = st.sidebar.text_input("ASIN", placeholder="e.g., B0CX23VSAS")
    geo = st.sidebar.text_input("Zip / Postal Code", placeholder="e.g., 83980")
    domain = st.sidebar.selectbox(
        "Domain", ["com", "ca", "co", "uk", "de", "fr", "it", "ke", "ae"]
    )

    scrape_disabled = not asin.strip()

    if st.sidebar.button("Scrape Product", disabled=scrape_disabled):
        with st.spinner("Scraping product..."):
            try:
                scrape_and_store_product(asin.strip(), geo.strip(), domain)
                st.success("Product scraped successfully!")
                st.cache_data.clear()
            except Exception:
                st.error("Scraping failed. Check logs.")
                print(traceback.format_exc())

    if st.sidebar.button("Clear All Products"):
        clear_all_products()
        st.cache_data.clear()
        st.success("All products cleared!")

    return asin.strip(), geo.strip(), domain


def render_product_card(product, domain_default, geo_default):
    asin = product.get("asin", "Unknown ASIN")
    title = product.get("title", asin)
    images = product.get("images") or []
    price = product.get("price", "-")
    currency = product.get("currency", "")
    brand = product.get("brand", "-")
    url = product.get("url", "")

    domain_info = f"amazon.{product.get('amazon_domain', domain_default)}"
    geo_info = product.get("geo_location", geo_default or "-")

    with st.container():
        cols = st.columns([1, 2])

        if images:
            cols[0].image(images[0], width=180)
        else:
            cols[0].write("No image")

        with cols[1]:
            st.subheader(title[:80])
            info_cols = st.columns(3)

            info_cols[0].metric(
                "Price",
                f"{currency} {price}" if currency else price,
            )
            info_cols[1].write(f"Brand: {brand}")

            st.caption(f"Domain: {domain_info} | Geo: {geo_info}")
            if url:
                st.markdown(f"[View on Amazon]({url})")

            analyze_key = f"show_{asin}"
            if st.button("Show Competitors", key=analyze_key):
                st.session_state.selected_asin = asin

    if st.session_state.get("selected_asin") != asin:
        return

    db = get_db()
    existing_comps = db.search_products({"parent_asin": asin})

    if not existing_comps:
        with st.spinner("Fetching competitors..."):
            try:
                comps = fetch_and_store_competitors(
                    asin,
                    domain_info.split(".")[1],
                    geo_info,
                )
            except Exception:
                st.error("Failed to fetch competitors.")
                print(traceback.format_exc())
                return
    else:
        comps = existing_comps
        st.info(f"Loaded {len(comps)} competitors from database.")

    if not comps:
        st.warning("No competitors found.")
        return

    df = pd.DataFrame(comps)
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    else:
        df["price"] = None

    st.markdown("Competitor Summary")
    st.write(f"Average Price: {df['price'].mean():.2f}")
    st.write(f"Lowest Price: {df['price'].min():.2f}")
    st.write(f"Highest Price: {df['price'].max():.2f}")

    if "rating" in df.columns:
        st.write(f"Average Rating: {df['rating'].mean():.2f}")

    st.download_button(
        "Download Competitors CSV",
        df.to_csv(index=False),
        "competitors.csv",
    )

    st.markdown("Price Distribution")
    chart_df = df[["title", "price"]].dropna().sort_values("price", ascending=False)
    st.bar_chart(chart_df.set_index("title"))

    with st.expander("Show Competitor List"):
        for c in comps:
            st.write(
                f"- {c.get('asin')} | {c.get('title')} | {c.get('currency', '')} {c.get('price', '-')}"
            )

    if not comps:
        st.warning("No competitors available for LLM analysis.")
        return

    llm_key = f"llm_{asin}"
    if st.button("Analyze Product with LLM", key=llm_key):
        with st.spinner("Analyzing with LLM..."):
            try:
                analysis_text = cached_llm_analysis(asin)
                st.markdown("### LLM Analysis")
                st.text(analysis_text)
            except Exception:
                st.error("LLM analysis failed.")
                print(traceback.format_exc())


def main():
    st.set_page_config(
        page_title="Amazon Competitor Analysis",
        layout="wide",
    )

    if "selected_asin" not in st.session_state:
        st.session_state.selected_asin = None

    if "page" not in st.session_state:
        st.session_state.page = 1

    render_header()
    asin, geo, domain = render_inputs()

    products = get_products()
    if not products:
        st.info("No products scraped yet.")
        return

    st.divider()
    st.subheader("Products Scraped")

    items_per_page = 10
    total_pages = max(1, (len(products) + items_per_page - 1) // items_per_page)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Previous", disabled=st.session_state.page <= 1):
            st.session_state.page -= 1
            st.session_state.selected_asin = None
    with col3:
        if st.button("Next", disabled=st.session_state.page >= total_pages):
            st.session_state.page += 1
            st.session_state.selected_asin = None

    page = st.session_state.page
    start = (page - 1) * items_per_page
    end = min(start + items_per_page, len(products))

    st.caption(f"Showing {start + 1} to {end} of {len(products)}")

    for p in products[start:end]:
        render_product_card(p, domain_default=domain, geo_default=geo)


if __name__ == "__main__":
    main()
