import streamlit as st
import pandas as pd
from src.services import (
    scrape_and_store_product,
    fetch_and_store_competitors,
    clear_all_products,
)
from src.db import Database
from src.llm import analyze_competitors
import traceback

# ------------------------------
# Header & Inputs
# ------------------------------
def render_header():
    st.title("Amazon Competitor Analysis")
    st.caption("Enter your ASIN to get product insights.")


def render_inputs():
    st.sidebar.header("Product Inputs")
    asin = st.sidebar.text_input("ASIN", placeholder="e.g., B0CX23VSAS")
    geo = st.sidebar.text_input("Zip/Postal Code", placeholder="e.g., 83980")
    domain = st.sidebar.selectbox(
        "Domain", ["com", "ca", "co.uk", "de", "fr", "it", "ae"]
    )
    return asin.strip(), geo.strip(), domain


# ------------------------------
# Product Card & Competitor Display
# ------------------------------
def render_product_card(product, domain_default, geo_default):
    with st.container():
        cols = st.columns([1, 2])

        # Image
        images = product.get("images", [])
        if images:
            cols[0].image(images[0], width=200)
        else:
            cols[0].write("No image found")

        # Info
        with cols[1]:
            st.subheader(product.get("title") or product["asin"])
            info_cols = st.columns(3)
            currency = product.get("currency", "")
            price = product.get("price", "-")
            info_cols[0].metric("Price", f"{currency} {price}" if currency else price)
            info_cols[1].write(f"Brand: {product.get('brand', '-')}")

            domain_info = f"amazon.{product.get('amazon_domain', domain_default)}"
            geo_info = product.get("geo_location", geo_default or "-")
            st.caption(f"Domain: {domain_info} | Geo Location: {geo_info}")
            st.write(product.get("url", ""))

            # ------------------------------
            # Fetch Competitors Button
            # ------------------------------
            analyze_key = f"analyze_{product['asin']}"
            if st.button("Show Competitors", key=analyze_key):
                st.session_state["analyzing_asin"] = product["asin"]

                db = Database()
                existing_comps = db.search_products({"parent_asin": product["asin"]})

                if not existing_comps:
                    with st.spinner("Fetching competitors..."):
                        comps = fetch_and_store_competitors(
                            product["asin"], domain_info.split(".")[1], geo_info
                        )
                    st.success(f"Found {len(comps)} competitors!")
                else:
                    comps = existing_comps
                    st.info(f"Found {len(comps)} existing competitors in the database.")

                if comps:
                    # Limit competitors for LLM if too many
                    llm_competitors = comps[:10]

                    # Competitor DataFrame
                    df = pd.DataFrame(comps)
                    df["price"] = pd.to_numeric(df["price"], errors="coerce")

                    # Price/Rating Summary
                    st.markdown("**Competitor Summary**")
                    st.write(f"Average Price: {df['price'].mean():.2f}")
                    st.write(f"Lowest Price: {df['price'].min():.2f}")
                    st.write(f"Highest Price: {df['price'].max():.2f}")
                    if "rating" in df.columns:
                        st.write(f"Average Rating: {df['rating'].mean():.2f}")

                    # Export CSV
                    st.download_button(
                        "Download Competitors CSV",
                        df.to_csv(index=False),
                        "competitors.csv",
                    )

                    # Price Chart
                    st.markdown("**Price Distribution**")
                    chart_df = df[["title", "price"]].dropna()
                    chart_df = chart_df.sort_values("price", ascending=False)
                    st.bar_chart(chart_df.set_index("title"))

                    # Collapsible Competitor List
                    with st.expander("Show Competitors List"):
                        for c in comps:
                            price_str = f"{c.get('currency','')} {c.get('price','-')}"
                            st.write(
                                f"- {c.get('asin')} | {c.get('title')} | {price_str}"
                            )

                    # ------------------------------
                    # LLM Analysis Button
                    # ------------------------------
                    llm_key = f"llm_{product['asin']}"
                    if st.button("Analyze Product with LLM", key=llm_key):
                        with st.spinner("Analyzing product and competitors..."):
                            try:
                                analysis_text = analyze_competitors(product["asin"])
                                st.markdown("**LLM Analysis**")
                                st.text(analysis_text)
                            except Exception as e:
                                st.error("LLM analysis failed. See console for details.")
                                print(traceback.format_exc())

                else:
                    st.write("No competitors found.")


# ------------------------------
# Main App
# ------------------------------
def main():
    st.set_page_config(
        page_title="Amazon Competitor Analysis", layout="wide"
    )
    render_header()
    asin, geo, domain = render_inputs()

    # Scrape Product
    if st.sidebar.button("Scrape Product") and asin:
        with st.spinner("Scraping product..."):
            scrape_and_store_product(asin, geo, domain)
        st.success("Product scraped successfully!")

    # Clear Products
    if st.sidebar.button("Clear All Products"):
        clear_all_products()
        st.success("All products cleared!")

    # Display Products
    db = Database()
    products = db.get_all_products()
    if products:
        st.divider()
        st.subheader("Products Scraped")

        items_per_page = 10
        total_pages = (len(products) + items_per_page - 1) // items_per_page
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1) - 1

        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(products))
        st.write(f"Showing {start_idx + 1} - {end_idx} of {len(products)} products")

        for p in products[start_idx:end_idx]:
            render_product_card(p, domain_default=domain, geo_default=geo)


if __name__ == "__main__":
    main()
