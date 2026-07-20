"""Flask blueprint for the commercial-routes generator UI."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile

from flask import Blueprint, Response, redirect, render_template_string, request, url_for

import routes_batch as batch
import routes_db as db
import routes_sheet_sync as sheet_sync

SQLITE_MAGIC = b"SQLite format 3\x00"

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

  .nav-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
  .btn-secondary {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--surface); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 14px; font-size: 13px; font-weight: 600;
    text-decoration: none; white-space: nowrap;
  }
  .btn-secondary:hover { background: var(--bg); text-decoration: none; }

  .table-wrap {
    max-height: 70vh; overflow: auto; border: 1px solid var(--border); border-radius: 10px;
    background: var(--surface);
  }
  table { width: 100%; border-collapse: collapse; background: var(--surface); font-size: 12.5px; }
  th, td {
    text-align: left; padding: 5px 10px; border-bottom: 1px solid var(--bg);
    max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  th {
    position: sticky; top: 0; background: var(--bg); color: var(--text-muted);
    font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
    z-index: 1;
  }
  tbody tr:nth-child(even) { background: #fafafa; }
  tbody tr:hover { background: #eaf3ff; }
  tr:last-child td { border-bottom: none; }

  .cat-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; flex: none; }
  .cat-Repuestos { background: #0071e3; }
  .cat-Fundas { background: #f58231; }
  .cat-Telefonos { background: #3cb44b; }

  .badge { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .badge-ok { background: #e6f4ea; color: #1e7e34; }
  .badge-no { background: #fdecea; color: #c0392b; }

  .estado-select {
    border: none; border-radius: 6px; padding: 3px 6px; font-size: 11.5px; font-weight: 600;
    cursor: pointer; font-family: inherit;
  }
  .estado-sin_contactar { background: #f0f0f2; color: #6e6e73; }
  .estado-contactado { background: #e8f0fe; color: #1a56db; }
  .estado-respondio { background: #fff4e5; color: #b45309; }
  .estado-convertido { background: #e6f4ea; color: #1e7e34; }
  .estado-form { margin: 0; padding: 0; background: none; border: none; }
</style>
"""

NAV_LINKS = """
<div class="nav-row">
  <a class="btn-secondary" href="{{ url_for('rutas.home') }}">Inicio</a>
  <a class="btn-secondary" href="{{ url_for('rutas.historial') }}">Historial</a>
  <a class="btn-secondary" href="{{ url_for('rutas.fallidos') }}">No geocodificables</a>
  <a class="btn-secondary" href="{{ url_for('rutas.mapa') }}">Mapa</a>
  <a class="btn-secondary" href="{{ url_for('rutas.crm') }}">CRM</a>
</div>
"""

PAGE_HOME = """
<!doctype html>
<title>Rutas comerciales</title>
""" + BASE_STYLE + NAV_LINKS + """
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
  <label>Categoria:
    <select name="categoria">
      <option value="">Todas</option>
      <option value="Repuestos">Repuestos</option>
      <option value="Fundas">Fundas</option>
      <option value="Telefonos">Telefonos</option>
    </select>
  </label>
  <label>Reviews minimas (opcional): <input type="number" name="min_reviews" min="0" step="1"></label>
  <label>Rating minimo (opcional): <input type="number" name="min_rating" min="0" max="5" step="0.1"></label>
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
""" + BASE_STYLE + NAV_LINKS + """
<h1>Lote #{{ resultado.lote_id }}{% if resultado.categoria %} — {{ resultado.categoria }}{% endif %}
   — {{ resultado.tamano_real }}/{{ resultado.tamano_solicitado }} direcciones</h1>
<p><strong>Aviso:</strong> si el vendedor abre el link desde el navegador del celular
   (en vez de la app de Maps instalada), puede que solo se respeten 3 waypoints en vez de 9.
   Recomendale abrir con la app instalada.</p>
{% for sublote in resultado.sublotes %}
  <h2>Sub-lote {{ sublote.orden }} ({{ sublote.leads|length }} paradas)
    {% if sublote.compartido_en %}<span class="badge badge-ok">Compartido</span>{% endif %}
  </h2>
  <p><a href="{{ sublote.maps_link }}" target="_blank">{{ sublote.maps_link }}</a></p>
  <div class="table-wrap" style="max-height: 260px;">
  <table>
    <thead><tr><th>Negocio</th><th>Categoria</th><th>Direccion</th></tr></thead>
    <tbody>
    {% for lead in sublote.leads %}
      <tr>
        <td title="{{ lead.negocio }}">{{ lead.negocio }}</td>
        <td>
          {% for cat in lead.categorias %}<span class="cat-dot cat-{{ cat }}"></span>{{ cat }}{% if not loop.last %}, {% endif %}{% endfor %}
        </td>
        <td title="{{ lead.direccion or '' }}">{{ lead.direccion or "-" }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
  <form method="post" action="{{ url_for('rutas.compartir_sublote', sublote_id=sublote.id) }}">
    <button type="submit">Marcar este sub-lote como compartido</button>
  </form>
{% endfor %}
<form method="post" action="{{ url_for('rutas.compartir_lote', lote_id=resultado.lote_id) }}">
  <button type="submit">Marcar todo el lote como compartido</button>
</form>
"""

PAGE_ERROR = """
<!doctype html>
<title>Error</title>
""" + BASE_STYLE + NAV_LINKS + """
<p>Error: {{ error }}</p>
"""

PAGE_FALLIDOS = """
<!doctype html>
<title>Leads no geocodificables</title>
""" + BASE_STYLE + NAV_LINKS + """
<h1>Leads no geocodificables</h1>
<p class="crm-summary">{{ leads|length }} lead{{ "s" if leads|length != 1 else "" }} sin geocodificar.</p>
<div class="table-wrap">
<table>
  <thead><tr><th>Categoria</th><th>Negocio</th><th>Direccion</th></tr></thead>
  <tbody>
  {% for lead in leads %}
    <tr>
      <td><span class="cat-dot cat-{{ lead.categoria }}"></span>{{ lead.categoria }}</td>
      <td title="{{ lead.negocio }}">{{ lead.negocio }}</td>
      <td title="{{ lead.direccion or '' }}">{{ lead.direccion or "-" }}</td>
    </tr>
  {% else %}
    <tr><td colspan="3">Ninguno por ahora.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
"""

PAGE_HISTORIAL = """
<!doctype html>
<title>Historial de lotes</title>
""" + BASE_STYLE + NAV_LINKS + """
<h1>Historial de lotes</h1>
<div class="table-wrap">
<table>
  <thead><tr><th>Lote</th><th>Fecha</th><th>Origen</th><th>Categoria</th><th>Direcciones</th><th>Acciones</th></tr></thead>
  <tbody>
  {% for lote in lotes %}
    <tr>
      <td>#{{ lote.id }}</td>
      <td>{{ lote.fecha_generado }}</td>
      <td title="{{ lote.origen_texto }}">{{ lote.origen_texto }}</td>
      <td>
        {% if lote.categoria %}<span class="cat-dot cat-{{ lote.categoria }}"></span>{{ lote.categoria }}{% else %}Todas{% endif %}
      </td>
      <td>{{ lote.tamano_real }}/{{ lote.tamano_solicitado }}</td>
      <td><a class="btn-secondary" href="{{ url_for('rutas.detalle_lote', lote_id=lote.id) }}">Ver rutas</a></td>
    </tr>
  {% else %}
    <tr><td colspan="6">Todavia no generaste ningun lote.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
"""

PAGE_MAPA = """
<!doctype html>
<title>Mapa de rutas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
""" + BASE_STYLE + NAV_LINKS + """
<style>
  .map-layout { display: flex; gap: 16px; align-items: flex-start; }
  #map { height: 600px; flex: 1; min-width: 0; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); }
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
  #panel {
    width: 280px; flex: none; height: 600px; overflow-y: auto;
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px;
    font-size: 13px;
  }
  #panel h3 { margin: 0 0 12px; font-size: 15px; font-weight: 600; }
  #panel .panel-row { margin-bottom: 10px; }
  #panel .panel-label {
    display: block; color: var(--text-muted); font-weight: 600; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 2px;
  }
  #panel .panel-placeholder { color: var(--text-muted); }
</style>
<h1>Mapa de rutas</h1>

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

<div class="map-layout">
  <div id="map"></div>
  <div id="panel"><p class="panel-placeholder">Selecciona un negocio en el mapa para ver el detalle.</p></div>
</div>

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

  const estadoLabels = {sin_contactar: "Sin contactar", contactado: "Contactado",
                         respondio: "Respondió", convertido: "Convertido"};

  function escapeHtml(s) {
    if (!s) return "";
    return String(s).replace(/[&<>"']/g, function(c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  function panelRow(label, value) {
    if (!value) return "";
    return '<div class="panel-row"><span class="panel-label">' + label + '</span>' + escapeHtml(value) + '</div>';
  }

  function estadoSelectHtml(lead) {
    var options = Object.keys(estadoLabels).map(function(value) {
      var selected = value === lead.outreach_status ? " selected" : "";
      return '<option value="' + value + '"' + selected + '>' + estadoLabels[value] + '</option>';
    }).join("");
    return '<div class="panel-row"><span class="panel-label">Estado</span>' +
      '<form class="estado-form"><select class="estado-select estado-' + lead.outreach_status + '">' +
      options + '</select></form></div>';
  }

  function renderPanel(lead, prefix) {
    var panel = document.getElementById('panel');
    var ratingText = (lead.rating != null && lead.reviews_count != null)
      ? lead.rating + " (" + lead.reviews_count + " reviews)"
      : (lead.rating != null ? String(lead.rating) : (lead.reviews_count != null ? lead.reviews_count + " reviews" : ""));
    var categoriaText = lead.categorias ? lead.categorias.join(", ") : lead.categoria;
    var leadIds = lead.lead_ids || (lead.id ? [lead.id] : []);
    panel.innerHTML =
      "<h3>" + (prefix || "") + escapeHtml(lead.negocio) + "</h3>" +
      panelRow("Categoria", categoriaText) +
      panelRow("Direccion", lead.direccion) +
      panelRow("Telefono", lead.telefono) +
      panelRow("Rating", ratingText) +
      (leadIds.length ? estadoSelectHtml(lead) : "");

    var select = panel.querySelector(".estado-select");
    if (select) {
      select.addEventListener('change', function() {
        var nuevoEstado = select.value;
        select.className = 'estado-select estado-' + nuevoEstado;
        Promise.all(leadIds.map(function(leadId) {
          return fetch('/rutas/crm/' + leadId + '/estado', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'estado=' + encodeURIComponent(nuevoEstado)
          });
        })).then(function() { lead.outreach_status = nuevoEstado; });
      });
    }
  }

  allLeads.forEach(function(lead) {
    const layer = categoryLayers[lead.categoria];
    if (!layer) return;
    const color = categoryColors[lead.categoria];
    L.circleMarker([lead.lat, lead.lng], {
      radius: 4, color: color, fillColor: color, fillOpacity: 0.6, weight: 1
    }).on('click', function() { renderPanel(lead); }).addTo(layer);
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
          }).on('click', function() { renderPanel(p, i === 0 ? "Origen — " : (i + ". ")); }).addTo(layerGroup);
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


OUTREACH_STATUS_LABELS = {
    "sin_contactar": "Sin contactar",
    "contactado": "Contactado",
    "respondio": "Respondió",
    "convertido": "Convertido",
}

PAGE_CRM = """
<!doctype html>
<title>CRM de leads</title>
""" + BASE_STYLE + NAV_LINKS + """
<style>
  .crm-toolbar {
    display: flex; justify-content: space-between; align-items: flex-end;
    gap: 16px; flex-wrap: wrap; margin-bottom: 12px;
  }
  .filtros-form { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 0; }
  .filtros-form label { margin-bottom: 0; }
  .crm-summary { color: var(--text-muted); font-size: 13px; margin: 0 0 10px; }
  .pager { display: flex; justify-content: space-between; margin-top: 12px; font-size: 13px; }
</style>
<h1>CRM de leads</h1>

<div class="crm-toolbar">
  <form method="get" class="filtros-form">
    <label>Categoria:
      <select name="categoria">
        <option value="">Todas</option>
        {% for cat in ["Repuestos", "Fundas", "Telefonos"] %}
          <option value="{{ cat }}" {% if categoria == cat %}selected{% endif %}>{{ cat }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Estado:
      <select name="estado">
        <option value="">Todos</option>
        {% for value, label in status_labels.items() %}
          <option value="{{ value }}" {% if estado == value %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Reviews minimas:
      <input type="number" name="min_reviews" min="0" step="1" value="{{ min_reviews or '' }}" style="width:80px;">
    </label>
    <label>Rating minimo:
      <input type="number" name="min_rating" min="0" max="5" step="0.1" value="{{ min_rating or '' }}" style="width:80px;">
    </label>
    <button type="submit">Filtrar</button>
  </form>
  <a class="btn-secondary" href="{{ url_for('rutas.exportar_crm_csv', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating) }}">
    Exportar CSV
  </a>
</div>

<p class="crm-summary">{{ total }} lead{{ "s" if total != 1 else "" }} — pagina {{ page }} de {{ total_pages }}</p>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Categoria</th><th>Negocio</th><th>Telefono</th><th>Direccion</th>
      <th>Reviews</th><th>Rating</th><th>Geo</th><th>Estado</th>
    </tr>
  </thead>
  <tbody>
    {% for lead in leads %}
    <tr>
      <td><span class="cat-dot cat-{{ lead.categoria }}"></span>{{ lead.categoria }}</td>
      <td title="{{ lead.negocio }}">{{ lead.negocio }}</td>
      <td>{{ lead.telefono or "-" }}</td>
      <td title="{{ lead.direccion or '' }}">{{ lead.direccion or "-" }}</td>
      <td>{{ lead.reviews_count if lead.reviews_count is not none else "-" }}</td>
      <td>{{ lead.rating if lead.rating is not none else "-" }}</td>
      <td>
        {% if lead.lat %}
          <span class="badge badge-ok">Si</span>
        {% else %}
          <span class="badge badge-no">No</span>
        {% endif %}
      </td>
      <td>
        <form method="post" class="estado-form" action="{{ url_for('rutas.actualizar_estado', lead_id=lead.id) }}">
          <select name="estado" class="estado-select estado-{{ lead.outreach_status }}"
                  onchange="this.className = 'estado-select estado-' + this.value; this.form.submit();">
            {% for value, label in status_labels.items() %}
              <option value="{{ value }}" {% if lead.outreach_status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
          </select>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="8">No hay leads para este filtro.</td></tr>
    {% endfor %}
  </tbody>
</table>
</div>

<div class="pager">
  <span>
    {% if page > 1 %}
      <a href="{{ url_for('rutas.crm', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating, page=page-1) }}">&laquo; Anterior</a>
    {% endif %}
  </span>
  <span>
    {% if page < total_pages %}
      <a href="{{ url_for('rutas.crm', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating, page=page+1) }}">Siguiente &raquo;</a>
    {% endif %}
  </span>
</div>
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
        categoria = request.form.get("categoria", "").strip() or None
        min_reviews = request.form.get("min_reviews", type=int)
        min_rating = request.form.get("min_rating", type=float)
        resultado = batch.generate_lote(
            conn, origen_texto, n, origen_coords=origen_coords, categoria=categoria,
            min_reviews=min_reviews, min_rating=min_rating,
        )
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
    return redirect(request.referrer or url_for("rutas.historial"))


@rutas_bp.route("/lotes/<int:lote_id>/compartir", methods=["POST"])
def compartir_lote(lote_id: int):
    conn = _conn()
    try:
        db.mark_lote_compartido(conn, lote_id)
    finally:
        conn.close()
    return redirect(request.referrer or url_for("rutas.historial"))


@rutas_bp.route("/lotes/<int:lote_id>", methods=["GET"])
def detalle_lote(lote_id: int):
    conn = _conn()
    try:
        lote = db.get_lote(conn, lote_id)
        if lote is None:
            return render_template_string(PAGE_ERROR, error=f"Lote #{lote_id} no encontrado"), 404
        sublotes = []
        for sublote in db.get_sublotes_for_lote(conn, lote_id):
            sublotes.append({
                "id": sublote["id"],
                "orden": sublote["orden"],
                "maps_link": sublote["maps_link"],
                "compartido_en": sublote["compartido_en"],
                "leads": db.get_sublote_stops(conn, sublote["id"]),
            })
    finally:
        conn.close()
    resultado = {
        "lote_id": lote["id"],
        "origen_texto": lote["origen_texto"],
        "categoria": lote["categoria"],
        "tamano_solicitado": lote["tamano_solicitado"],
        "tamano_real": lote["tamano_real"],
        "sublotes": sublotes,
    }
    return render_template_string(PAGE_RESULTADO, resultado=resultado)


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


@rutas_bp.route("/crm", methods=["GET"])
def crm():
    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()
    min_reviews = request.args.get("min_reviews", type=int)
    min_rating = request.args.get("min_rating", type=float)
    page = max(1, request.args.get("page", 1, type=int))
    conn = _conn()
    try:
        leads = db.get_crm_leads(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating, page=page,
        )
        total = db.count_crm_leads(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating,
        )
    finally:
        conn.close()
    total_pages = max(1, -(-total // db.CRM_PAGE_SIZE))  # ceil division
    return render_template_string(
        PAGE_CRM,
        leads=leads,
        categoria=categoria,
        estado=estado,
        min_reviews=min_reviews,
        min_rating=min_rating,
        status_labels=OUTREACH_STATUS_LABELS,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@rutas_bp.route("/crm/exportar", methods=["GET"])
def exportar_crm_csv():
    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()
    min_reviews = request.args.get("min_reviews", type=int)
    min_rating = request.args.get("min_rating", type=float)
    conn = _conn()
    try:
        leads = db.get_crm_leads_all(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating,
        )
    finally:
        conn.close()

    output = io.StringIO()
    output.write("﻿")  # BOM so Excel/Sheets detect UTF-8 on import
    writer = csv.writer(output)
    writer.writerow([
        "Categoria", "Negocio", "Telefono", "Direccion", "Reviews", "Rating",
        "Geocodificado", "Estado de contacto",
    ])
    for lead in leads:
        writer.writerow([
            lead["categoria"],
            lead["negocio"],
            lead["telefono"] or "",
            lead["direccion"] or "",
            lead["reviews_count"] if lead["reviews_count"] is not None else "",
            lead["rating"] if lead["rating"] is not None else "",
            "Si" if lead["lat"] is not None else "No",
            OUTREACH_STATUS_LABELS.get(lead["outreach_status"], lead["outreach_status"]),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=crm_leads.csv"},
    )


@rutas_bp.route("/crm/<int:lead_id>/estado", methods=["POST"])
def actualizar_estado(lead_id: int):
    estado = request.form.get("estado", "")
    if estado not in db.OUTREACH_STATUSES:
        return render_template_string(PAGE_ERROR, error=f"Estado invalido: {estado}"), 400
    conn = _conn()
    try:
        db.set_outreach_status(conn, lead_id, estado)
    finally:
        conn.close()
    return redirect(request.referrer or url_for("rutas.crm"))


@rutas_bp.route("/admin/restore-db", methods=["POST"])
def admin_restore_db():
    """One-time-use: uploads a local leads_routes.db onto this deployment's
    persistent volume. Guarded by ADMIN_RESTORE_TOKEN -- unset that env var
    (or remove this route) once the initial data migration is done."""
    expected_token = os.environ.get("ADMIN_RESTORE_TOKEN", "")
    if not expected_token or request.form.get("token", "") != expected_token:
        return "No autorizado.", 403

    uploaded = request.files.get("db_file")
    if not uploaded:
        return "Falta el archivo db_file.", 400

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as f:
        header = f.read(len(SQLITE_MAGIC))
    if header != SQLITE_MAGIC:
        os.remove(tmp_path)
        return "El archivo no es una base SQLite valida.", 400

    shutil.move(tmp_path, db.DB_PATH)
    return "Base restaurada correctamente.", 200
