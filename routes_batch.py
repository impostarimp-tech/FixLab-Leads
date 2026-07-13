"""Orchestrates full lote generation: pool selection, ordering, chunking, and
persistence, chaining each sub-lote's origin from the previous sub-lote's last stop."""
from __future__ import annotations

import sqlite3

import routes_algorithm as algo
import routes_db as db
import routes_geocoding as geocoding


def generate_lote(conn: sqlite3.Connection, origen_texto: str, n: int) -> dict:
    """Geocodes the origin, selects up to n nearby non-shared candidates, orders them
    into a continuous route, splits into <=9-stop sub-lotes chained end-to-end, and
    persists everything. Returns a summary dict."""
    origin_coords = geocoding.geocode_free_text(origen_texto)
    if origin_coords is None:
        raise ValueError(f"No se pudo geocodificar el origen: {origen_texto}")
    if n < 1:
        raise ValueError(f"n debe ser un entero positivo, recibido: {n}")

    pool = [dict(row) for row in db.get_candidate_pool(conn)]
    nearest = algo.select_n_nearest(origin_coords, pool, n)
    ordered = algo.order_nearest_neighbor(origin_coords, nearest)
    chunks = algo.chunk_into_sublotes(ordered)

    lote_id = db.create_lote(
        conn,
        origen_lat=origin_coords[0],
        origen_lng=origin_coords[1],
        origen_texto=origen_texto,
        tamano_solicitado=n,
        tamano_real=len(ordered),
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
            lead_ids_in_order=[c["id"] for c in chunk],
        )
        sublotes_creados.append({"id": sublote_id, "orden": i, "maps_link": maps_link, "leads": chunk})
        current_origin = (chunk[-1]["lat"], chunk[-1]["lng"])

    return {
        "lote_id": lote_id,
        "origen_texto": origen_texto,
        "tamano_solicitado": n,
        "tamano_real": len(ordered),
        "sublotes": sublotes_creados,
    }
