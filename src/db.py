from tinydb import TinyDB, Query
from datetime import datetime
import os


class Database:
    def __init__(self, db_path="data.json"):
        dirname = os.path.dirname(db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        self.db = TinyDB(db_path)
        self.products = self.db.table("products")

    def insert_products(self, product_data):
        """Insert a product record into the database."""
        product_data["created_at"] = datetime.now().isoformat()
        return self.products.insert(product_data)

    def get_product(self, asin):
        """Get a single product by ASIN."""
        Product = Query()
        return self.products.get(Product.asin == asin)

    def get_all_products(self):
        """Return all products in the database."""
        return self.products.all()

    def search_products(self, search_criteria):
        """Search products based on criteria dictionary."""
        Product = Query()
        query = None
        for key, value in search_criteria.items():
            if query is None:
                query = Product[key] == value
            else:
                query &= Product[key] == value
        return self.products.search(query) if query else []

    def clear_all_products(self):
        """Delete all products and competitors from the database."""
        self.products.truncate()

    def delete_product(self, asin):
        """Delete a single product by ASIN."""
        Product = Query()
        return self.products.remove(Product.asin == asin)
