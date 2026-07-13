"""Pure geographic algorithms: nearest-neighbor route ordering and sub-lote
chunking. No external services, no I/O."""
from __future__ import annotations

import math
from urllib.parse import urlencode

EARTH_RADIUS_METERS = 6371000
MAX_STOPS_PER_SUBLOTE = 9


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def select_n_nearest(origin: tuple[float, float], candidates: list[dict], n: int) -> list[dict]:
    """Returns up to n candidates closest to origin, sorted by distance ascending.
    Each candidate dict must have 'lat' and 'lng' keys."""
    origin_lat, origin_lng = origin
    scored = sorted(
        candidates,
        key=lambda c: haversine_meters(origin_lat, origin_lng, c["lat"], c["lng"]),
    )
    return scored[:n]


def order_nearest_neighbor(origin: tuple[float, float], points: list[dict]) -> list[dict]:
    """Orders points into a route starting at origin: repeatedly visits the closest
    unvisited point. Does not include the origin itself in the result."""
    remaining = list(points)
    ordered: list[dict] = []
    current_lat, current_lng = origin

    while remaining:
        nearest = min(
            remaining,
            key=lambda p: haversine_meters(current_lat, current_lng, p["lat"], p["lng"]),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lng = nearest["lat"], nearest["lng"]

    return ordered


def chunk_into_sublotes(ordered_points: list[dict], max_size: int = MAX_STOPS_PER_SUBLOTE) -> list[list[dict]]:
    """Splits an already-ordered sequence into consecutive chunks of up to max_size,
    preserving order so each chunk continues geographically from the previous one."""
    return [ordered_points[i : i + max_size] for i in range(0, len(ordered_points), max_size)]


def build_maps_link(origin: tuple[float, float], stops: list[dict]) -> str:
    """Builds a Google Maps directions URL: origin -> up to 8 waypoints -> destination
    (the last stop). `stops` must have between 1 and 9 items."""
    if not stops:
        raise ValueError("stops must contain at least one point")
    if len(stops) > MAX_STOPS_PER_SUBLOTE:
        raise ValueError(f"stops must contain at most {MAX_STOPS_PER_SUBLOTE} points")

    waypoints = stops[:-1]
    destination = stops[-1]

    params = {
        "api": "1",
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination['lat']},{destination['lng']}",
    }
    if waypoints:
        params["waypoints"] = "|".join(f"{p['lat']},{p['lng']}" for p in waypoints)

    return "https://www.google.com/maps/dir/?" + urlencode(params)
