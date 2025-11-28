import os
from dotenv import load_dotenv
from src.db import Database
from typing import Optional, List
from pydantic import BaseModel, Field
import time
import openai

# Load environment variables
load_dotenv()
print("API Key loaded:", bool(os.getenv("OPENAI_API_KEY")))


# -------------------------
# Pydantic Models
# -------------------------
class CompetitorInsights(BaseModel):
    asin: str
    title: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    rating: Optional[float]
    key_points: List[str] = Field(default_factory=list)


class AnalysisOutput(BaseModel):
    summary: str
    positioning: str
    top_competitors: List[CompetitorInsights]
    recommendations: List[str]


# -------------------------
# Helper Functions
# -------------------------
def format_competitors(db, parent_asin):
    comps = db.search_products({"parent_asin": parent_asin})
    return [
        {
            "asin": c["asin"],
            "title": c["title"],
            "price": c["price"],
            "currency": c.get("currency"),
            "rating": c["rating"],
            "amazon_domain": c.get("amazon_domain"),
        }
        for c in comps
    ]


# -------------------------
# Main Analysis Function
# -------------------------
def analyze_competitors(asin):
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.chains import LLMChain
    from openai.error import RateLimitError

    db = Database()
    product = db.get_product(asin)
    competitors = format_competitors(db, asin)

    parser = PydanticOutputParser(pydantic_object=AnalysisOutput)

    template = (
        "You are a market analyst. Given a product and its competitor list, "
        "write a concise analysis. Pay attention to currency and pricing context.\n\n"
        "Product Title: {product_title}\n"
        "Brand: {brand}\n"
        "Price: {currency} {price}\n"
        "Rating: {rating}\n"
        "Categories: {categories}\n"
        "Amazon Domain: {amazon_domain}\n\n"
        "Competitors (JSON): {competitors}\n\n"
        "IMPORTANT: All prices should be displayed with their correct currency symbol. "
        "When comparing prices, ensure you're using the same currency context.\n\n"
        "{format_instructions}"
    )

    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "product_title",
            "brand",
            "price",
            "rating",
            "categories",
            "amazon_domain",
            "competitors",
        ],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    # Function to create chain with a given model
    def create_chain(model_name):
        llm = ChatOpenAI(
            model=model_name, temperature=0, api_key=os.getenv("OPENAI_API_KEY")
        )
        return LLMChain(llm=llm, prompt=prompt, output_parser=parser)

    # Try GPT-4o-mini first, fallback to GPT-3.5-turbo
    for model_name in ["gpt-4o-mini", "gpt-3.5-turbo"]:
        try:
            chain = create_chain(model_name)
            result = chain.invoke(
                {
                    "product_title": product["title"] if product else asin,
                    "brand": product.get("brand") if product else None,
                    "price": product.get("price") if product else None,
                    "currency": product.get("currency") if product else "",
                    "rating": product.get("rating") if product else None,
                    "categories": product.get("categories") if product else None,
                    "amazon_domain": product.get("amazon_domain") if product else "com",
                    "competitors": competitors,
                }
            )
            print(f"✅ Analysis done using {model_name}")
            break  # success, exit loop
        except RateLimitError:
            print(f"⚠ {model_name} quota exceeded, trying fallback...")
            time.sleep(1)
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
            raise e
    else:
        raise RuntimeError("All LLM models failed. Check API key and quota.")

    # Format the result as readable output
    lines = [
        "Summary:\n" + result.summary,
        "\nPositioning:\n" + result.positioning,
        "\nCompetitors:",
    ]
    for c in result.top_competitors[:5]:
        pts = "; ".join(c.key_points) if c.key_points else ""
        currency = c.currency if c.currency else ""
        price_str = f"{currency} {c.price}" if currency else f"${c.price}"
        lines.append(f"- {c.asin} | {c.title} | {price_str} | {c.rating} | {pts}")

    if result.recommendations:
        lines.append("\nRecommendations:")
        for r in result.recommendations:
            lines.append(f"- {r}")

    return "\n".join(lines)
