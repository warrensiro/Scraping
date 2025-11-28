import os
import requests
from dotenv import load_dotenv

load_dotenv()

OXYLABS_BASE_URL = "https://realtime.oxylabs.io/v1/queries"

def scrape_product_oxylabs(asin: str, domain: str = "ae", geo_location: str = None):
    """
    Scrapes Amazon product details via Oxylabs Realtime API.
    
    Parameters:
        asin (str): Amazon product ASIN.
        domain (str): Amazon domain, e.g., "ae", "com", "co.uk".
        geo_location (str): Country/region name if supported. Ignored if not supported.
        
    Returns:
        dict: Parsed JSON response from Oxylabs.
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")

    if not username or not password:
        raise ValueError("Oxylabs credentials not found in .env file.")

    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": domain,
        "parse": True
    }

    # Include geo_location only if provided and non-empty
    if geo_location and domain not in ["ae", "ae"] :  # add other domains without geo if needed
        payload["geo_location"] = geo_location

    response = requests.post(
        OXYLABS_BASE_URL,
        auth=(username, password),
        json=payload
    )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"API request failed: {e}\nResponse: {response.text}")
        raise

    return response.json()


# Example usage
if __name__ == "__main__":
    asin = "B01MFDIAQM"
    domain = "ae"  # Amazon UAE
    result = scrape_product_oxylabs(asin, domain)
    print(result)
