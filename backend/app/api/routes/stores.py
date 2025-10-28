"""Store catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from backend.app.models import StoreListResponse, StoreSummary, Store
from backend.app.dependencies import get_db
from haversine import haversine




router = APIRouter()


class NearbyStore(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float




@router.get("/stores", response_model=StoreListResponse, summary="List supported retailers")
async def list_supported_stores() -> StoreListResponse:
    """Return a placeholder set of stores until the catalog is backed by Postgres."""

    # TODO: Replace with real database query once the ORM layer is wired.
    #we will get unique store names from the database
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

#queries the database for stores within a certain radius of the given lat/lon
#returns a list of stores with their id, name, latitude, longitude, and distance from the user
@router.get("/stores/nearby", response_model=list[NearbyStore], summary="Find nearby stores")
async def find_nearby_stores(
    userLat: float,
    userLong: float,
    radius_km: float = Query(5.0, description="Search radius in kilometers"),
    limit: int = Query(10, description="Maximum number of stores to return"),
    db: Session = Depends(get_db),
) -> list[NearbyStore]:
    """Return stores within radius_km of the given user location.

    This attempts to use PostGIS functions (ST_DWithin + ST_Distance) against the
    `stores` table. If the database or PostGIS is unavailable the function falls
    back to an in-memory demo list and a haversine filter.
    """

    # If DB is available try a spatial query using PostGIS
    try:
        radius_m = float(radius_km) * 1000.0

        sql = text(
            """
            SELECT
                external_id AS id,
                name,
                NULLIF(address, '') AS address,
                latitude,
                longitude,
                ST_Distance(
                    (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326))::geography,
                    (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))::geography
                ) AS distance_m
            FROM stores
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
              AND ST_DWithin(
                    (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326))::geography,
                    (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))::geography,
                    :radius_m
              )
            ORDER BY distance_m
            LIMIT :limit
            """
        )

        params = {"lat": float(userLat), "lon": float(userLong), "radius_m": radius_m, "limit": int(limit)}

        rows = db.exec(sql, params).all()

        results: list[NearbyStore] = []
        for r in rows:
            # r may be a SQLAlchemy Row; access by column name
            distance_km = float(r.distance_m) / 1000.0 if r.distance_m is not None else 0.0
            results.append(
                NearbyStore(
                    id=r.id,
                    name=r.name,
                    latitude=float(r.latitude) if r.latitude is not None else 0.0,
                    longitude=float(r.longitude) if r.longitude is not None else 0.0,
                    distance_km=round(distance_km, 3),
                )
            )

        return results

    except Exception:
        # Fallback to demo list when DB/PostGIS is not available or query fails
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
            StoreSummary(
                id="faraway-store",
                name="Faraway Store",
                address="789 Distant St, New York, NY",
                latitude=40.7128,
                longitude=-74.0060,
            ),
        ]

        results: list[NearbyStore] = []
        user_location = (userLat, userLong)
        for store in demo_stores:
            store_location = (store.latitude, store.longitude)
            distance = haversine(user_location, store_location)
            if distance <= radius_km:
                results.append(NearbyStore(
                    id=store.id,
                    name=store.name,
                    latitude=store.latitude,
                    longitude=store.longitude,
                    distance_km=round(distance, 3)
                ))
            if len(results) >= limit:
                break

        return sorted(results, key=lambda s: s.distance_km)[:limit]
# @router.get("/stores", response_model=StoreListResponse, summary="List supported retailers")
# async def list_supported_stores() -> StoreListResponse:
#     """Return a placeholder set of stores until the catalog is backed by Postgres."""

#     # TODO: Replace with real database query once the ORM layer is wired.
#     demo_stores = [
#         StoreSummary(
#             id="kroger-demo",
#             name="Kroger Demo Store",
#             address="123 Demo Ave, Albany, NY",
#             latitude=42.6526,
#             longitude=-73.7562,
#         ),
#         StoreSummary(
#             id="walmart-demo",
#             name="Walmart Demo Supercenter",
#             address="456 Sample Rd, Albany, NY",
#             latitude=42.6895,
#             longitude=-73.8503,
#         ),
#     ]

#     return StoreListResponse(stores=demo_stores)
