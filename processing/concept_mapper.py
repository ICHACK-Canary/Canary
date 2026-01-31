import yaml

with open("config/products.yaml") as f:
    PRODUCTS = yaml.safe_load(f)

def map_to_product(text: str):
    t = text.lower()
    for product, meta in PRODUCTS.items():
        for s in meta["synonyms"]:
            if s in t:
                return product
    return None
