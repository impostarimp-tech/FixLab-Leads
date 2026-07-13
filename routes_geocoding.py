"""Geocoding fallback chain for leads: Maps_URL coordinate extraction, then
Nominatim by address, then Nominatim by business name."""
from __future__ import annotations

import re

_MAPS_URL_COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")


def parse_coords_from_maps_url(maps_url: str | None) -> tuple[float, float] | None:
    """Extracts (lat, lng) from a Google Maps URL if it contains an @lat,lng segment."""
    if not maps_url:
        return None
    match = _MAPS_URL_COORD_RE.search(maps_url)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))
