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


_STREET_ABBREVIATIONS = {
    "Cdad.": "Ciudad",
    "Gral.": "General",
    "Tte.": "Teniente",
    "Sta.": "Santa",
    "Pres.": "Presidente",
    "Pdte.": "Presidente",
    "Dr.": "Doctor",
    "Dra.": "Doctora",
    "Cnel.": "Coronel",
    "Almte.": "Almirante",
    "Gdor.": "Gobernador",
    "Pje.": "Pasaje",
    "Cno.": "Camino",
    "Blvd.": "Boulevard",
    "Comod.": "Comodoro",
    "Ing.": "Ingeniero",
    "Int.": "Intendente",
}

_STREET_ABBREVIATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(abbr) for abbr in _STREET_ABBREVIATIONS) + r")"
)


def _expand_abbreviations(direccion: str) -> str:
    """Expands common Argentine street-type/title abbreviations (Cdad., Gral.,
    Cnel., etc.) that Nominatim's free-text search doesn't recognize, without
    changing the address's actual meaning."""
    return _STREET_ABBREVIATION_RE.sub(
        lambda m: _STREET_ABBREVIATIONS[m.group(0)], direccion
    )


_POSTAL_CODE_CITY_RE = re.compile(r"(\b[A-Z]\d{4}(?:[A-Z]{2,3})?)\s+(Ciudad|Provincia)\b")


def _insert_postal_code_comma(direccion: str) -> str:
    """Inserts a comma between a postal code (e.g. C1081ABA, B1602) and the
    "Ciudad"/"Provincia" that follows it — scraped addresses often run them
    together, which breaks Nominatim's parser."""
    return _POSTAL_CODE_CITY_RE.sub(r"\1, \2", direccion)


def _with_city_suffix(text: str) -> str:
    """Appends ', Buenos Aires, Argentina' unless the text already mentions
    Buenos Aires. Scraped addresses usually already include full city context
    (e.g. "Ciudad Autónoma de Buenos Aires, Argentina"), and appending our own
    suffix on top creates a redundant double-mention that breaks Nominatim's
    parser."""
    if "buenos aires" in text.lower():
        return text
    return f"{text}, Buenos Aires, Argentina"


# Rough bounding box for AMBA (Buenos Aires metro area: CABA + Greater Buenos
# Aires). This tool only ever deals with leads/routes in this area, so any
# Nominatim match outside it is treated as a wrong match rather than accepted.
AMBA_LAT_MIN, AMBA_LAT_MAX = -35.3, -34.3
AMBA_LNG_MIN, AMBA_LNG_MAX = -59.3, -58.0


def _within_amba_bounds(lat: float, lng: float) -> bool:
    return AMBA_LAT_MIN <= lat <= AMBA_LAT_MAX and AMBA_LNG_MIN <= lng <= AMBA_LNG_MAX


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
            lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
            if not _within_amba_bounds(lat, lng):
                return None
            return lat, lng
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
        normalizado = _insert_postal_code_comma(_expand_abbreviations(direccion))
        coords = nominatim_geocode(_with_city_suffix(normalizado))
        if coords:
            return coords, "direccion"

    coords = nominatim_geocode(_with_city_suffix(negocio))
    if coords:
        return coords, "negocio"

    return None, "fallido"


def geocode_free_text(query: str) -> tuple[float, float] | None:
    """Geocodes an arbitrary manually-typed query (e.g. a route origin address)."""
    return nominatim_geocode(_with_city_suffix(query))
