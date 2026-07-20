"""Orchestrates full lote generation: pool selection, ordering, chunking, and
persistence, chaining each sub-lote's origin from the previous sub-lote's last stop."""
from __future__ import annotations

import sqlite3

import routes_algorithm as algo
import routes_db as db
import routes_geocoding as geocoding


def generate_lote(
    conn: sqlite3.Connection,
    origen_texto: str,
    n: int,
    origen_coords: tuple[float, float] | None = None,
    categoria: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
) -> dict:
    """Resolves the origin's coordinates (in order: origen_coords if already known
    -- e.g. a saved origin or a zone with a pre-vetted query --, then a matching
    lead's own coordinates if origen_texto is typed exactly as it appears on the
    map, then Nominatim geocoding as a last resort), selects up to n nearby
    non-shared candidates (optionally restricted to one categoria and/or a minimum
    review count/rating; the same business listed under multiple category tabs
    counts once, per get_candidate_pool), builds the route via algo.build_route
    (tries both nearest-neighbor and cheapest-insertion construction, each
    refined with 2-opt, keeps whichever is shorter), splits into <=9-stop
    sub-lotes chained end-to-end, and persists everything. Returns a summary
    dict."""
    if origen_coords is not None:
        origin_coords = origen_coords
    else:
        lead_match = db.find_lead_by_name(conn, origen_texto)
        if lead_match is not None:
            origin_coords = (lead_match["lat"], lead_match["lng"])
        else:
            origin_coords = geocoding.geocode_free_text(origen_texto)
    if origin_coords is None:
        raise ValueError(f"No se pudo geocodificar el origen: {origen_texto}")
    if n < 1:
        raise ValueError(f"n debe ser un entero positivo, recibido: {n}")

    pool = db.get_candidate_pool(
        conn, categoria=categoria, min_reviews=min_reviews, min_rating=min_rating, origin=origin_coords,
    )
    ordered = algo.build_route(origin_coords, pool, n)
    chunks = algo.chunk_into_sublotes(ordered)

    lote_id = db.create_lote(
        conn,
        origen_lat=origin_coords[0],
        origen_lng=origin_coords[1],
        origen_texto=origen_texto,
        tamano_solicitado=n,
        tamano_real=len(ordered),
        categoria=categoria,
    )

    sublotes_creados = []
    current_origin = origin_coords
    for i, chunk in enumerate(chunks, start=1):
        maps_link = algo.build_maps_link(current_origin, chunk)
        sublote_id = db.create_sublote(
            conn,
            lote_id=lote_id,
            orden=i,
            maps_link=maps_link,
            lead_id_groups=[c["lead_ids"] for c in chunk],
        )
        sublotes_creados.append({"id": sublote_id, "orden": i, "maps_link": maps_link, "leads": chunk})
        current_origin = (chunk[-1]["lat"], chunk[-1]["lng"])

    return {
        "lote_id": lote_id,
        "origen_texto": origen_texto,
        "categoria": categoria,
        "tamano_solicitado": n,
        "tamano_real": len(ordered),
        "sublotes": sublotes_creados,
    }
