"""Flask blueprint for the commercial-routes generator UI."""
from __future__ import annotations

import json

from flask import Blueprint, Response, redirect, render_template_string, request, url_for

import routes_batch as batch
import routes_db as db
import routes_sheet_sync as sheet_sync

rutas_bp = Blueprint("rutas", __name__, url_prefix="/rutas")

# CABA barrios + GBA partidos usable as a route origin (subset of app.py's
# ZONAS_PREDEFINIDAS, dropping comuna-level groupings and far-away interior
# cities that don't make sense as a starting point for a local route).
ZONAS_ORIGEN = [
    ("Retiro", "Retiro, Buenos Aires, Argentina"),
    ("San Nicolas", "San Nicolas, Buenos Aires, Argentina"),
    ("Puerto Madero", "Puerto Madero, Buenos Aires, Argentina"),
    ("San Telmo", "San Telmo, Buenos Aires, Argentina"),
    ("Monserrat", "Monserrat, Buenos Aires, Argentina"),
    ("Constitucion", "Constitucion, Buenos Aires, Argentina"),
    ("Recoleta", "Recoleta, Buenos Aires, Argentina"),
    ("Balvanera", "Balvanera, Buenos Aires, Argentina"),
    ("San Cristobal", "San Cristobal, Buenos Aires, Argentina"),
    ("La Boca", "La Boca, Buenos Aires, Argentina"),
    ("Barracas", "Barracas, Buenos Aires, Argentina"),
    ("Parque Patricios", "Parque Patricios, Buenos Aires, Argentina"),
    ("Nueva Pompeya", "Nueva Pompeya, Buenos Aires, Argentina"),
    ("Almagro", "Almagro, Buenos Aires, Argentina"),
    ("Boedo", "Boedo, Buenos Aires, Argentina"),
    ("Caballito", "Caballito, Buenos Aires, Argentina"),
    ("Flores", "Flores, Buenos Aires, Argentina"),
    ("Parque Chacabuco", "Parque Chacabuco, Buenos Aires, Argentina"),
    ("Villa Soldati", "Villa Soldati, Buenos Aires, Argentina"),
    ("Villa Riachuelo", "Villa Riachuelo, Buenos Aires, Argentina"),
    ("Villa Lugano", "Villa Lugano, Buenos Aires, Argentina"),
    ("Liniers", "Liniers, Buenos Aires, Argentina"),
    ("Mataderos", "Mataderos, Buenos Aires, Argentina"),
    ("Parque Avellaneda", "Parque Avellaneda, Buenos Aires, Argentina"),
    ("Villa Real", "Villa Real, Buenos Aires, Argentina"),
    ("Monte Castro", "Monte Castro, Buenos Aires, Argentina"),
    ("Versalles", "Versalles, Buenos Aires, Argentina"),
    ("Floresta", "Floresta, Buenos Aires, Argentina"),
    ("Velez Sarsfield", "Velez Sarsfield, Buenos Aires, Argentina"),
    ("Villa Luro", "Villa Luro, Buenos Aires, Argentina"),
    ("Villa General Mitre", "Villa General Mitre, Buenos Aires, Argentina"),
    ("Villa Devoto", "Villa Devoto, Buenos Aires, Argentina"),
    ("Villa del Parque", "Villa del Parque, Buenos Aires, Argentina"),
    ("Villa Santa Rita", "Villa Santa Rita, Buenos Aires, Argentina"),
    ("Coghlan", "Coghlan, Buenos Aires, Argentina"),
    ("Saavedra", "Saavedra, Buenos Aires, Argentina"),
    ("Villa Urquiza", "Villa Urquiza, Buenos Aires, Argentina"),
    ("Villa Pueyrredon", "Villa Pueyrredon, Buenos Aires, Argentina"),
    ("Belgrano", "Belgrano, Buenos Aires, Argentina"),
    ("Nunez", "Nunez, Buenos Aires, Argentina"),
    ("Colegiales", "Colegiales, Buenos Aires, Argentina"),
    ("Palermo", "Palermo, Buenos Aires, Argentina"),
    ("Chacarita", "Chacarita, Buenos Aires, Argentina"),
    ("Villa Crespo", "Villa Crespo, Buenos Aires, Argentina"),
    ("La Paternal", "La Paternal, Buenos Aires, Argentina"),
    ("Villa Ortuzar", "Villa Ortuzar, Buenos Aires, Argentina"),
    ("Agronomia", "Agronomia, Buenos Aires, Argentina"),
    ("Parque Chas", "Parque Chas, Buenos Aires, Argentina"),
    ("San Isidro (GBA Norte)", "San Isidro, Buenos Aires, Argentina"),
    ("Vicente Lopez (GBA Norte)", "Vicente Lopez, Buenos Aires, Argentina"),
    ("Tigre (GBA Norte)", "Tigre, Buenos Aires, Argentina"),
    ("San Martin (GBA Norte)", "San Martin, Buenos Aires, Argentina"),
    ("Tres de Febrero (GBA Norte)", "Tres de Febrero, Buenos Aires, Argentina"),
    ("Hurlingham (GBA Norte)", "Hurlingham, Buenos Aires, Argentina"),
    ("Quilmes (GBA Sur)", "Quilmes, Buenos Aires, Argentina"),
    ("Avellaneda (GBA Sur)", "Avellaneda, Buenos Aires, Argentina"),
    ("Lomas de Zamora (GBA Sur)", "Lomas de Zamora, Buenos Aires, Argentina"),
    ("Lanus (GBA Sur)", "Lanus, Buenos Aires, Argentina"),
    ("Berazategui (GBA Sur)", "Berazategui, Buenos Aires, Argentina"),
    ("Florencio Varela (GBA Sur)", "Florencio Varela, Buenos Aires, Argentina"),
    ("Almirante Brown (GBA Sur)", "Almirante Brown, Buenos Aires, Argentina"),
    ("Esteban Echeverria (GBA Sur)", "Esteban Echeverria, Buenos Aires, Argentina"),
    ("Moron (GBA Oeste)", "Moron, Buenos Aires, Argentina"),
    ("La Matanza (GBA Oeste)", "La Matanza, Buenos Aires, Argentina"),
    ("Merlo (GBA Oeste)", "Merlo, Buenos Aires, Argentina"),
    ("Moreno (GBA Oeste)", "Moreno, Buenos Aires, Argentina"),
    ("Ituzaingo (GBA Oeste)", "Ituzaingo, Buenos Aires, Argentina"),
]


def _conn():
    return db.get_connection(db.DB_PATH)


BASE_STYLE = """
<style>
  :root {
    --blue: #0071e3;
    --blue-dark: #0058b0;
    --bg: #f5f5f7;
    --surface: #ffffff;
    --text: #1d1d1f;
    --text-muted: #6e6e73;
    --border: #d2d2d7;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 24px;
    line-height: 1.5;
  }
  h1 { font-size: 22px; font-weight: 600; margin: 0 0 16px; }
  h2 { font-size: 16px; font-weight: 600; margin-top: 24px; }
  a { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }
  form, ul {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 16px;
    list-style: none;
  }
  ul { padding: 8px 16px; }
  li { padding: 6px 0; border-bottom: 1px solid var(--bg); }
  li:last-child { border-bottom: none; }
  label { display: block; margin-bottom: 10px; color: var(--text-muted); font-size: 14px; }
  input[type="text"], input[type="number"], select {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 14px;
    margin-top: 4px;
    font-family: inherit;
  }
  button, input[type="submit"] {
    background: var(--blue);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  button:hover { background: var(--blue-dark); }
  button:disabled { background: var(--border); cursor: not-allowed; }
</style>
"""

PAGE_HOME = """
<!doctype html>
<title>Rutas comerciales</title>
""" + BASE_STYLE + """
<h1>Generador de rutas comerciales</h1>
<form method="post" action="{{ url_for('rutas.generar') }}">
  <label>Origen:
    <select name="origen_select" id="origenSelect" onchange="onOrigenSelectChange()" required>
      <option value="" disabled selected>-- Elegir origen --</option>
      {% if origenes_guardados %}
      <optgroup label="Origenes guardados">
        {% for o in origenes_guardados %}
          <option value="guardado|{{ o.origen_lat }}|{{ o.origen_lng }}|{{ o.origen_texto }}">{{ o.origen_texto }}</option>
        {% endfor %}
      </optgroup>
      {% endif %}
      <optgroup label="Zona / Barrio">
        {% for label, query in zonas %}
          <option value="zona|{{ query }}">{{ label }}</option>
        {% endfor %}
      </optgroup>
      <option value="otro">Otra direccion (escribir)...</option>
    </select>
  </label>
  <div id="origenLibreWrap" style="display:none;">
    <label>Direccion o nombre del negocio (como figura en el mapa):
      <input type="text" id="origenLibre" name="origen_libre"></label>
  </div>
  <label>Cantidad de direcciones: <input type="number" name="n" value="40" min="1" required></label><br>
  <button type="submit">Generar lote</button>
</form>

<script>
function onOrigenSelectChange() {
  var sel = document.getElementById('origenSelect');
  var wrap = document.getElementById('origenLibreWrap');
  var libre = document.getElementById('origenLibre');
  var esOtro = sel.value === 'otro';
  wrap.style.display = esOtro ? 'block' : 'none';
  libre.required = esOtro;
}
</script>

<button type="button" id="syncBtn" onclick="sincronizar()">Sincronizar leads desde el Sheet</button>
<p id="syncProgress"></p>
<div id="syncLog" style="max-height: 200px; overflow-y: auto; font-size: 13px; color: #555;"></div>

<p><a href="{{ url_for('rutas.historial') }}">Ver historial de lotes</a> |
   <a href="{{ url_for('rutas.fallidos') }}">Ver leads no geocodificables</a> |
   <a href="{{ url_for('rutas.mapa') }}">Ver mapa</a></p>

<script>
function appendSyncLog(msg) {
  var el = document.getElementById('syncLog');
  var p = document.createElement('p');
  p.textContent = msg;
  el.appendChild(p);
  el.scrollTop = el.scrollHeight;
}

function sincronizar() {
  var btn = document.getElementById('syncBtn');
  var progress = document.getElementById('syncProgress');
  document.getElementById('syncLog').innerHTML = '';
  progress.textContent = '';
  btn.disabled = true;

  var src = new EventSource('{{ url_for("rutas.sincronizar_stream") }}');

  src.onmessage = function(e) {
    var data = JSON.parse(e.data);
    if (data.type === 'log') {
      appendSyncLog(data.msg);
    } else if (data.type === 'progress') {
      progress.textContent = 'Geocodificando: ' + data.actual + ' / ' + data.total +
        (data.negocio ? ' (' + data.negocio + ')' : '');
    } else if (data.type === 'done') {
      progress.textContent = '';
      appendSyncLog('Listo: ' + data.summary.nuevos + ' nuevos, ' +
        data.summary.geocodificados + ' geocodificados, ' + data.summary.fallidos + ' fallidos.');
      btn.disabled = false;
      src.close();
    } else if (data.type === 'error') {
      appendSyncLog('Error: ' + data.msg);
      btn.disabled = false;
      src.close();
    }
  };

  src.onerror = function() {
    appendSyncLog('Se perdio la conexion con el servidor.');
    btn.disabled = false;
    src.close();
  };
}
</script>
"""

PAGE_RESULTADO = """
<!doctype html>
<title>Lote generado</title>
""" + BASE_STYLE + """
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
""" + BASE_STYLE + """
<p>Error: {{ error }}</p>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_FALLIDOS = """
<!doctype html>
<title>Leads no geocodificables</title>
""" + BASE_STYLE + """
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
""" + BASE_STYLE + """
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
""" + BASE_STYLE + """
<style>
  #map { height: 600px; width: 100%; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); }
  #filtros {
    max-height: 200px; overflow-y: auto; background: var(--surface);
    border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;
  }
  #filtros label { display: block; font-size: 13px; padding: 4px 0; border: none; color: var(--text); }
  .cat-tabs { display: flex; gap: 4px; margin-bottom: 16px; background: var(--surface);
              border: 1px solid var(--border); border-radius: 10px; padding: 4px; }
  .cat-tab { flex: 1; padding: 8px; border: none; border-radius: 7px; font-size: 13px; font-weight: 600;
             cursor: pointer; background: transparent; color: var(--text-muted); }
  .cat-tab.active { background: var(--blue); color: white; }
  .cat-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
</style>
<h1>Mapa de rutas</h1>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>

<div class="cat-tabs">
  <button type="button" class="cat-tab active" data-cat="Todos" onclick="onCatTabClick(this)">Todos</button>
  <button type="button" class="cat-tab" data-cat="Repuestos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#0071e3;"></span>Repuestos</button>
  <button type="button" class="cat-tab" data-cat="Fundas" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#f58231;"></span>Fundas</button>
  <button type="button" class="cat-tab" data-cat="Telefonos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#3cb44b;"></span>Telefonos</button>
</div>

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

  const categoryColors = {"Repuestos": "#0071e3", "Fundas": "#f58231", "Telefonos": "#3cb44b"};
  const categoryLayers = {};
  Object.keys(categoryColors).forEach(function(cat) { categoryLayers[cat] = L.layerGroup(); });

  allLeads.forEach(function(lead) {
    const layer = categoryLayers[lead.categoria];
    if (!layer) return;
    const color = categoryColors[lead.categoria];
    L.circleMarker([lead.lat, lead.lng], {
      radius: 4, color: color, fillColor: color, fillOpacity: 0.6, weight: 1
    }).bindPopup(lead.negocio + " (" + lead.categoria + ")").addTo(layer);
  });

  function showCategory(cat) {
    Object.keys(categoryLayers).forEach(function(c) { map.removeLayer(categoryLayers[c]); });
    if (cat === "Todos") {
      Object.keys(categoryLayers).forEach(function(c) { categoryLayers[c].addTo(map); });
    } else if (categoryLayers[cat]) {
      categoryLayers[cat].addTo(map);
    }
  }

  function onCatTabClick(btn) {
    document.querySelectorAll(".cat-tab").forEach(function(b) { b.classList.remove("active"); });
    btn.classList.add("active");
    showCategory(btn.dataset.cat);
  }

  showCategory("Todos");

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
    conn = _conn()
    try:
        origenes_guardados = db.get_recent_origenes(conn)
    finally:
        conn.close()
    return render_template_string(PAGE_HOME, origenes_guardados=origenes_guardados, zonas=ZONAS_ORIGEN)


def _resolve_origen(origen_select: str, origen_libre: str) -> tuple[str, tuple[float, float] | None]:
    """Maps the origin form selection to (origen_texto, origen_coords).
    origen_coords is None when it still needs geocoding (zona or free text)."""
    if origen_select.startswith("guardado|"):
        _, lat, lng, texto = origen_select.split("|", 3)
        return texto, (float(lat), float(lng))
    if origen_select.startswith("zona|"):
        return origen_select.split("|", 1)[1], None
    return origen_libre.strip(), None


@rutas_bp.route("/generar", methods=["POST"])
def generar():
    conn = _conn()
    try:
        origen_select = request.form["origen_select"]
        origen_texto, origen_coords = _resolve_origen(origen_select, request.form.get("origen_libre", ""))
        n = int(request.form["n"])
        resultado = batch.generate_lote(conn, origen_texto, n, origen_coords=origen_coords)
    except (KeyError, ValueError) as exc:
        return render_template_string(PAGE_ERROR, error=str(exc)), 400
    finally:
        conn.close()
    return render_template_string(PAGE_RESULTADO, resultado=resultado)


@rutas_bp.route("/sincronizar/stream", methods=["GET"])
def sincronizar_stream():
    def generate():
        conn = _conn()
        try:
            client = sheet_sync.get_sheets_client()
            for event in sheet_sync.sync_all_tabs_progress(conn, client):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'msg': str(exc)})}\n\n"
        finally:
            conn.close()

    return Response(generate(), mimetype="text/event-stream")


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
