"""Pure geographic algorithms: nearest-neighbor route ordering and sub-lote
chunking. No external services, no I/O."""
from __future__ import annotations

import math
from urllib.parse import urlencode

EARTH_RADIUS_METERS = 6371000
MAX_STOPS_PER_SUBLOTE = 9
MAX_MAPS_WAYPOINTS = 9  # Google Maps Directions API hard limit on total stops (origin + waypoints + destination)


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def build_route_cheapest_insertion(
    origin: tuple[float, float], candidates: list[dict], n: int
) -> list[dict]:
    """Builds an up-to-n-stop open route starting at origin (it does not return
    to origin) using cheapest insertion: at every step, scans every remaining
    candidate against every possible insertion position in the route built so
    far, and inserts whichever (candidate, position) pair adds the least extra
    distance. Unlike picking "the n nearest to origin" and only then ordering
    them, this scans the *entire* candidate pool at each step, so a tight,
    efficient cluster just past the n-th-closest-to-origin point is never
    skipped the way a radius-based cutoff would skip it."""
    remaining = list(candidates)
    route: list[dict] = []

    while remaining and len(route) < n:
        best_candidate = None
        best_position = None
        best_cost = None

        for candidate in remaining:
            for position in range(len(route) + 1):
                before_lat, before_lng = origin if position == 0 else (
                    route[position - 1]["lat"], route[position - 1]["lng"]
                )
                cost = haversine_meters(before_lat, before_lng, candidate["lat"], candidate["lng"])
                if position < len(route):
                    after = route[position]
                    cost += haversine_meters(candidate["lat"], candidate["lng"], after["lat"], after["lng"])
                    cost -= haversine_meters(before_lat, before_lng, after["lat"], after["lng"])

                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_candidate = candidate
                    best_position = position

        route.insert(best_position, best_candidate)
        remaining.remove(best_candidate)

    return route


def _build_route_nearest_neighbor(
    origin: tuple[float, float], candidates: list[dict], n: int
) -> list[dict]:
    """Greedy construction: repeatedly appends whichever remaining candidate is
    nearest to the last stop added (starting from origin), stopping at n. Used
    as the other half of a multi-start comparison against cheapest insertion —
    see build_route."""
    remaining = list(candidates)
    route: list[dict] = []
    current_lat, current_lng = origin

    while remaining and len(route) < n:
        nearest = min(
            remaining,
            key=lambda p: haversine_meters(current_lat, current_lng, p["lat"], p["lng"]),
        )
        route.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lng = nearest["lat"], nearest["lng"]

    return route


def _route_length(origin: tuple[float, float], points: list[dict]) -> float:
    total = 0.0
    lat, lng = origin
    for p in points:
        total += haversine_meters(lat, lng, p["lat"], p["lng"])
        lat, lng = p["lat"], p["lng"]
    return total


def two_opt(origin: tuple[float, float], ordered_points: list[dict]) -> list[dict]:
    """Removes crossing edges from an already-ordered route via the standard
    2-opt local search: repeatedly reverses a sub-segment when doing so
    shortens the total route length, until no such improvement remains.
    Nearest-neighbor construction is greedy and can strand points, forcing a
    long backtrack later that shows up as crossed lines on the map — 2-opt
    fixes exactly that, and for points that happen to lie on a line it
    converges on the straightforward end-to-end sweep."""
    route = list(ordered_points)
    improved = True
    while improved:
        improved = False
        current_length = _route_length(origin, route)
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                candidate = route[:i] + route[i : j + 1][::-1] + route[j + 1 :]
                candidate_length = _route_length(origin, candidate)
                if candidate_length < current_length - 1e-9:
                    route = candidate
                    current_length = candidate_length
                    improved = True
    return route


def build_route(origin: tuple[float, float], candidates: list[dict], n: int) -> list[dict]:
    """Builds the final up-to-n-stop route: constructs a tour both ways
    (nearest-neighbor and cheapest insertion), refines each independently with
    2-opt, and returns whichever ends up shorter. Cheapest insertion is usually
    the better starting point since — unlike nearest-neighbor — it isn't
    anchored to a fixed n-nearest-to-origin cutoff. But 2-opt is a local
    search: it can get stuck at a worse local optimum starting from one
    construction than from the other, depending on the specific point layout,
    so neither construction reliably dominates on every instance. Running
    both and keeping the best is cheap insurance (nearest-neighbor
    construction is near-instant) against relying on a single heuristic."""
    nn_route = two_opt(origin, _build_route_nearest_neighbor(origin, candidates, n))
    ci_route = two_opt(origin, build_route_cheapest_insertion(origin, candidates, n))
    if _route_length(origin, nn_route) <= _route_length(origin, ci_route):
        return nn_route
    return ci_route


def chunk_into_sublotes(ordered_points: list[dict], max_size: int = MAX_STOPS_PER_SUBLOTE) -> list[list[dict]]:
    """Splits an already-ordered sequence into consecutive chunks of up to max_size,
    preserving order so each chunk continues geographically from the previous one."""
    return [ordered_points[i : i + max_size] for i in range(0, len(ordered_points), max_size)]


def build_maps_link(origin: tuple[float, float], stops: list[dict]) -> str:
    """Builds a Google Maps directions URL: origin -> up to 8 waypoints -> destination
    (the last stop). `stops` must have between 1 and MAX_MAPS_WAYPOINTS items."""
    if not stops:
        raise ValueError("stops must contain at least one point")
    if len(stops) > MAX_MAPS_WAYPOINTS:
        raise ValueError(f"stops must contain at most {MAX_MAPS_WAYPOINTS} points")

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
