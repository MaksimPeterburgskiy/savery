"""Store catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.models import StoreListResponse, StoreSummary

router = APIRouter()


@router.get("/stores", response_model=StoreListResponse, summary="List supported retailers")
async def list_supported_stores() -> StoreListResponse:
    """Return a placeholder set of stores until the catalog is backed by Postgres."""

    # TODO: Replace with real database query once the ORM layer is wired.
    demo_stores = [
        StoreSummary(
            id="kroger-demo",
            name="Kroger Demo Store",
            address="123 Demo Ave, Albany, NY",
            latitude=42.6526,
            longitude=-73.7562,
        ),
        StoreSummary(
            id="walmart-demo",
            name="Walmart Demo Supercenter",
            address="456 Sample Rd, Albany, NY",
            latitude=42.6895,
            longitude=-73.8503,
        ),
    ]

    return StoreListResponse(stores=demo_stores)
