"""Schemas for catalog (store) endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.utils.geography import extract_point_coordinates
from backend.app.models import Store


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
        coords = extract_point_coordinates(geography_geojson)
        if coords is not None:
            base_data.update({"longitude": coords[0], "latitude": coords[1]})

        return cls(**base_data)


class StoreChainsWithStoresResponse(BaseModel):
    """Response model for store chains with stores."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    stores: list[StoreResponse] = Field(default_factory=list)


__all__ = ["StoreChainsWithStoresResponse", "StoreResponse"]
