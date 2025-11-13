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
