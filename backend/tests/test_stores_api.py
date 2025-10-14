"""Tests for store location endpoints."""

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_nearby_stores_returns_demo_store_within_radius():
    # Coordinates near the demo stores in Albany, NY
    user_lat = 42.66
    user_lon = -73.76
    resp = client.get(
        "/api/stores/nearby",
        params={"userLat": user_lat, "userLong": user_lon, "radius_km": 10, "limit": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Expect at least one demo store returned
    assert any(s["id"] == "kroger-demo" for s in data)
    assert any(s["id"] == "walmart-demo" for s in data)
    assert all(s["distance_km"] <= 10 for s in data)
    assert not any(s['id'] == 'faraway-store' for s in data)
    


def test_max_limit_enforced():
    user_lat = 42.66
    user_lon = -73.76
    resp = client.get(
        "/api/stores/nearby",
        params={"userLat": user_lat, "userLong": user_lon, "radius_km": 10, "limit": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 1 
    