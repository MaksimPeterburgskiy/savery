"""Helpers for working with geography columns in API responses."""

from __future__ import annotations

import json
import math


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


def haversine_distance(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """Calculate the great-circle distance between two points on Earth using the haversine formula.
    
    Args:
        lon1: Longitude of the first point in degrees
        lat1: Latitude of the first point in degrees
        lon2: Longitude of the second point in degrees
        lat2: Latitude of the second point in degrees
    
    Returns:
        Distance in meters between the two points
    """
    # Earth radius in meters
    R = 6371000
    
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c
