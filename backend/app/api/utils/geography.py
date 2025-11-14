"""Helpers for working with geography columns in API responses."""

from __future__ import annotations

import json


def extract_point_coordinates(geojson_text: str | None) -> tuple[float, float] | None:
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
