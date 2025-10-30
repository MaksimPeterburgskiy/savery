"""Store endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlmodel import Session, select
from pydantic import BaseModel, ConfigDict, Field

from backend.app.dependencies import get_db
from backend.app.models import Store, StoreChain

router = APIRouter()


class StoreResponse(BaseModel):
    """API response payload for a single store."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chain_id: UUID | None
    name: str
    number: str
    address_line1: str
    address_line2: str | None = None
    city: str
    region: str
    postal_code: str
    country_code: str
    timezone: str
    phone: str
    external_ref: dict | None = None
    hours_json: dict | None = None
    longitude: float | None = None
    latitude: float | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, store: Store, geography_geojson: str | None) -> "StoreResponse":
        """Instantiate a response object from a SQLModel store instance."""

        base_data = store.model_dump(
            exclude={
                "geography",
                "chain",
                "store_products",
                "plan_selected",
                "store_visits",
                "item_matches",
            }
        )
        coords = _extract_point_coordinates(geography_geojson)
        if coords is not None:
            base_data.update({"longitude": coords[0], "latitude": coords[1]})

        return cls(**base_data)


def _extract_point_coordinates(geojson_text: str | None) -> tuple[float, float] | None:
    """Return longitude/latitude tuple from a GeoJSON Point payload."""

    if not geojson_text:
        return None

    try:
        payload = json.loads(geojson_text)
    except (TypeError, json.JSONDecodeError):
        return None

    if (
        not isinstance(payload, dict)
        or payload.get("type") != "Point"
        or not isinstance(payload.get("coordinates"), (list, tuple))
        or len(payload["coordinates"]) != 2
    ):
        return None

    lon, lat = payload["coordinates"]
    if not isinstance(lon, (float, int)) or not isinstance(lat, (float, int)):
        return None

    return float(lon), float(lat)


class StoreChainsWithStoresResponse(BaseModel):
    """Response model for store chains with stores."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    stores: list[StoreResponse] = Field(default_factory=list)
    

#get store chains
@router.get("/store_chains", response_model=Sequence[StoreChain], summary="Get all store chains")
async def get_store_chains(session: Session = Depends(get_db)) -> Sequence[StoreChain]:
    statement = select(StoreChain)
    results = session.exec(statement).all()
    return results

#get stores by store chain
@router.get("/store_chains/{store_chain_id}/stores", response_model=Sequence[StoreResponse], summary="Get stores by store chain")
async def get_stores_by_store_chain(store_chain_id: UUID, session: Session = Depends(get_db)) -> Sequence[StoreResponse]:
    """Return all stores for a given store chain."""

    statement = (
        select(
            Store,
            func.ST_AsGeoJSON(Store.geography).label("geography_geojson"),
        )
        .where(Store.chain_id == store_chain_id)
    )
    results = session.exec(statement).all()
    return [StoreResponse.from_model(store, geojson) for store, geojson in results]

#get storeschains[stores] by distance from location
@router.get("/store_chains/nearby", response_model=Sequence[StoreChainsWithStoresResponse], summary="Get store chains by driving distance from location")
async def get_nearby_store_chains(
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

    stmt = (
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
    for store, chain, _, geojson in session.exec(stmt):
        chain_payload = chain_map.setdefault(
            chain.id, StoreChainsWithStoresResponse(id=chain.id, name=chain.name)
        )
        chain_payload.stores.append(StoreResponse.from_model(store, geojson))

    return list(chain_map.values())
