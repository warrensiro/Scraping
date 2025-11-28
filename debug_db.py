from src.db import Database

db = Database()

print("\n=== ALL PRODUCTS IN DB ===")
try:
    for p in db.get_all_products():
        print(p)
except Exception as e:
    print("Error:", e)


asin = input("\nEnter parent ASIN to view competitors: ")

print(f"\n=== COMPETITORS FOR {asin} ===")
try:
    competitors = db.search_products({"parent_asin": asin})
    for c in competitors:
        print(c)
except Exception as e:
    print("Error searching competitors:", e)
