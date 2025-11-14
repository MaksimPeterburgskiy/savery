"""Tests for geography utility functions."""

from __future__ import annotations

import math

import pytest

from backend.app.api.utils.geography import extract_point_coordinates, haversine_distance


class TestExtractPointCoordinates:
    """Tests for the extract_point_coordinates function."""

    def test_extract_valid_point(self) -> None:
        """Test extracting coordinates from valid GeoJSON Point."""
        geojson = '{"type": "Point", "coordinates": [-122.4194, 37.7749]}'
        result = extract_point_coordinates(geojson)
        assert result == (-122.4194, 37.7749)

    def test_extract_with_none_input(self) -> None:
        """Test that None input returns None."""
        result = extract_point_coordinates(None)
        assert result is None

    def test_extract_with_empty_string(self) -> None:
        """Test that empty string returns None."""
        result = extract_point_coordinates("")
        assert result is None

    def test_extract_with_invalid_json(self) -> None:
        """Test that invalid JSON returns None."""
        result = extract_point_coordinates("not valid json")
        assert result is None

    def test_extract_with_wrong_type(self) -> None:
        """Test that non-Point type returns None."""
        geojson = '{"type": "LineString", "coordinates": [[-122.4194, 37.7749]]}'
        result = extract_point_coordinates(geojson)
        assert result is None

    def test_extract_with_missing_coordinates(self) -> None:
        """Test that missing coordinates returns None."""
        geojson = '{"type": "Point"}'
        result = extract_point_coordinates(geojson)
        assert result is None

    def test_extract_with_invalid_coordinate_count(self) -> None:
        """Test that invalid number of coordinates returns None."""
        geojson = '{"type": "Point", "coordinates": [-122.4194]}'
        result = extract_point_coordinates(geojson)
        assert result is None

    def test_extract_with_non_numeric_coordinates(self) -> None:
        """Test that non-numeric coordinates returns None."""
        geojson = '{"type": "Point", "coordinates": ["not", "numbers"]}'
        result = extract_point_coordinates(geojson)
        assert result is None

    def test_extract_with_integer_coordinates(self) -> None:
        """Test that integer coordinates are converted to floats."""
        geojson = '{"type": "Point", "coordinates": [-122, 37]}'
        result = extract_point_coordinates(geojson)
        assert result == (-122.0, 37.0)
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)


class TestHaversineDistance:
    """Tests for the haversine_distance function."""

    def test_same_point_returns_zero(self) -> None:
        """Test that distance between same point is zero."""
        lon, lat = -122.4194, 37.7749
        distance = haversine_distance(lon, lat, lon, lat)
        assert distance == 0.0

    def test_distance_between_known_points(self) -> None:
        """Test distance calculation between known points.
        
        San Francisco (-122.4194, 37.7749) to Los Angeles (-118.2437, 34.0522)
        is approximately 559 km or 559,000 meters.
        """
        # San Francisco coordinates
        sf_lon, sf_lat = -122.4194, 37.7749
        # Los Angeles coordinates
        la_lon, la_lat = -118.2437, 34.0522
        
        distance = haversine_distance(sf_lon, sf_lat, la_lon, la_lat)
        
        # Allow 1% margin of error
        expected = 559000  # meters
        assert abs(distance - expected) < expected * 0.01

    def test_distance_is_symmetric(self) -> None:
        """Test that distance from A to B equals distance from B to A."""
        lon1, lat1 = -122.4194, 37.7749
        lon2, lat2 = -118.2437, 34.0522
        
        distance_ab = haversine_distance(lon1, lat1, lon2, lat2)
        distance_ba = haversine_distance(lon2, lat2, lon1, lat1)
        
        assert distance_ab == distance_ba

    def test_distance_across_equator(self) -> None:
        """Test distance calculation across the equator."""
        # Point just north of equator
        lon1, lat1 = 0.0, 1.0
        # Point just south of equator
        lon2, lat2 = 0.0, -1.0
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        # Distance should be approximately 222 km (2 degrees at equator)
        expected = 222000  # meters
        assert abs(distance - expected) < expected * 0.01

    def test_distance_across_prime_meridian(self) -> None:
        """Test distance calculation across the prime meridian."""
        # Point just west of prime meridian
        lon1, lat1 = -1.0, 0.0
        # Point just east of prime meridian
        lon2, lat2 = 1.0, 0.0
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        # Distance should be approximately 222 km (2 degrees at equator)
        expected = 222000  # meters
        assert abs(distance - expected) < expected * 0.01

    def test_distance_at_north_pole(self) -> None:
        """Test distance calculation near the north pole."""
        # Two points near north pole with different longitudes should be very close
        lon1, lat1 = 0.0, 89.9
        lon2, lat2 = 180.0, 89.9
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        # Should be a small distance (less than 100 km)
        assert distance < 100000

    def test_short_distance(self) -> None:
        """Test that haversine works for short distances."""
        # Two points very close together
        lon1, lat1 = -122.4194, 37.7749
        lon2, lat2 = -122.4184, 37.7750
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        # Should be about 100 meters
        assert 50 < distance < 150

    def test_long_distance_antipodal(self) -> None:
        """Test distance for nearly antipodal points."""
        # Nearly opposite sides of Earth
        lon1, lat1 = 0.0, 0.0
        lon2, lat2 = 180.0, 0.0
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        # Should be approximately half Earth's circumference (20,000 km)
        expected = 20000000  # meters
        assert abs(distance - expected) < expected * 0.01

    def test_returns_positive_distance(self) -> None:
        """Test that distance is always positive."""
        lon1, lat1 = -122.4194, 37.7749
        lon2, lat2 = -118.2437, 34.0522
        
        distance = haversine_distance(lon1, lat1, lon2, lat2)
        
        assert distance > 0
