"""Catalog (store) HTTP endpoints."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_
from sqlmodel import Session, select

from backend.app.dependencies import get_db
from backend.app.models import Store, StoreChain

from .catalog_schemas import StoreChainsWithStoresResponse, StoreResponse

router = APIRouter()


@router.get(
    "/store-chains",
    response_model=Sequence[StoreChain],
    status_code=status.HTTP_200_OK,
    summary="Get all store chains",
)
def get_store_chains(session: Session = Depends(get_db)) -> Sequence[StoreChain]:
    """Return all store chains."""
    statement = select(StoreChain)
    results = session.exec(statement).all()
    return results


@router.get(
    "/store-chains/{store_chain_id}/stores",
    response_model=Sequence[StoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Get stores by store chain",
)
def get_stores_by_store_chain(store_chain_id: UUID, session: Session = Depends(get_db)) -> Sequence[StoreResponse]:
    """Return all stores for a given store chain."""

    statement = select(
        Store,
        func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
    ).where(Store.chain_id == store_chain_id)
    results = session.exec(statement).all()
    return [StoreResponse.from_model(store, geojson) for store, geojson in results]


@router.get(
    "/store-chains/nearby",
    response_model=Sequence[StoreChainsWithStoresResponse],
    status_code=status.HTTP_200_OK,
    summary="Get store chains by driving distance from location",
)
def get_nearby_store_chains(
    latitude: float = Query(..., description="Latitude of the reference point."),
    longitude: float = Query(..., description="Longitude of the reference point."),
    distance_km: float = Query(..., gt=0, description="Search radius in kilometers."),
    session: Session = Depends(get_db),
) -> Sequence[StoreChainsWithStoresResponse]:
    """Return all store chains within a certain driving distance from a location."""
    search_radius_m = distance_km * 1000.0
    reference_point = cast(
        func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )

    statement = (
        select(
            Store,
            StoreChain,
            func.ST_Distance(Store.geography, reference_point).label("distance"),
            func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
        )
        .join(StoreChain, Store.chain_id == StoreChain.id)
        .where(
            Store.geography.isnot(None),
            func.ST_DWithin(Store.geography, reference_point, search_radius_m),
        )
        .order_by("distance")
    )

    chain_map: dict[UUID, StoreChainsWithStoresResponse] = {}
    for store, chain, _, geojson in session.exec(statement):
        chain_payload = chain_map.setdefault(chain.id, StoreChainsWithStoresResponse(id=chain.id, name=chain.name))
        chain_payload.stores.append(StoreResponse.from_model(store, geojson))

    return list(chain_map.values())


@router.get(
    "/stores/search",
    response_model=Sequence[StoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Search for stores by name or address",
)
def search_stores(
    q: str = Query(..., min_length=1, description="Search query (store name, chain name, address, city, or postal code)."),
    latitude: float | None = Query(default=None, description="Latitude for distance filtering and ordering."),
    longitude: float | None = Query(default=None, description="Longitude for distance filtering and ordering."),
    distance_km: float | None = Query(default=None, gt=0, description="Search radius in kilometers (requires latitude and longitude)."),
    limit: int = Query(default=25, ge=1, le=100, description="Maximum number of results to return."),
    session: Session = Depends(get_db),
) -> Sequence[StoreResponse]:
    """
    Search stores by name, chain name, address, city, or postal code.

    When latitude and longitude are provided, results can be filtered by distance
    and are ordered by proximity. Otherwise, results are ordered by store name.
    """
    q_ilike = f"%{q.strip()}%"

    # Base query with geography GeoJSON for response mapping
    statement = (
        select(
            Store,
            func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
        )
        .outerjoin(StoreChain, Store.chain_id == StoreChain.id)
        .where(
            or_(
                Store.name.ilike(q_ilike),
                Store.address_line1.ilike(q_ilike),
                Store.city.ilike(q_ilike),
                Store.postal_code.ilike(q_ilike),
                StoreChain.name.ilike(q_ilike),
            )
        )
    )

    # Apply distance filtering and ordering when location is provided
    if latitude is not None and longitude is not None:
        reference_point = cast(
            func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
            Geography(geometry_type="POINT", srid=4326),
        )

        if distance_km is not None:
            search_radius_m = distance_km * 1000.0
            statement = statement.where(
                Store.geography.isnot(None),
                func.ST_DWithin(Store.geography, reference_point, search_radius_m),
            )

        # Order by distance when location is provided
        statement = statement.order_by(func.ST_Distance(Store.geography, reference_point))
    else:
        # Order alphabetically by store name when no location is provided
        statement = statement.order_by(Store.name)

    statement = statement.limit(limit)

    results = session.exec(statement).all()
    return [StoreResponse.from_model(store, geojson) for store, geojson in results]


__all__ = ["router"]
