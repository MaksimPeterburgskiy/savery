#!/usr/bin/env python3
"""Seed test stores and chains near a specified location."""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text
from sqlmodel import Session

from backend.app.db import get_engine
from backend.app.models import PriceEntry, Product, Store, StoreChain, StoreProduct

# Reference point: 41.134274, -73.989650 (Tarrytown/Sleepy Hollow, NY area)
REF_LAT = 41.134274
REF_LON = -73.989650

# Test store chains
CHAINS = [
    {"name": "ShopRite"},
    {"name": "Stop & Shop"},
    {"name": "Trader Joe's"},
    {"name": "Whole Foods Market"},
    {"name": "ALDI"},
]

# Test stores within a few miles of the reference point
# Each store has slight coordinate offsets to place them nearby
STORES = [
    # ShopRite stores
    {
        "chain_name": "ShopRite",
        "name": "ShopRite of Tarrytown",
        "number": "1001",
        "address_line1": "100 Wildey St",
        "city": "Tarrytown",
        "region": "NY",
        "postal_code": "10591",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0101",
        "lat": 41.0762,
        "lon": -73.8587,
    },
    {
        "chain_name": "ShopRite",
        "name": "ShopRite of Ossining",
        "number": "1002",
        "address_line1": "230 S Highland Ave",
        "city": "Ossining",
        "region": "NY",
        "postal_code": "10562",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0102",
        "lat": 41.1548,
        "lon": -73.8615,
    },
    # Stop & Shop stores
    {
        "chain_name": "Stop & Shop",
        "name": "Stop & Shop - Elmsford",
        "number": "2001",
        "address_line1": "333 Saw Mill River Rd",
        "city": "Elmsford",
        "region": "NY",
        "postal_code": "10523",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0201",
        "lat": 41.0551,
        "lon": -73.8201,
    },
    {
        "chain_name": "Stop & Shop",
        "name": "Stop & Shop - Croton-on-Hudson",
        "number": "2002",
        "address_line1": "41 S Riverside Ave",
        "city": "Croton-on-Hudson",
        "region": "NY",
        "postal_code": "10520",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0202",
        "lat": 41.2087,
        "lon": -73.8912,
    },
    # Trader Joe's stores
    {
        "chain_name": "Trader Joe's",
        "name": "Trader Joe's - Hartsdale",
        "number": "3001",
        "address_line1": "215 N Central Ave",
        "city": "Hartsdale",
        "region": "NY",
        "postal_code": "10530",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0301",
        "lat": 41.0234,
        "lon": -73.7987,
    },
    {
        "chain_name": "Trader Joe's",
        "name": "Trader Joe's - Larchmont",
        "number": "3002",
        "address_line1": "1350 Boston Post Rd",
        "city": "Larchmont",
        "region": "NY",
        "postal_code": "10538",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0302",
        "lat": 40.9312,
        "lon": -73.7523,
    },
    # Whole Foods Market stores
    {
        "chain_name": "Whole Foods Market",
        "name": "Whole Foods Market - White Plains",
        "number": "4001",
        "address_line1": "110 Bloomingdale Rd",
        "city": "White Plains",
        "region": "NY",
        "postal_code": "10605",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0401",
        "lat": 41.0412,
        "lon": -73.7756,
    },
    {
        "chain_name": "Whole Foods Market",
        "name": "Whole Foods Market - Port Chester",
        "number": "4002",
        "address_line1": "630 W Boston Post Rd",
        "city": "Port Chester",
        "region": "NY",
        "postal_code": "10573",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0402",
        "lat": 41.0012,
        "lon": -73.6856,
    },
    # ALDI stores
    {
        "chain_name": "ALDI",
        "name": "ALDI - Yonkers",
        "number": "5001",
        "address_line1": "2500 Central Park Ave",
        "city": "Yonkers",
        "region": "NY",
        "postal_code": "10710",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0501",
        "lat": 40.9876,
        "lon": -73.8534,
    },
    {
        "chain_name": "ALDI",
        "name": "ALDI - Mount Kisco",
        "number": "5002",
        "address_line1": "195 N Bedford Rd",
        "city": "Mount Kisco",
        "region": "NY",
        "postal_code": "10549",
        "country_code": "US",
        "timezone": "America/New_York",
        "phone": "(914) 555-0502",
        "lat": 41.2134,
        "lon": -73.7234,
    },
]

# Product catalog: brand + generic variants for test items
PRODUCTS = [
    {
        "key": "baby_spinach_brand",
        "item_slug": "baby_spinach",
        "brand": "Organic Girl",
        "name": "Baby Spinach",
        "size_text": "5 oz",
        "pkg_qty_value": 5,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.25,
    },
    {
        "key": "baby_spinach_generic",
        "item_slug": "baby_spinach",
        "brand": "Marketside",
        "name": "Baby Spinach",
        "size_text": "6 oz",
        "pkg_qty_value": 6,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.0,
    },
    {
        "key": "cream_cheese_brand",
        "item_slug": "cream_cheese",
        "brand": "Philadelphia",
        "name": "Cream Cheese",
        "size_text": "8 oz",
        "pkg_qty_value": 8,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.2,
    },
    {
        "key": "cream_cheese_generic",
        "item_slug": "cream_cheese",
        "brand": "Store Brand",
        "name": "Cream Cheese",
        "size_text": "8 oz",
        "pkg_qty_value": 8,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.0,
    },
    {
        "key": "chicken_thighs_brand",
        "item_slug": "chicken_thighs",
        "brand": "Perdue",
        "name": "Chicken Thighs",
        "size_text": "1.5 lb",
        "pkg_qty_value": 1.5,
        "pkg_qty_unit": "lb",
        "brand_premium": 1.22,
    },
    {
        "key": "chicken_thighs_generic",
        "item_slug": "chicken_thighs",
        "brand": "Store Brand",
        "name": "Chicken Thighs",
        "size_text": "1 lb",
        "pkg_qty_value": 1.0,
        "pkg_qty_unit": "lb",
        "brand_premium": 1.0,
    },
    {
        "key": "cheerios_brand",
        "item_slug": "cheerios",
        "brand": "General Mills",
        "name": "Cheerios Cereal",
        "size_text": "18 oz",
        "pkg_qty_value": 18,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.18,
    },
    {
        "key": "cheerios_generic",
        "item_slug": "cheerios",
        "brand": "Store Brand",
        "name": "Toasted Oat Cereal",
        "size_text": "14 oz",
        "pkg_qty_value": 14,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.0,
    },
    {
        "key": "spaghetti_brand",
        "item_slug": "spaghetti",
        "brand": "Barilla",
        "name": "Spaghetti Pasta",
        "size_text": "16 oz",
        "pkg_qty_value": 16,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.15,
    },
    {
        "key": "spaghetti_generic",
        "item_slug": "spaghetti",
        "brand": "Store Brand",
        "name": "Spaghetti",
        "size_text": "16 oz",
        "pkg_qty_value": 16,
        "pkg_qty_unit": "oz",
        "brand_premium": 1.0,
    },
    {
        "key": "bananas_brand",
        "item_slug": "bananas",
        "brand": "Dole",
        "name": "Bananas",
        "size_text": "1 lb",
        "pkg_qty_value": 1.0,
        "pkg_qty_unit": "lb",
        "brand_premium": 1.12,
    },
    {
        "key": "bananas_generic",
        "item_slug": "bananas",
        "brand": "Organic Bananas",
        "name": "Bananas",
        "size_text": "1 lb",
        "pkg_qty_value": 1.0,
        "pkg_qty_unit": "lb",
        "brand_premium": 1.0,
    },
]

# Base prices for generic variants (before brand or chain adjustments)
ITEM_BASE_PRICES = {
    "baby_spinach": 3.29,
    "cream_cheese": 2.49,
    "chicken_thighs": 3.99,
    "cheerios": 2.79,
    "spaghetti": 1.09,
    "bananas": 0.69,
}

# Per-chain pricing multipliers (Whole Foods highest, ALDI lowest)
CHAIN_PRICE_MULTIPLIERS = {
    "Whole Foods Market": 1.25,
    "Trader Joe's": 1.05,
    "ShopRite": 1.10,
    "Stop & Shop": 1.08,
    "ALDI": 0.90,
}

# Availability map: not all stores carry every product
STORE_PRODUCT_AVAILABILITY = {
    "ShopRite": [
        "baby_spinach_brand",
        "baby_spinach_generic",
        "cream_cheese_brand",
        "cream_cheese_generic",
        "chicken_thighs_brand",
        "chicken_thighs_generic",
        "cheerios_brand",
        "cheerios_generic",
        "spaghetti_brand",
        "spaghetti_generic",
        "bananas_brand",
        "bananas_generic",
    ],
    "Stop & Shop": [
        "baby_spinach_brand",
        "baby_spinach_generic",
        "cream_cheese_brand",
        "cream_cheese_generic",
        "chicken_thighs_generic",
        "cheerios_brand",
        "cheerios_generic",
        "spaghetti_brand",
        "spaghetti_generic",
        "bananas_brand",
        "bananas_generic",
    ],
    "Trader Joe's": [
        "baby_spinach_generic",
        "cream_cheese_generic",
        "chicken_thighs_generic",
        "cheerios_brand",
        "spaghetti_generic",
        "bananas_brand",
        "bananas_generic",
    ],
    "Whole Foods Market": [
        "baby_spinach_brand",
        "cream_cheese_brand",
        "chicken_thighs_brand",
        "cheerios_brand",
        "spaghetti_brand",
        "bananas_brand",
        "bananas_generic",
    ],
    "ALDI": [
        "baby_spinach_generic",
        "cream_cheese_generic",
        "chicken_thighs_generic",
        "cheerios_generic",
        "spaghetti_generic",
        "bananas_generic",
    ],
}


def seed_stores():
    """Seed test store chains and stores into the database."""
    engine = get_engine()
    with Session(engine) as session:
        # Create chains first
        chain_map = {}
        for chain_data in CHAINS:
            # Check if chain already exists
            existing = session.query(StoreChain).filter(StoreChain.name == chain_data["name"]).first()
            if existing:
                print(f"Chain '{chain_data['name']}' already exists, skipping...")
                chain_map[chain_data["name"]] = existing
            else:
                chain = StoreChain(**chain_data)
                session.add(chain)
                session.flush()  # Get the ID
                chain_map[chain_data["name"]] = chain
                print(f"Created chain: {chain.name} (ID: {chain.id})")

        # Create stores
        for store_data in STORES:
            chain_name = store_data.pop("chain_name")
            lat = store_data.pop("lat")
            lon = store_data.pop("lon")

            # Check if store already exists by number
            existing = session.query(Store).filter(Store.number == store_data["number"]).first()
            if existing:
                print(f"Store '{store_data['name']}' already exists, skipping...")
                continue

            chain = chain_map[chain_name]
            store = Store(
                chain_id=chain.id,
                **store_data,
            )
            session.add(store)
            session.flush()

            # Update geography using raw SQL (PostGIS)
            session.execute(
                text(
                    "UPDATE stores SET geography = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography WHERE id = :id"
                ),
                {"lon": lon, "lat": lat, "id": str(store.id)},
            )
            print(f"Created store: {store.name} at ({lat}, {lon})")

        session.commit()
        print("\nSeeding complete!")


def seed_products() -> dict[str, UUID]:
    """Create brand + generic product records for test items, returning id map."""
    engine = get_engine()
    product_map: dict[str, UUID] = {}

    with Session(engine) as session:
        for product_data in PRODUCTS:
            lookup = (
                session.query(Product)
                .filter(
                    Product.brand == product_data["brand"],
                    Product.name == product_data["name"],
                    Product.size_text == product_data["size_text"],
                )
                .first()
            )
            if lookup:
                product_map[product_data["key"]] = lookup.id
                print(f"Product '{product_data['brand']} {product_data['name']} {product_data['size_text']}' exists, skipping...")
                continue

            payload = {k: v for k, v in product_data.items() if k not in {"key", "item_slug", "brand_premium"}}
            product = Product(**payload)
            session.add(product)
            session.flush()
            product_map[product_data["key"]] = product.id
            print(f"Created product: {product.brand} {product.name} ({product.size_text})")

        session.commit()

    return product_map


def seed_store_products(product_map: dict[str, UUID]) -> list[StoreProduct]:
    """Link products to stores based on availability matrix."""
    engine = get_engine()
    created_store_products: list[StoreProduct] = []

    with Session(engine) as session:
        stores = session.query(Store).join(StoreChain).all()
        for store in stores:
            if not store.chain:
                print(f"Store {store.name} missing chain association, skipping store products...")
                continue

            available_keys = STORE_PRODUCT_AVAILABILITY.get(store.chain.name, [])
            for product_key in available_keys:
                product_id = product_map.get(product_key)
                if not product_id:
                    print(f"Product key '{product_key}' missing, skipping for store {store.name}")
                    continue

                existing = (
                    session.query(StoreProduct)
                    .filter(StoreProduct.store_id == store.id, StoreProduct.product_id == product_id)
                    .first()
                )
                if existing:
                    created_store_products.append(existing)
                    continue

                external_sku = f"{store.number}-{product_key}"
                store_product = StoreProduct(
                    store_id=store.id,
                    product_id=product_id,
                    external_sku=external_sku,
                    is_active=True,
                )
                session.add(store_product)
                session.flush()
                created_store_products.append(store_product)

                # Fetch product fields for logging without triggering detach issues
                product_obj = session.get(Product, product_id)
                brand = product_obj.brand if product_obj else "Product"
                name = product_obj.name if product_obj else product_key
                print(f"Linked {brand} {name} to {store.name}")

        session.commit()

    return created_store_products


def _calculate_price(product_key: str, chain_name: str) -> tuple[float, float | None, str | None]:
    """Determine price + unit price based on chain and product metadata."""
    product_data = next((p for p in PRODUCTS if p["key"] == product_key), None)
    if not product_data:
        raise ValueError(f"No product data for key '{product_key}'")

    base_price = ITEM_BASE_PRICES[product_data["item_slug"]]
    chain_multiplier = CHAIN_PRICE_MULTIPLIERS.get(chain_name, 1.0)
    brand_multiplier = product_data.get("brand_premium", 1.0)
    price = round(base_price * brand_multiplier * chain_multiplier, 2)

    unit_price = None
    unit = product_data.get("pkg_qty_unit")
    qty = product_data.get("pkg_qty_value")
    if qty and unit:
        unit_price = round(price / qty, 4)

    return price, unit_price, unit


def seed_price_entries():
    """Create current price entries for all store products."""
    engine = get_engine()

    with Session(engine) as session:
        store_products = session.query(StoreProduct).join(Store).join(StoreChain).all()
        for store_product in store_products:
            if not store_product.store or not store_product.store.chain:
                print(f"Store product {store_product.id} missing store/chain, skipping price seed")
                continue

            if "-" not in store_product.external_sku:
                print(f"Skipping store_product {store_product.id} with unexpected SKU format")
                continue

            _, product_key = store_product.external_sku.split("-", 1)
            try:
                chain_name = store_product.store.chain.name if store_product.store and store_product.store.chain else "Unknown"
                price, unit_price, unit_price_unit = _calculate_price(product_key, chain_name)
            except ValueError as exc:
                print(exc)
                continue

            existing = (
                session.query(PriceEntry)
                .filter(PriceEntry.store_product_id == store_product.id, PriceEntry.is_current == True)  # noqa: E712
                .first()
            )

            if existing and float(existing.price) == price:
                print(f"Price for {store_product.external_sku} up-to-date (${price:.2f}), skipping...")
                continue

            if existing:
                existing.is_current = False

            price_entry = PriceEntry(
                store_product_id=store_product.id,
                price=price,
                unit_price=unit_price,
                unit_price_unit=unit_price_unit,
                source="seed_test_data",
                is_current=True,
            )
            session.add(price_entry)
            print(
                f"Set price for {store_product.store.name} / {product_key}: ${price:.2f}"
                + (f" (${unit_price:.4f} per {unit_price_unit})" if unit_price else "")
            )

        session.commit()
        print("\nPrice entries seeded.")


if __name__ == "__main__":
    seed_stores()
    products = seed_products()
    seed_store_products(products)
    seed_price_entries()
