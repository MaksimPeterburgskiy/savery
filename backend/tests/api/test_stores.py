"""Integration tests for the store API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2 import WKTElement
from sqlmodel import select

from backend.app.db import session_scope
from backend.app.main import create_app
from backend.app.models import Store, StoreChain


@pytest.fixture()
def client() -> TestClient:
    """Provide a FastAPI test client for the store routes."""

    with TestClient(create_app()) as test_client:
        yield test_client


def cleanup_store_chain(chain_id: UUID) -> None:
    """Remove a store chain and any associated stores from the database."""

    with session_scope() as session:
        stores = session.exec(select(Store).where(Store.chain_id == chain_id)).all()
        for store in stores:
            session.delete(store)

        chain = session.exec(select(StoreChain).where(StoreChain.id == chain_id)).first()
        if chain:
            session.delete(chain)


def test_get_store_chains_returns_created_chains(client: TestClient) -> None:
    created_chains: dict[UUID, str] = {}

    try:
        with session_scope() as session:
            for _ in range(2):
                chain = StoreChain(name=f"Store Chain {uuid4()}")
                session.add(chain)
                session.flush()
                created_chains[chain.id] = chain.name

        response = client.get("/api/store-chains")

        assert response.status_code == 200
        payload = response.json()
        returned = {UUID(entry["id"]): entry["name"] for entry in payload}

        for chain_id, chain_name in created_chains.items():
            assert chain_id in returned
            assert returned[chain_id] == chain_name
    finally:
        for chain_id in created_chains:
            cleanup_store_chain(chain_id)


def test_get_stores_by_store_chain_returns_expected_stores(client: TestClient) -> None:
    chain_id: UUID | None = None
    created_stores: dict[UUID, tuple[str, float, float]] = {}

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Chain-{uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            store_specs = [
                {
                    "name": "Downtown Test Store",
                    "number": "001",
                    "address_line1": "1 Main St",
                    "city": "Testville",
                    "region": "TS",
                    "postal_code": "12345",
                    "country_code": "US",
                    "timezone": "America/New_York",
                    "phone": "555-0101",
                    "longitude": -73.691,
                    "latitude": 42.731,
                },
                {
                    "name": "Uptown Test Store",
                    "number": "002",
                    "address_line1": "200 River St",
                    "city": "Testville",
                    "region": "TS",
                    "postal_code": "12345",
                    "country_code": "US",
                    "timezone": "America/New_York",
                    "phone": "555-0202",
                    "longitude": -73.661,
                    "latitude": 42.761,
                },
            ]

            for spec in store_specs:
                store = Store(
                    chain_id=chain_id,
                    name=spec["name"],
                    number=spec["number"],
                    address_line1=spec["address_line1"],
                    city=spec["city"],
                    region=spec["region"],
                    postal_code=spec["postal_code"],
                    country_code=spec["country_code"],
                    timezone=spec["timezone"],
                    phone=spec["phone"],
                    geography=WKTElement(
                        f"POINT({spec['longitude']} {spec['latitude']})", srid=4326
                    ),
                )
                session.add(store)
                session.flush()
                created_stores[store.id] = (spec["name"], spec["longitude"], spec["latitude"])

        response = client.get(f"/api/store-chains/{chain_id}/stores")

        assert response.status_code == 200
        payload = response.json()
        returned_ids = {UUID(entry["id"]) for entry in payload}
        assert returned_ids == set(created_stores.keys())

        for entry in payload:
            store_id = UUID(entry["id"])
            expected_name, expected_lon, expected_lat = created_stores[store_id]
            assert entry["chain_id"] == str(chain_id)
            assert entry["name"] == expected_name
            assert entry["longitude"] == pytest.approx(expected_lon)
            assert entry["latitude"] == pytest.approx(expected_lat)
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_get_nearby_store_chains_returns_chains_within_radius(client: TestClient) -> None:
    reference_lat = 42.7309
    reference_lon = -73.6916
    near_chain_id: UUID | None = None
    far_chain_id: UUID | None = None
    near_store_name = "Nearby Test Store"
    near_store_id: UUID | None = None

    try:
        with session_scope() as session:
            near_chain = StoreChain(name=f"Near Chain {uuid4()}")
            session.add(near_chain)
            session.flush()
            near_chain_id = near_chain.id

            near_store = Store(
                chain_id=near_chain_id,
                name=near_store_name,
                number="100",
                address_line1="100 Nearby St",
                city="Troy",
                region="NY",
                postal_code="12180",
                country_code="US",
                timezone="America/New_York",
                phone="555-0303",
                geography=WKTElement(f"POINT({reference_lon} {reference_lat})", srid=4326),
            )
            session.add(near_store)
            session.flush()
            near_store_id = near_store.id

            far_chain = StoreChain(name=f"Far Chain {uuid4()}")
            session.add(far_chain)
            session.flush()
            far_chain_id = far_chain.id

            far_store = Store(
                chain_id=far_chain_id,
                name="Far Test Store",
                number="200",
                address_line1="500 Distant Rd",
                city="Albany",
                region="NY",
                postal_code="12207",
                country_code="US",
                timezone="America/New_York",
                phone="555-0404",
                geography=WKTElement(
                    f"POINT({reference_lon} {reference_lat + 1.0})", srid=4326
                ),
            )
            session.add(far_store)

        response = client.get(
            "/api/store-chains/nearby",
            params={
                "latitude": reference_lat,
                "longitude": reference_lon,
                "distance_km": 10.0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        returned_chain_ids = {UUID(entry["id"]) for entry in payload}
        assert near_chain_id in returned_chain_ids
        assert far_chain_id not in returned_chain_ids

        near_entry = next(entry for entry in payload if entry["id"] == str(near_chain_id))
        returned_store_ids = {UUID(store["id"]) for store in near_entry["stores"]}
        assert returned_store_ids == {near_store_id}

        store_payload = near_entry["stores"][0]
        assert store_payload["name"] == near_store_name
        assert store_payload["longitude"] == pytest.approx(reference_lon)
        assert store_payload["latitude"] == pytest.approx(reference_lat)
    finally:
        if near_chain_id:
            cleanup_store_chain(near_chain_id)
        if far_chain_id:
            cleanup_store_chain(far_chain_id)


# ---- /stores/search tests ----


def test_search_stores_by_store_name(client: TestClient) -> None:
    """Test that searching by store name returns expected stores."""
    chain_id: UUID | None = None
    store_name = f"Unique Store Name {uuid4()}"

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            store = Store(
                chain_id=chain_id,
                name=store_name,
                number="001",
                address_line1="123 Test St",
                city="TestCity",
                region="TC",
                postal_code="11111",
                country_code="US",
                timezone="America/New_York",
                phone="555-0001",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store)
            session.flush()
            store_id = store.id

        response = client.get("/api/stores/search", params={"q": "Unique Store Name"})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 1
        store_ids = {UUID(entry["id"]) for entry in payload}
        assert store_id in store_ids

        matched_store = next(s for s in payload if s["id"] == str(store_id))
        assert matched_store["name"] == store_name
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_by_address(client: TestClient) -> None:
    """Test that searching by address fields returns expected stores."""
    chain_id: UUID | None = None
    unique_address = f"999 Unique Address {uuid4()}"

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            store = Store(
                chain_id=chain_id,
                name="Generic Store",
                number="002",
                address_line1=unique_address,
                city="AddressCity",
                region="AC",
                postal_code="22222",
                country_code="US",
                timezone="America/New_York",
                phone="555-0002",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store)
            session.flush()
            store_id = store.id

        response = client.get("/api/stores/search", params={"q": "999 Unique Address"})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 1
        store_ids = {UUID(entry["id"]) for entry in payload}
        assert store_id in store_ids
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_by_chain_name(client: TestClient) -> None:
    """Test that searching by chain name returns stores from that chain."""
    chain_name = f"Unique Chain Name {uuid4()}"
    chain_id: UUID | None = None

    try:
        with session_scope() as session:
            chain = StoreChain(name=chain_name)
            session.add(chain)
            session.flush()
            chain_id = chain.id

            store = Store(
                chain_id=chain_id,
                name="Store Under Unique Chain",
                number="003",
                address_line1="456 Chain St",
                city="ChainCity",
                region="CC",
                postal_code="33333",
                country_code="US",
                timezone="America/New_York",
                phone="555-0003",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store)
            session.flush()
            store_id = store.id

        response = client.get("/api/stores/search", params={"q": "Unique Chain Name"})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 1
        store_ids = {UUID(entry["id"]) for entry in payload}
        assert store_id in store_ids
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_by_city(client: TestClient) -> None:
    """Test that searching by city returns expected stores."""
    unique_city = f"UniqueCity{uuid4().hex[:8]}"
    chain_id: UUID | None = None

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            store = Store(
                chain_id=chain_id,
                name="City Test Store",
                number="004",
                address_line1="789 City St",
                city=unique_city,
                region="CT",
                postal_code="44444",
                country_code="US",
                timezone="America/New_York",
                phone="555-0004",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store)
            session.flush()
            store_id = store.id

        response = client.get("/api/stores/search", params={"q": unique_city})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 1
        store_ids = {UUID(entry["id"]) for entry in payload}
        assert store_id in store_ids
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_with_distance_filter(client: TestClient) -> None:
    """Test that distance filtering excludes stores outside the radius."""
    reference_lat = 42.7309
    reference_lon = -73.6916
    near_chain_id: UUID | None = None
    far_chain_id: UUID | None = None
    near_store_name = f"Near Search Store {uuid4()}"
    far_store_name = f"Far Search Store {uuid4()}"

    try:
        with session_scope() as session:
            # Create a store chain and store very close to the reference point
            near_chain = StoreChain(name=f"Near Search Chain {uuid4()}")
            session.add(near_chain)
            session.flush()
            near_chain_id = near_chain.id

            near_store = Store(
                chain_id=near_chain_id,
                name=near_store_name,
                number="100",
                address_line1="100 Nearby St",
                city="Troy",
                region="NY",
                postal_code="12180",
                country_code="US",
                timezone="America/New_York",
                phone="555-1001",
                geography=WKTElement(f"POINT({reference_lon} {reference_lat})", srid=4326),
            )
            session.add(near_store)
            session.flush()
            near_store_id = near_store.id

            # Create a chain and store far away (about 111 km north)
            far_chain = StoreChain(name=f"Far Search Chain {uuid4()}")
            session.add(far_chain)
            session.flush()
            far_chain_id = far_chain.id

            far_store = Store(
                chain_id=far_chain_id,
                name=far_store_name,
                number="200",
                address_line1="500 Distant Rd",
                city="Albany",
                region="NY",
                postal_code="12207",
                country_code="US",
                timezone="America/New_York",
                phone="555-1002",
                geography=WKTElement(f"POINT({reference_lon} {reference_lat + 1.0})", srid=4326),
            )
            session.add(far_store)
            session.flush()
            far_store_id = far_store.id

        # Search for "Search Store" with a small radius - should only find the near one
        response = client.get(
            "/api/stores/search",
            params={
                "q": "Search Store",
                "latitude": reference_lat,
                "longitude": reference_lon,
                "distance_km": 10.0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        returned_ids = {UUID(entry["id"]) for entry in payload}
        assert near_store_id in returned_ids
        assert far_store_id not in returned_ids
    finally:
        if near_chain_id:
            cleanup_store_chain(near_chain_id)
        if far_chain_id:
            cleanup_store_chain(far_chain_id)


def test_search_stores_without_location_orders_by_name(client: TestClient) -> None:
    """Test that without location params, results are ordered alphabetically by name."""
    chain_id: UUID | None = None
    unique_prefix = f"OrderTest{uuid4().hex[:6]}"
    store_a_name = f"{unique_prefix}_A_Store"
    store_b_name = f"{unique_prefix}_B_Store"

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            # Create store B first so insertion order differs from name order
            store_b = Store(
                chain_id=chain_id,
                name=store_b_name,
                number="006",
                address_line1="200 Order St",
                city="OrderCity",
                region="OC",
                postal_code="66666",
                country_code="US",
                timezone="America/New_York",
                phone="555-0006",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store_b)

            store_a = Store(
                chain_id=chain_id,
                name=store_a_name,
                number="005",
                address_line1="100 Order St",
                city="OrderCity",
                region="OC",
                postal_code="55555",
                country_code="US",
                timezone="America/New_York",
                phone="555-0005",
                geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
            )
            session.add(store_a)

        response = client.get("/api/stores/search", params={"q": unique_prefix})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 2

        # Filter to only our test stores and verify ordering
        our_stores = [s for s in payload if s["name"].startswith(unique_prefix)]
        assert len(our_stores) == 2
        assert our_stores[0]["name"] == store_a_name  # A should come before B
        assert our_stores[1]["name"] == store_b_name
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_respects_limit(client: TestClient) -> None:
    """Test that the limit parameter caps results."""
    chain_id: UUID | None = None
    unique_prefix = f"LimitTest{uuid4().hex[:6]}"

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            # Create 5 stores
            for i in range(5):
                store = Store(
                    chain_id=chain_id,
                    name=f"{unique_prefix}_Store_{i}",
                    number=f"00{i}",
                    address_line1=f"{i}00 Limit St",
                    city="LimitCity",
                    region="LC",
                    postal_code=f"{i}0000",
                    country_code="US",
                    timezone="America/New_York",
                    phone=f"555-{i}000",
                    geography=WKTElement("POINT(-73.691 42.731)", srid=4326),
                )
                session.add(store)

        response = client.get("/api/stores/search", params={"q": unique_prefix, "limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 3
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)


def test_search_stores_with_location_orders_by_distance(client: TestClient) -> None:
    """Test that with location params, results are ordered by distance."""
    chain_id: UUID | None = None
    reference_lat = 42.7309
    reference_lon = -73.6916
    unique_prefix = f"DistOrder{uuid4().hex[:6]}"

    try:
        with session_scope() as session:
            chain = StoreChain(name=f"Test Chain {uuid4()}")
            session.add(chain)
            session.flush()
            chain_id = chain.id

            # Create far store first
            far_store = Store(
                chain_id=chain_id,
                name=f"{unique_prefix}_Far",
                number="010",
                address_line1="300 Far St",
                city="FarCity",
                region="FC",
                postal_code="77777",
                country_code="US",
                timezone="America/New_York",
                phone="555-0010",
                # About 0.5 degree north (~55 km)
                geography=WKTElement(f"POINT({reference_lon} {reference_lat + 0.5})", srid=4326),
            )
            session.add(far_store)

            # Create near store second
            near_store = Store(
                chain_id=chain_id,
                name=f"{unique_prefix}_Near",
                number="009",
                address_line1="200 Near St",
                city="NearCity",
                region="NC",
                postal_code="88888",
                country_code="US",
                timezone="America/New_York",
                phone="555-0009",
                # Very close to reference
                geography=WKTElement(f"POINT({reference_lon} {reference_lat})", srid=4326),
            )
            session.add(near_store)

        response = client.get(
            "/api/stores/search",
            params={
                "q": unique_prefix,
                "latitude": reference_lat,
                "longitude": reference_lon,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        our_stores = [s for s in payload if s["name"].startswith(unique_prefix)]
        assert len(our_stores) == 2
        # Near should come first when ordered by distance
        assert our_stores[0]["name"] == f"{unique_prefix}_Near"
        assert our_stores[1]["name"] == f"{unique_prefix}_Far"
    finally:
        if chain_id:
            cleanup_store_chain(chain_id)
