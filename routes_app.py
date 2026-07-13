"""Flask blueprint for the commercial-routes generator UI."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template_string, request, url_for

import routes_batch as batch
import routes_db as db
import routes_sheet_sync as sheet_sync

rutas_bp = Blueprint("rutas", __name__, url_prefix="/rutas")


def _conn():
    return db.get_connection(db.DB_PATH)


PAGE_HOME = """
<!doctype html>
<title>Rutas comerciales</title>
<h1>Generador de rutas comerciales</h1>
<form method="post" action="{{ url_for('rutas.generar') }}">
  <label>Origen: <input type="text" name="origen" required></label><br>
  <label>Cantidad de direcciones: <input type="number" name="n" value="40" min="1" required></label><br>
  <button type="submit">Generar lote</button>
</form>
<form method="post" action="{{ url_for('rutas.sincronizar') }}">
  <button type="submit">Sincronizar leads desde el Sheet</button>
</form>
{% if sync_summary %}
  <p>Sync: {{ sync_summary.nuevos }} nuevos, {{ sync_summary.geocodificados }} geocodificados,
     {{ sync_summary.fallidos }} fallidos.</p>
{% endif %}
<p><a href="{{ url_for('rutas.historial') }}">Ver historial de lotes</a> |
   <a href="{{ url_for('rutas.fallidos') }}">Ver leads no geocodificables</a> |
   <a href="{{ url_for('rutas.mapa') }}">Ver mapa</a></p>
"""

PAGE_RESULTADO = """
<!doctype html>
<title>Lote generado</title>
<h1>Lote #{{ resultado.lote_id }} — {{ resultado.tamano_real }}/{{ resultado.tamano_solicitado }} direcciones</h1>
<p><strong>Aviso:</strong> si el vendedor abre el link desde el navegador del celular
   (en vez de la app de Maps instalada), puede que solo se respeten 3 waypoints en vez de 9.
   Recomendale abrir con la app instalada.</p>
{% for sublote in resultado.sublotes %}
  <h2>Sub-lote {{ sublote.orden }} ({{ sublote.leads|length }} paradas)</h2>
  <p><a href="{{ sublote.maps_link }}" target="_blank">{{ sublote.maps_link }}</a></p>
  <ul>
    {% for lead in sublote.leads %}
      <li>{{ lead.negocio }} — {{ lead.direccion }}</li>
    {% endfor %}
  </ul>
  <form method="post" action="{{ url_for('rutas.compartir_sublote', sublote_id=sublote.id) }}">
    <button type="submit">Marcar este sub-lote como compartido</button>
  </form>
{% endfor %}
<form method="post" action="{{ url_for('rutas.compartir_lote', lote_id=resultado.lote_id) }}">
  <button type="submit">Marcar todo el lote como compartido</button>
</form>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_ERROR = """
<!doctype html>
<title>Error</title>
<p>Error: {{ error }}</p>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_FALLIDOS = """
<!doctype html>
<title>Leads no geocodificables</title>
<h1>Leads no geocodificables</h1>
<ul>
{% for lead in leads %}
  <li>[{{ lead.categoria }}] {{ lead.negocio }} — {{ lead.direccion }}</li>
{% else %}
  <li>Ninguno por ahora.</li>
{% endfor %}
</ul>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_HISTORIAL = """
<!doctype html>
<title>Historial de lotes</title>
<h1>Historial de lotes</h1>
<ul>
{% for lote in lotes %}
  <li>Lote #{{ lote.id }} — {{ lote.fecha_generado }} — origen: {{ lote.origen_texto }}
      — {{ lote.tamano_real }}/{{ lote.tamano_solicitado }} direcciones</li>
{% else %}
  <li>Todavia no generaste ningun lote.</li>
{% endfor %}
</ul>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_MAPA = """
<!doctype html>
<title>Mapa de rutas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  #map { height: 600px; width: 100%; }
  #filtros { max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 8px; margin-bottom: 10px; }
  #filtros label { display: block; font-size: 13px; padding: 2px 0; }
</style>
<h1>Mapa de rutas</h1>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>

<div id="filtros">
  {% for lote in lotes %}
    <label>
      <input type="checkbox" class="lote-checkbox" value="{{ lote.id }}">
      Lote #{{ lote.id }} — {{ lote.fecha_generado }} — {{ lote.origen_texto }}
      ({{ lote.tamano_real }}/{{ lote.tamano_solicitado }})
    </label>
  {% else %}
    <p>Todavia no generaste ningun lote.</p>
  {% endfor %}
</div>

<div id="map"></div>

<script>
  const allLeads = {{ all_leads | tojson }};
  const lotePoints = {{ lote_points | tojson }};
  const colors = ["#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
                  "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990"];

  const map = L.map('map');
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  allLeads.forEach(function(lead) {
    L.circleMarker([lead.lat, lead.lng], {
      radius: 4, color: "#999", fillColor: "#999", fillOpacity: 0.6, weight: 1
    }).bindPopup(lead.negocio).addTo(map);
  });

  if (allLeads.length > 0) {
    const bounds = L.latLngBounds(allLeads.map(function(l) { return [l.lat, l.lng]; }));
    map.fitBounds(bounds, {padding: [20, 20]});
  } else {
    map.setView([-34.6, -58.4], 12);
  }

  const loteLayers = {};

  document.querySelectorAll('.lote-checkbox').forEach(function(checkbox, index) {
    checkbox.addEventListener('change', function() {
      const loteId = checkbox.value;
      if (checkbox.checked) {
        const points = lotePoints[loteId] || [];
        const color = colors[index % colors.length];
        const layerGroup = L.layerGroup().addTo(map);
        L.polyline(points.map(function(p) { return [p.lat, p.lng]; }), {
          color: color, weight: 3
        }).addTo(layerGroup);
        points.forEach(function(p, i) {
          L.circleMarker([p.lat, p.lng], {
            radius: 6, color: color, fillColor: color, fillOpacity: 0.9, weight: 2
          }).bindPopup((i === 0 ? "Origen — " : (i + ". ")) + p.negocio).addTo(layerGroup);
        });
        loteLayers[loteId] = layerGroup;
      } else if (loteLayers[loteId]) {
        map.removeLayer(loteLayers[loteId]);
        delete loteLayers[loteId];
      }
    });
  });
</script>
"""


@rutas_bp.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE_HOME, sync_summary=None)


@rutas_bp.route("/generar", methods=["POST"])
def generar():
    conn = _conn()
    try:
        origen = request.form["origen"]
        n = int(request.form["n"])
        resultado = batch.generate_lote(conn, origen, n)
    except (KeyError, ValueError) as exc:
        return render_template_string(PAGE_ERROR, error=str(exc)), 400
    finally:
        conn.close()
    return render_template_string(PAGE_RESULTADO, resultado=resultado)


@rutas_bp.route("/sincronizar", methods=["POST"])
def sincronizar():
    conn = _conn()
    try:
        client = sheet_sync.get_sheets_client()
        summary = sheet_sync.sync_all_tabs(conn, client)
    except Exception as exc:
        return render_template_string(
            PAGE_ERROR, error=f"No se pudo sincronizar con el Sheet: {exc}"
        ), 502
    finally:
        conn.close()
    return render_template_string(PAGE_HOME, sync_summary=summary)


@rutas_bp.route("/sublotes/<int:sublote_id>/compartir", methods=["POST"])
def compartir_sublote(sublote_id: int):
    conn = _conn()
    try:
        db.mark_sublote_compartido(conn, sublote_id)
    finally:
        conn.close()
    return redirect(url_for("rutas.historial"))


@rutas_bp.route("/lotes/<int:lote_id>/compartir", methods=["POST"])
def compartir_lote(lote_id: int):
    conn = _conn()
    try:
        db.mark_lote_compartido(conn, lote_id)
    finally:
        conn.close()
    return redirect(url_for("rutas.historial"))


@rutas_bp.route("/fallidos", methods=["GET"])
def fallidos():
    conn = _conn()
    try:
        leads = db.get_failed_leads(conn)
    finally:
        conn.close()
    return render_template_string(PAGE_FALLIDOS, leads=leads)


@rutas_bp.route("/historial", methods=["GET"])
def historial():
    conn = _conn()
    try:
        lotes = db.get_lote_history(conn)
    finally:
        conn.close()
    return render_template_string(PAGE_HISTORIAL, lotes=lotes)


@rutas_bp.route("/mapa", methods=["GET"])
def mapa():
    conn = _conn()
    try:
        all_leads = [dict(row) for row in db.get_all_geocoded_leads(conn)]
        lotes = [dict(row) for row in db.get_lote_history(conn)]
        lote_points = {lote["id"]: db.get_lote_route_points(conn, lote["id"]) for lote in lotes}
    finally:
        conn.close()
    return render_template_string(PAGE_MAPA, all_leads=all_leads, lotes=lotes, lote_points=lote_points)
