from tinydb import TinyDB, Query
from datetime import datetime, timezone
from typing import Dict, List, Optional
import os


class Database:
    """
    Lightweight database wrapper for products & competitors.
    Uses TinyDB with enforced structure and upsert safety.
    """

    def __init__(self, db_path: Optional[str] = None):
        # Resolve database path safely
        base_dir = os.getenv("DATA_DIR", "data")
        os.makedirs(base_dir, exist_ok=True)

        self.db_path = db_path or os.path.join(base_dir, "products.json")
        self.db = TinyDB(self.db_path)
        self.products = self.db.table("products")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def upsert_product(self, product: Dict) -> None:
        """
        Insert or update a product by ASIN.
        """
        asin = product.get("asin")
        if not asin:
            raise ValueError("Product must contain an ASIN")

        data = dict(product)  # avoid mutating caller
        data["updated_at"] = self._now_iso()
        data.setdefault("created_at", self._now_iso())
        data.setdefault("type", "product")

        Product = Query()
        self.products.upsert(data, Product.asin == asin)

    def upsert_many(self, products: List[Dict]) -> None:
        for p in products:
            self.upsert_product(p)

    def get_product(self, asin: str) -> Optional[Dict]:
        Product = Query()
        return self.products.get(Product.asin == asin)

    def get_all_products(self) -> List[Dict]:
        return self.products.search(Query().type == "product")

    def get_competitors(self, parent_asin: str) -> List[Dict]:
        Product = Query()
        return self.products.search(
            (Product.parent_asin == parent_asin)
            & (Product.type == "competitor")
        )

    def search_products(self, criteria: Dict) -> List[Dict]:
        if not criteria:
            return []

        Product = Query()
        query = None

        for key, value in criteria.items():
            condition = Product[key] == value
            query = condition if query is None else query & condition

        return self.products.search(query)

    def delete_product(self, asin: str) -> None:
        Product = Query()
        self.products.remove(Product.asin == asin)

    def delete_competitors(self, parent_asin: str) -> None:
        Product = Query()
        self.products.remove(Product.parent_asin == parent_asin)

    def clear_all(self) -> None:
        self.products.truncate()
