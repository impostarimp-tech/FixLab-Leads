"""Geocoding fallback chain for leads: Maps_URL coordinate extraction, then
Nominatim by address, then Nominatim by business name."""
from __future__ import annotations

import re
import threading
import time

import requests

_MAPS_URL_COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")


def parse_coords_from_maps_url(maps_url: str | None) -> tuple[float, float] | None:
    """Extracts (lat, lng) from a Google Maps URL if it contains an @lat,lng segment."""
    if not maps_url:
        return None
    match = _MAPS_URL_COORD_RE.search(maps_url)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "fixlab-leads-routes/1.0 (uso interno)"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0

_last_request_time: float = 0.0
_rate_limit_lock = threading.Lock()


def _respect_rate_limit() -> None:
    global _last_request_time
    with _rate_limit_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        _last_request_time = time.monotonic()


def nominatim_geocode(query: str, max_retries: int = 2) -> tuple[float, float] | None:
    """Geocodes free text via the public Nominatim API. Returns None on failure
    (empty results, HTTP error, or malformed response) after exhausting retries."""
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": NOMINATIM_USER_AGENT}

    for attempt in range(max_retries + 1):
        _respect_rate_limit()
        try:
            response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            results = response.json()
            if not results:
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def geocode_lead(
    negocio: str, direccion: str | None, maps_url: str | None
) -> tuple[tuple[float, float] | None, str]:
    """Runs the fallback chain for one lead: Maps_URL -> Direccion -> Negocio.
    Returns ((lat, lng), source) or (None, 'fallido')."""
    coords = parse_coords_from_maps_url(maps_url)
    if coords:
        return coords, "maps_url"

    if direccion:
        coords = nominatim_geocode(f"{direccion}, Buenos Aires, Argentina")
        if coords:
            return coords, "direccion"

    coords = nominatim_geocode(f"{negocio}, Buenos Aires, Argentina")
    if coords:
        return coords, "negocio"

    return None, "fallido"


def geocode_free_text(query: str) -> tuple[float, float] | None:
    """Geocodes an arbitrary manually-typed query (e.g. a route origin address)."""
    return nominatim_geocode(f"{query}, Buenos Aires, Argentina")
