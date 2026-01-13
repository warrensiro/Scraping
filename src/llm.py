import os
from typing import Optional, List

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from src.db import Database

load_dotenv()


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


def format_competitors(db: Database, parent_asin: str):
    comps = db.search_products({"parent_asin": parent_asin})
    return [
        {
            "asin": c.get("asin"),
            "title": c.get("title"),
            "price": c.get("price"),
            "currency": c.get("currency"),
            "rating": c.get("rating"),
        }
        for c in comps
    ]


def analyze_competitors(asin: str) -> str:
    db = Database()
    product = db.get_product(asin)

    if not product:
        return "Product not found in database."

    competitors = format_competitors(db, asin)
    if not competitors:
        return "No competitors found for analysis."

    parser = PydanticOutputParser(pydantic_object=AnalysisOutput)

    prompt = PromptTemplate(
        template="""
You are a market analyst.

Analyze the following Amazon product and its competitors.

Product:
- Title: {title}
- Brand: {brand}
- Price: {currency} {price}
- Rating: {rating}
- Categories: {categories}
- Domain: {domain}

Competitors (JSON):
{competitors}

{format_instructions}
""",
        input_variables=[
            "title",
            "brand",
            "price",
            "currency",
            "rating",
            "categories",
            "domain",
            "competitors",
        ],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # LCEL-style chain
    chain = prompt | llm | parser

    result = chain.invoke(
        {
            "title": product.get("title"),
            "brand": product.get("brand"),
            "price": product.get("price"),
            "currency": product.get("currency"),
            "rating": product.get("rating"),
            "categories": product.get("categories"),
            "domain": product.get("amazon_domain", "com"),
            "competitors": competitors,
        }
    )

    lines = [
        "Summary:\n" + result.summary,
        "\nPositioning:\n" + result.positioning,
        "\nTop Competitors:",
    ]

    for c in result.top_competitors[:5]:
        price = f"{c.currency} {c.price}" if c.currency else c.price
        points = "; ".join(c.key_points)
        lines.append(f"- {c.asin} | {c.title} | {price} | {c.rating} | {points}")

    if result.recommendations:
        lines.append("\nRecommendations:")
        for r in result.recommendations:
            lines.append(f"- {r}")

    return "\n".join(lines)
