"""
FixLab Lead Prospector - Interfaz Web Local
Correr: python app.py  ->  abrir http://localhost:5000
"""

import subprocess
import sys
import os
import threading
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, Response

import routes_app
import routes_db

app = Flask(__name__)

routes_db.init_db()
app.register_blueprint(routes_app.rutas_bp)

HISTORIAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial.json")

ZONAS_PREDEFINIDAS = [
    # CABA - completa
    ("CABA — Completa",                   "Ciudad Autonoma de Buenos Aires, Argentina"),
    # CABA - por comuna
    ("CABA — Comuna 1 (Retiro, San Nicolas, Puerto Madero, San Telmo, Monserrat, Constitucion)", "Comuna 1, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 2 (Recoleta)",                    "Comuna 2, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 3 (Balvanera, San Cristobal)",    "Comuna 3, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 4 (La Boca, Barracas, Parque Patricios, Nueva Pompeya)", "Comuna 4, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 5 (Almagro, Boedo)",              "Comuna 5, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 6 (Caballito)",                   "Comuna 6, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 7 (Flores, Parque Chacabuco)",    "Comuna 7, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 8 (Villa Soldati, Villa Riachuelo, Villa Lugano)", "Comuna 8, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 9 (Liniers, Mataderos, Parque Avellaneda)", "Comuna 9, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 10 (Villa Real, Monte Castro, Versalles, Floresta, Velez Sarsfield, Villa Luro)", "Comuna 10, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 11 (Villa General Mitre, Villa Devoto, Villa del Parque, Villa Santa Rita)", "Comuna 11, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 12 (Coghlan, Saavedra, Villa Urquiza, Villa Pueyrredon)", "Comuna 12, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 13 (Belgrano, Nunez, Colegiales)",  "Comuna 13, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 14 (Palermo)",                    "Comuna 14, Ciudad Autonoma de Buenos Aires, Argentina"),
    ("CABA — Comuna 15 (Chacarita, Villa Crespo, Paternal, Villa Ortuzar, Agronomia, Parque Chas)", "Comuna 15, Ciudad Autonoma de Buenos Aires, Argentina"),
    # CABA - por barrio
    ("CABA — Barrios C1 — Retiro",              "Retiro, Buenos Aires, Argentina"),
    ("CABA — Barrios C1 — San Nicolas",         "San Nicolas, Buenos Aires, Argentina"),
    ("CABA — Barrios C1 — Puerto Madero",       "Puerto Madero, Buenos Aires, Argentina"),
    ("CABA — Barrios C1 — San Telmo",           "San Telmo, Buenos Aires, Argentina"),
    ("CABA — Barrios C1 — Monserrat",           "Monserrat, Buenos Aires, Argentina"),
    ("CABA — Barrios C1 — Constitucion",        "Constitucion, Buenos Aires, Argentina"),
    ("CABA — Barrios C2 — Recoleta",            "Recoleta, Buenos Aires, Argentina"),
    ("CABA — Barrios C3 — Balvanera",           "Balvanera, Buenos Aires, Argentina"),
    ("CABA — Barrios C3 — San Cristobal",       "San Cristobal, Buenos Aires, Argentina"),
    ("CABA — Barrios C4 — La Boca",             "La Boca, Buenos Aires, Argentina"),
    ("CABA — Barrios C4 — Barracas",            "Barracas, Buenos Aires, Argentina"),
    ("CABA — Barrios C4 — Parque Patricios",    "Parque Patricios, Buenos Aires, Argentina"),
    ("CABA — Barrios C4 — Nueva Pompeya",       "Nueva Pompeya, Buenos Aires, Argentina"),
    ("CABA — Barrios C5 — Almagro",             "Almagro, Buenos Aires, Argentina"),
    ("CABA — Barrios C5 — Boedo",               "Boedo, Buenos Aires, Argentina"),
    ("CABA — Barrios C6 — Caballito",           "Caballito, Buenos Aires, Argentina"),
    ("CABA — Barrios C7 — Flores",              "Flores, Buenos Aires, Argentina"),
    ("CABA — Barrios C7 — Parque Chacabuco",    "Parque Chacabuco, Buenos Aires, Argentina"),
    ("CABA — Barrios C8 — Villa Soldati",       "Villa Soldati, Buenos Aires, Argentina"),
    ("CABA — Barrios C8 — Villa Riachuelo",     "Villa Riachuelo, Buenos Aires, Argentina"),
    ("CABA — Barrios C8 — Villa Lugano",        "Villa Lugano, Buenos Aires, Argentina"),
    ("CABA — Barrios C9 — Liniers",             "Liniers, Buenos Aires, Argentina"),
    ("CABA — Barrios C9 — Mataderos",           "Mataderos, Buenos Aires, Argentina"),
    ("CABA — Barrios C9 — Parque Avellaneda",   "Parque Avellaneda, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Villa Real",         "Villa Real, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Monte Castro",       "Monte Castro, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Versalles",          "Versalles, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Floresta",           "Floresta, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Velez Sarsfield",    "Velez Sarsfield, Buenos Aires, Argentina"),
    ("CABA — Barrios C10 — Villa Luro",         "Villa Luro, Buenos Aires, Argentina"),
    ("CABA — Barrios C11 — Villa Gral Mitre",   "Villa General Mitre, Buenos Aires, Argentina"),
    ("CABA — Barrios C11 — Villa Devoto",       "Villa Devoto, Buenos Aires, Argentina"),
    ("CABA — Barrios C11 — Villa del Parque",   "Villa del Parque, Buenos Aires, Argentina"),
    ("CABA — Barrios C11 — Villa Santa Rita",   "Villa Santa Rita, Buenos Aires, Argentina"),
    ("CABA — Barrios C12 — Coghlan",            "Coghlan, Buenos Aires, Argentina"),
    ("CABA — Barrios C12 — Saavedra",           "Saavedra, Buenos Aires, Argentina"),
    ("CABA — Barrios C12 — Villa Urquiza",      "Villa Urquiza, Buenos Aires, Argentina"),
    ("CABA — Barrios C12 — Villa Pueyrredon",   "Villa Pueyrredon, Buenos Aires, Argentina"),
    ("CABA — Barrios C13 — Belgrano",           "Belgrano, Buenos Aires, Argentina"),
    ("CABA — Barrios C13 — Nunez",              "Nunez, Buenos Aires, Argentina"),
    ("CABA — Barrios C13 — Colegiales",         "Colegiales, Buenos Aires, Argentina"),
    ("CABA — Barrios C14 — Palermo",            "Palermo, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — Chacarita",          "Chacarita, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — Villa Crespo",       "Villa Crespo, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — La Paternal",        "La Paternal, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — Villa Ortuzar",      "Villa Ortuzar, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — Agronomia",          "Agronomia, Buenos Aires, Argentina"),
    ("CABA — Barrios C15 — Parque Chas",        "Parque Chas, Buenos Aires, Argentina"),
    # GBA Norte
    ("GBA Norte — San Isidro",        "San Isidro, Buenos Aires, Argentina"),
    ("GBA Norte — Vicente Lopez",      "Vicente Lopez, Buenos Aires, Argentina"),
    ("GBA Norte — Tigre",              "Tigre, Buenos Aires, Argentina"),
    ("GBA Norte — San Martin",         "San Martin, Buenos Aires, Argentina"),
    ("GBA Norte — Tres de Febrero",    "Tres de Febrero, Buenos Aires, Argentina"),
    ("GBA Norte — Hurlingham",         "Hurlingham, Buenos Aires, Argentina"),
    # GBA Sur
    ("GBA Sur — Quilmes",              "Quilmes, Buenos Aires, Argentina"),
    ("GBA Sur — Avellaneda",           "Avellaneda, Buenos Aires, Argentina"),
    ("GBA Sur — Lomas de Zamora",      "Lomas de Zamora, Buenos Aires, Argentina"),
    ("GBA Sur — Lanus",                "Lanus, Buenos Aires, Argentina"),
    ("GBA Sur — Berazategui",          "Berazategui, Buenos Aires, Argentina"),
    ("GBA Sur — Florencio Varela",     "Florencio Varela, Buenos Aires, Argentina"),
    ("GBA Sur — Almirante Brown",      "Almirante Brown, Buenos Aires, Argentina"),
    ("GBA Sur — Esteban Echeverria",   "Esteban Echeverria, Buenos Aires, Argentina"),
    # GBA Oeste
    ("GBA Oeste — Moron",              "Moron, Buenos Aires, Argentina"),
    ("GBA Oeste — La Matanza",         "La Matanza, Buenos Aires, Argentina"),
    ("GBA Oeste — Merlo",              "Merlo, Buenos Aires, Argentina"),
    ("GBA Oeste — Moreno",             "Moreno, Buenos Aires, Argentina"),
    ("GBA Oeste — Ituzaingo",          "Ituzaingo, Buenos Aires, Argentina"),
    # Interior
    ("Interior — Cordoba",             "Cordoba, Argentina"),
    ("Interior — Rosario",             "Rosario, Santa Fe, Argentina"),
    ("Interior — Mar del Plata",       "Mar del Plata, Buenos Aires, Argentina"),
    ("Interior — Mendoza",             "Mendoza, Argentina"),
    ("Interior — Tucuman",             "San Miguel de Tucuman, Tucuman, Argentina"),
    ("Interior — Salta",               "Salta, Argentina"),
    ("Interior — Neuquen",             "Neuquen, Argentina"),
    ("Interior — Bahia Blanca",        "Bahia Blanca, Buenos Aires, Argentina"),
]

SEARCH_TERMS_COUNT = 6
COST_PER_RESULT    = 0.002

CATEGORIAS_UI = {
    "repuestos": {
        "label": "Repuestos y Reparacion",
        "terms_count": 6,
        "ig_distributor_count": 8,
        "ig_has_distributors": True,
        "ig_keywords": "fixlab, fix, tech, lab, reparaciones, cell, service, repuestos",
    },
    "fundas": {
        "label": "Fundas",
        "terms_count": 6,
        "ig_distributor_count": 0,
        "ig_has_distributors": False,
        "ig_keywords": "accesorios para celular, accesorios iphone, local accesorios movil, tienda accesorios celular, venta accesorios celulares, accesorios apple",
    },
    "telefonos": {
        "label": "Telefonos",
        "terms_count": 6,
        "ig_distributor_count": 0,
        "ig_has_distributors": False,
        "ig_keywords": "iphone usado, iphone seminuevo, iphone reacondicionado, compra venta iphone, venta iphone, celulares iphone",
    },
}


# ── Historial ──────────────────────────────────

def leer_historial():
    if not os.path.exists(HISTORIAL_FILE):
        return []
    try:
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def guardar_historial(entrada):
    h = leer_historial()
    h.insert(0, entrada)
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(h[:50], f, ensure_ascii=False, indent=2)


# ── HTML ───────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FixLab Lead Prospector</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #F8FAFC; color: #334155; }

  .header { background: #0F172A; color: white; padding: 20px 32px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .header span { font-size: 13px; color: #94A3B8; }

  .container { max-width: 720px; margin: 40px auto; padding: 0 20px 60px; }

  .card { background: white; border-radius: 16px; padding: 28px; margin-bottom: 20px; border: 1px solid #D8EBF2; }
  .card h2 { font-size: 15px; font-weight: 600; margin-bottom: 18px; color: #0F172A; }

  label { display: block; font-size: 13px; font-weight: 500; color: #64748B; margin-bottom: 6px; }
  select, input[type=text], input[type=number] {
    width: 100%; padding: 10px 14px; border: 1px solid #D8EBF2; border-radius: 8px;
    font-size: 14px; color: #334155; background: white; outline: none; transition: border-color .15s;
  }
  select:focus, input:focus { border-color: #0284C7; }

  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }

  .cost-box { background: #E8F4F8; border: 1px solid #D8EBF2; border-radius: 8px; padding: 14px 18px; margin-top: 18px; display: flex; justify-content: space-between; align-items: center; }
  .cost-box .label { font-size: 13px; color: #64748B; }
  .cost-box .value { font-size: 20px; font-weight: 700; color: #0F172A; }
  .cost-box .sub { font-size: 12px; color: #64748B; text-align: right; }

  .btn { width: 100%; padding: 14px; background: #0284C7; color: white; border: none; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 20px; transition: background .15s; }
  .btn:hover:not(:disabled) { background: #0369A1; }
  .btn:disabled { background: #D8EBF2; cursor: not-allowed; }
  .btn.secondary { background: white; color: #334155; border: 1px solid #D8EBF2; margin-top: 10px; font-size: 13px; padding: 10px; }
  .btn.secondary:hover:not(:disabled) { background: #E8F4F8; }

  .log-box { background: #0F172A; border-radius: 8px; padding: 16px; font-family: 'Courier New', monospace; font-size: 12px; color: #ccc; height: 220px; overflow-y: auto; display: none; margin-top: 20px; }
  .log-box.visible { display: block; }
  .log-line { margin-bottom: 4px; line-height: 1.5; }
  .log-line.ok  { color: #4ade80; }
  .log-line.err { color: #f87171; }
  .log-line.inf { color: #60a5fa; }

  /* Resultados */
  .results { display: none; margin-top: 20px; }
  .results.visible { display: block; }

  .semaforo { border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; display: flex; align-items: center; gap: 16px; }
  .semaforo.verde    { background: #f0fdf4; border: 1px solid #bbf7d0; }
  .semaforo.amarillo { background: #fefce8; border: 1px solid #fde68a; }
  .semaforo.rojo     { background: #fef2f2; border: 1px solid #fecaca; }
  .semaforo .dot { width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0; }
  .semaforo.verde    .dot { background: #16a34a; }
  .semaforo.amarillo .dot { background: #d97706; }
  .semaforo.rojo     .dot { background: #dc2626; }
  .semaforo .sem-title { font-size: 14px; font-weight: 700; }
  .semaforo.verde    .sem-title { color: #15803d; }
  .semaforo.amarillo .sem-title { color: #b45309; }
  .semaforo.rojo     .sem-title { color: #b91c1c; }
  .semaforo .sem-sub { font-size: 12px; color: #64748B; margin-top: 2px; }

  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
  .stat { background: #F8FAFC; border: 1px solid #D8EBF2; border-radius: 8px; padding: 14px; text-align: center; }
  .stat .n { font-size: 22px; font-weight: 700; color: #0F172A; }
  .stat .l { font-size: 11px; color: #64748B; margin-top: 2px; }
  .stat.highlight { background: #0284C7; border-color: #0284C7; }
  .stat.highlight .n, .stat.highlight .l { color: white; }

  .zona-hist-row { display:flex; justify-content:space-between; align-items:center; padding:3px 0; border-bottom:1px solid #eee; }
  .zona-hist-row:last-child { border-bottom:none; }
  .zona-hist-cat { display:inline-block; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:600; margin-right:4px; }
  .zona-hist-cat.repuestos { background:#dbeafe; color:#1d4ed8; }
  .zona-hist-cat.fundas    { background:#fce7f3; color:#9d174d; }
  .zona-hist-cat.telefonos { background:#d1fae5; color:#065f46; }

  /* Tabla resumen zonas */
  .zona-cobertura-wrap { margin-top:10px; }
  .zona-cobertura-wrap summary { cursor:pointer; font-size:12px; color:#64748B; user-select:none; }
  .zona-cobertura-table { width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }
  .zona-cobertura-table th { text-align:left; padding:5px 8px; background:#F8FAFC; font-weight:600; color:#64748B; border-bottom:1px solid #D8EBF2; }
  .zona-cobertura-table td { padding:5px 8px; border-bottom:1px solid #eee; color:#334155; }
  .zona-cobertura-table tr:last-child td { border-bottom:none; }
  .pct-badge { display:inline-block; padding:1px 7px; border-radius:10px; font-size:11px; font-weight:700; }
  .pct-verde    { background:#dcfce7; color:#15803d; }
  .pct-amarillo { background:#fef9c3; color:#854d0e; }
  .pct-rojo     { background:#fee2e2; color:#b91c1c; }
  .zona-dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:5px; }
  .zona-dot.nueva    { background:#d1d5db; }
  .zona-dot.hecha    { background:#16a34a; }

  .tipo-list { list-style: none; margin-bottom: 20px; }
  .tipo-list li { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
  .tipo-list li:last-child { border-bottom: none; }
  .tipo-list .count { font-weight: 600; }

  /* Tabla leads nuevos */
  .leads-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .leads-header h3 { font-size: 14px; font-weight: 600; }
  .leads-filter { padding: 6px 10px; border: 1px solid #D8EBF2; border-radius: 6px; font-size: 12px; width: 180px; }
  .leads-table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid #D8EBF2; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { background: #F8FAFC; padding: 10px 12px; text-align: left; font-weight: 600; color: #64748B; border-bottom: 1px solid #D8EBF2; white-space: nowrap; }
  td { padding: 9px 12px; border-bottom: 1px solid #F8FAFC; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #E8F4F8; }
  .badge { display: inline-block; padding: 2px 7px; border-radius: 20px; font-size: 10px; font-weight: 600; white-space: nowrap; }
  .badge.cadena   { background: #dbeafe; color: #1d4ed8; }
  .badge.alto     { background: #fef9c3; color: #854d0e; }
  .badge.chico    { background: #f3f4f6; color: #374151; }
  .badge.apple    { background: #dcfce7; color: #15803d; }
  .badge.multi    { background: #f3f4f6; color: #6b7280; }
  .maps-link { color: #0284C7; text-decoration: none; font-size: 11px; }
  .maps-link:hover { text-decoration: underline; }

  /* Tab selector */
  .tab-bar { display: flex; gap: 4px; margin-bottom: 20px; background: white; border: 1px solid #D8EBF2; border-radius: 10px; padding: 4px; }
  .tab-btn { flex: 1; padding: 10px 8px; border: none; border-radius: 7px; font-size: 13px; font-weight: 600; cursor: pointer; background: transparent; color: #64748B; transition: all .15s; text-decoration: none; text-align: center; display: flex; align-items: center; justify-content: center; box-sizing: border-box; }
  .tab-btn.active { background: #0284C7; color: white; }
  .tab-btn:hover:not(.active) { background: #E8F4F8; color: #334155; }

  /* Historial */
  .hist-table-wrap { overflow-x: auto; overflow-y: auto; max-height: 260px; }
  .hist-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .hist-table th { padding: 8px 12px; text-align: left; font-weight: 600; color: #64748B; border-bottom: 2px solid #D8EBF2; position: sticky; top: 0; background: white; }
  .hist-table td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
  .hist-table tr:last-child td { border-bottom: none; }
  .hist-empty { text-align: center; color: #64748B; padding: 24px; font-size: 13px; }
  .pill { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .pill.verde    { background: #dcfce7; color: #15803d; }
  .pill.amarillo { background: #fef9c3; color: #854d0e; }
  .pill.rojo     { background: #fee2e2; color: #b91c1c; }
  .pill.test     { background: #f3e8ff; color: #6b21a8; }

  .item-card {
    background: white; border: 1px solid #D8EBF2; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 10px;
  }

  .mobile-only { display: none; }
  @media (max-width: 767px) {
    .desktop-only { display: none; }
    .mobile-only { display: block; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>FixLab Lead Prospector</h1>
  <span>Google Maps -> Google Sheets</span>
</div>

<div class="container">

  <!-- TAB SELECTOR -->
  <div class="tab-bar">
    <button class="tab-btn active" id="tab-repuestos" onclick="switchTab('repuestos')">Repuestos y Reparacion</button>
    <button class="tab-btn" id="tab-fundas"    onclick="switchTab('fundas')">Fundas</button>
    <button class="tab-btn" id="tab-telefonos" onclick="switchTab('telefonos')">Telefonos</button>
    <a class="tab-btn" id="tab-rutas" href="/rutas/">Rutas</a>
  </div>

  <!-- FORMULARIO -->
  <div class="card">
    <h2>Nueva busqueda &mdash; <span id="catLabel">Repuestos y Reparacion</span></h2>

    <label>Zona geografica</label>
    <select id="zonaSelect" onchange="onZonaSelect()">
      <option value="">-- Seleccionar zona --</option>
      {% for group, items in zona_groups %}
      <optgroup label="{{ group }}">
        {% for label, value in items %}
        <option value="{{ value }}">{{ label }}</option>
        {% endfor %}
      </optgroup>
      {% endfor %}
      <option value="__custom__">Otra zona (escribir)...</option>
    </select>

    <div id="zonaHistorialBox" style="display:none; margin-top:12px; background:#f9f9f9; border:1px solid #e5e5e5; border-radius:8px; padding:12px 14px; font-size:12px; color:#555;">
      <div id="zonaHistorialContent"></div>
    </div>

    <div id="zonaCustomDiv" style="margin-top:10px; display:none;">
      <label>Escribir zona</label>
      <input type="text" id="zonaCustom" placeholder="ej: La Plata, Buenos Aires, Argentina">
    </div>

    <div class="row">
      <div>
        <label style="margin-top:0;">Max. resultados por busqueda</label>
        <input type="number" id="maxResults" value="150" min="10" max="500" onchange="updateCost()">
      </div>
      <div>
        <label style="margin-top:0;">Terminos de busqueda</label>
        <input type="number" id="numTerms" value="{{ search_terms_count }}" min="1" max="{{ search_terms_count }}" readonly style="background:#f5f5f5;color:#888;">
      </div>
    </div>

    <div class="cost-box">
      <div>
        <div class="label">Costo estimado maximo</div>
        <div class="value" id="costValue">$1.50 USD</div>
      </div>
      <div class="sub" id="costDetail">5 terminos x 150 resultados<br>x $0.002 por resultado</div>
    </div>

    <button class="btn" id="btnRun150" onclick="runScript('full')" disabled>
      Completa — 5 terminos x 150 resultados (~$1.50)
    </button>
    <button class="btn secondary" id="btnRun80" onclick="runScript('eco')" disabled>
      Economica — 3 terminos x 80 resultados (~$0.48)
    </button>
    <button class="btn secondary" id="btnTest" onclick="runScript('test')" disabled>
      Prueba — 1 termino x 10 resultados (~$0.02)
    </button>

    <div class="log-box" id="logBox"></div>

    <!-- RESULTADOS -->
    <div class="results" id="resultsBox">

      <div id="semaforoBox" class="semaforo" style="display:none;">
        <div class="dot"></div>
        <div>
          <div class="sem-title" id="semTitle"></div>
          <div class="sem-sub"   id="semSub"></div>
        </div>
      </div>

      <div class="stat-grid">
        <div class="stat highlight">
          <div class="n" id="statNuevos">-</div>
          <div class="l">Leads nuevos</div>
        </div>
        <div class="stat">
          <div class="n" id="statBruto">-</div>
          <div class="l">Encontrados</div>
        </div>
        <div class="stat">
          <div class="n" id="statDup">-</div>
          <div class="l">Duplicados</div>
        </div>
        <div class="stat">
          <div class="n" id="statCosto">-</div>
          <div class="l">Costo real</div>
        </div>
      </div>

      <ul class="tipo-list" id="tipoList"></ul>

      <!-- TABLA LEADS NUEVOS -->
      <div id="leadsSection" style="display:none;">
        <div class="leads-header">
          <h3 id="leadsTitle">Leads nuevos</h3>
          <input class="leads-filter" type="text" id="leadsFilter" placeholder="Filtrar..." oninput="filtrarLeads()">
        </div>
        <div class="leads-table-wrap">
          <table id="leadsTable">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Foco</th>
                <th>Resenas</th>
                <th>Telefono</th>
                <th>Maps</th>
              </tr>
            </thead>
            <tbody id="leadsBody"></tbody>
          </table>
        </div>
      </div>

    </div>
  </div>

  <!-- HISTORIAL -->
  <div class="card">
    <h2>Historial de corridas</h2>
    <div class="hist-table-wrap">
      <table class="hist-table" id="histTable">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Fuente</th>
            <th>Zona / Hashtags</th>
            <th>Nuevos</th>
            <th>Encontrados</th>
            <th>Costo real</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody id="histBody">
          <tr><td colspan="7" class="hist-empty">Sin corridas todavia. Ejecuta una busqueda para ver el historial.</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- COBERTURA DE ZONAS -->
  <div class="card">
    <h2>Cobertura de zonas</h2>
    <p style="font-size:12px;color:#888;margin-bottom:14px;">Zonas que ya fueron scrapeadas en la categoria activa. ✓ = al menos una corrida real.</p>
    <div id="coberturaWrap">
      <table class="zona-cobertura-table">
        <thead>
          <tr>
            <th>Zona</th>
            <th>Corridas</th>
            <th>Leads nuevos</th>
            <th>% Dup</th>
            <th>Ultima corrida</th>
          </tr>
        </thead>
        <tbody id="coberturaBody">
          <tr><td colspan="5" style="color:#aaa;font-size:12px;padding:10px 8px;">Sin datos todavia.</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- INSTAGRAM -->
  <div class="card">
    <h2>Instagram &mdash; <span id="igCatLabel">Repuestos y Reparacion</span></h2>

    <div style="background:#f9f9f9;border:1px solid #e5e5e5;border-radius:8px;padding:12px 16px;margin-bottom:18px;">
      <div id="igDistribSection">
        <div style="font-size:11px;font-weight:600;color:#888;margin-bottom:6px;">DISTRIBUIDORAS DE REFERENCIA (menciones)</div>
        <div style="font-size:12px;color:#444;line-height:1.9;">
          @bhtech.ba &nbsp;@premiumcell_oficial &nbsp;@infinitcell.ar &nbsp;@todocelurepuestos<br>
          @todocelulanus &nbsp;@smartparts_repuestos &nbsp;@celupro_repuestos &nbsp;@patagoniacell
        </div>
      </div>
      <div style="font-size:11px;font-weight:600;color:#888;margin-top:10px;margin-bottom:6px;">BUSQUEDA POR KEYWORD</div>
      <div id="igKeywordsText" style="font-size:12px;color:#444;line-height:1.9;">
        fixlab, fix, tech, lab, reparaciones, cell, service, repuestos
      </div>
    </div>

    <div style="font-size:11px;font-weight:600;color:#888;margin-bottom:8px;margin-top:4px;">VIA APIFY (pago por resultado)</div>
    <button class="btn" id="btnIGFull" onclick="runInstagram('full')">
      Completa &mdash; 8 distribuidoras + keywords (~$2.00 USD estimado)
    </button>
    <button class="btn secondary" id="btnIGTest" onclick="runInstagram('test')">
      Prueba Apify &mdash; 2 distribuidoras + 1 keyword (~$0.10 USD estimado)
    </button>

    <div style="font-size:11px;font-weight:600;color:#888;margin-top:18px;margin-bottom:8px;">VIA INSTALOADER (gratis)</div>
    <button class="btn" id="btnILFull" onclick="runFollowers('full')" style="background:#1a6e3c;">
      Seguidores &mdash; 8 distribuidoras x 150 cada una (~$0.00, demora ~20min)
    </button>
    <button class="btn secondary" id="btnILTest" onclick="runFollowers('test')">
      Prueba Instaloader &mdash; 2 cuentas x 20 seguidores (~2min)
    </button>

    <div id="ilProgressWrap" style="display:none;margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-bottom:4px;">
        <span>Progreso</span><span id="ilProgressLabel">0 / 0 perfiles</span>
      </div>
      <div style="background:#2a2a2a;border-radius:4px;height:8px;overflow:hidden;">
        <div id="ilProgressBar" style="height:100%;width:0%;background:#1a6e3c;border-radius:4px;transition:width 0.3s;"></div>
      </div>
    </div>
    <div class="log-box" id="igLogBox"></div>

    <div class="results" id="igResults">
      <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr);">
        <div class="stat highlight">
          <div class="n" id="igStatNuevos">-</div>
          <div class="l">Cuentas nuevas</div>
        </div>
        <div class="stat">
          <div class="n" id="igStatBruto">-</div>
          <div class="l">Perfiles analizados</div>
        </div>
        <div class="stat">
          <div class="n" id="igStatCosto">-</div>
          <div class="l">Costo real</div>
        </div>
      </div>

      <div id="igLeadsSection" style="display:none; margin-top:16px;">
        <div class="leads-header">
          <h3 id="igLeadsTitle">Cuentas nuevas</h3>
        </div>
        <div class="leads-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cuenta</th>
                <th>Seguidores</th>
                <th>Foco</th>
                <th>Contacto</th>
                <th>Instagram</th>
              </tr>
            </thead>
            <tbody id="igLeadsBody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

</div><!-- /container -->

<script>
const COST_PER_RESULT = {{ cost_per_result }};
const CATEGORIAS = {{ categorias_json | safe }};
let allLeads = [];
let currentCat = 'repuestos';

// ── Tab selector ──────────────────────────────
function switchTab(cat) {
  currentCat = cat;
  const cfg = CATEGORIAS[cat];

  // Botones activos
  ['repuestos','fundas','telefonos'].forEach(function(c) {
    document.getElementById('tab-' + c).classList.toggle('active', c === cat);
  });

  // Labels
  document.getElementById('catLabel').textContent   = cfg.label;
  document.getElementById('igCatLabel').textContent = cfg.label;

  // Terminos count
  document.getElementById('numTerms').value = cfg.terms_count;
  document.getElementById('numTerms').max   = cfg.terms_count;
  updateCost();

  // IG: mostrar/ocultar distribuidoras
  document.getElementById('igDistribSection').style.display = cfg.ig_has_distributors ? 'block' : 'none';
  document.getElementById('igKeywordsText').textContent = cfg.ig_keywords;

  // Boton IG: actualizar label
  const btnIGFull = document.getElementById('btnIGFull');
  if (cfg.ig_has_distributors) {
    btnIGFull.textContent = 'Completa — ' + cfg.ig_distributor_count + ' distribuidoras + keywords (~$2.00 USD estimado)';
  } else {
    btnIGFull.textContent = 'Completa — busqueda por keywords (~$0.50 USD estimado)';
  }

  // Actualizar cobertura y zonas para la nueva categoria
  renderCobertura();
  actualizarSelectZonas();

  // Limpiar logs y resultados al cambiar tab
  document.getElementById('logBox').innerHTML = '';
  document.getElementById('logBox').classList.remove('visible');
  document.getElementById('resultsBox').classList.remove('visible');
  document.getElementById('igLogBox').innerHTML = '';
  document.getElementById('igLogBox').classList.remove('visible');
  document.getElementById('igResults').classList.remove('visible');
}

// ── Zona ──────────────────────────────────────
function getZona() {
  const sel = document.getElementById('zonaSelect').value;
  return sel === '__custom__' ? document.getElementById('zonaCustom').value.trim() : sel;
}
function onZonaSelect() {
  const sel = document.getElementById('zonaSelect').value;
  document.getElementById('zonaCustomDiv').style.display = sel === '__custom__' ? 'block' : 'none';
  updateButtons();
}
function updateButtons() {
  const ok = getZona().length > 3;
  document.getElementById('btnRun150').disabled = !ok;
  document.getElementById('btnRun80').disabled  = !ok;
  document.getElementById('btnTest').disabled   = !ok;
}

// ── Costo estimado ─────────────────────────────
function updateCost() {
  const max   = parseInt(document.getElementById('maxResults').value) || 150;
  const terms = parseInt(document.getElementById('numTerms').value)   || 5;
  const cost  = (max * terms * COST_PER_RESULT).toFixed(2);
  document.getElementById('costValue').textContent = '$' + cost + ' USD';
  document.getElementById('costDetail').innerHTML  = terms + ' terminos x ' + max + ' resultados<br>x $0.002 por resultado';
}

// ── Log ───────────────────────────────────────
function addLog(msg, cls) {
  const box  = document.getElementById('logBox');
  const line = document.createElement('div');
  line.className   = 'log-line ' + (cls || '');
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

// ── Correr script ─────────────────────────────
function runScript(modo) {
  const zona = getZona();
  if (!zona) return;

  const configs = {
    full: { max: 60, terms: 6, label: 'completa' },
    eco:  { max: 60, terms: 4, label: 'economica' },
    test: { max: 10,  terms: 1, label: 'prueba'    },
  };
  const cfg = configs[modo];

  document.getElementById('logBox').innerHTML = '';
  document.getElementById('logBox').classList.add('visible');
  document.getElementById('resultsBox').classList.remove('visible');
  document.getElementById('btnRun150').disabled = true;
  document.getElementById('btnRun80').disabled  = true;
  document.getElementById('btnTest').disabled   = true;

  addLog('Iniciando busqueda ' + cfg.label + '...', 'inf');

  const src = new EventSource('/run?zona=' + encodeURIComponent(zona) + '&max=' + cfg.max + '&terms=' + cfg.terms + '&test=' + (modo === 'test') + '&categoria=' + currentCat);

  src.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'log') {
      const cls = data.msg.includes('[OK]') ? 'ok' : data.msg.includes('ERROR') ? 'err' : '';
      addLog(data.msg, cls);
    }
    if (data.type === 'done') {
      src.close();
      document.getElementById('btnRun150').disabled = false;
      document.getElementById('btnRun80').disabled  = false;
      document.getElementById('btnTest').disabled   = false;
      if (data.error) {
        addLog('ERROR: ' + data.error, 'err');
      } else {
        showResults(data.summary, modo === 'test');
        cargarHistorial();
      }
    }
  };

  src.onerror = function() {
    src.close();
    addLog('Error de conexion con el servidor.', 'err');
    document.getElementById('btnRun150').disabled = false;
    document.getElementById('btnRun80').disabled  = false;
    document.getElementById('btnTest').disabled   = false;
  };
}

// ── Mostrar resultados ────────────────────────
function showResults(s, testMode) {
  const bruto  = s.bruto  || 0;
  const nuevos = s.nuevos || 0;
  const dup    = bruto - nuevos;
  const pctDup = bruto > 0 ? Math.round((dup / bruto) * 100) : 0;
  const costo  = s.costo_real != null ? '$' + s.costo_real.toFixed(3) : '$' + (bruto * {{ cost_per_result }}).toFixed(3);

  document.getElementById('statNuevos').textContent = nuevos;
  document.getElementById('statBruto').textContent  = bruto;
  document.getElementById('statDup').textContent    = dup + ' (' + pctDup + '%)';
  document.getElementById('statCosto').textContent  = costo;

  // Semaforo
  const box = document.getElementById('semaforoBox');
  box.style.display = 'flex';
  box.className = 'semaforo';
  let color, title, sub;
  if (testMode) {
    color = 'verde'; title = 'Modo prueba completado';
    sub = 'Resultado de muestra. Correr busqueda completa para datos reales.';
  } else if (pctDup < 40) {
    color = 'verde';    title = 'Zona con potencial';
    sub = pctDup + '% duplicados — vale la pena volver a buscar en esta zona.';
  } else if (pctDup < 70) {
    color = 'amarillo'; title = 'Zona parcialmente cubierta';
    sub = pctDup + '% duplicados — quedan leads pero la zona se esta agotando.';
  } else {
    color = 'rojo';     title = 'Zona practicamente agotada';
    sub = pctDup + '% duplicados — conviene pasar a una zona nueva.';
  }
  box.classList.add(color);
  document.getElementById('semTitle').textContent = title;
  document.getElementById('semSub').textContent   = sub;

  // Desglose tipos
  const list = document.getElementById('tipoList');
  list.innerHTML = '';
  for (const [tipo, count] of Object.entries(s.tipos || {})) {
    const li = document.createElement('li');
    li.innerHTML = '<span>' + tipo + '</span><span class="count">' + count + '</span>';
    list.appendChild(li);
  }

  // Tabla leads nuevos
  allLeads = s.leads || [];
  renderLeads(allLeads);

  document.getElementById('resultsBox').classList.add('visible');
}

// ── Tabla leads ───────────────────────────────
function tipoBadge(tipo) {
  if (!tipo) return '';
  if (tipo === 'Cadena') return '<span class="badge cadena">Cadena</span>';
  if (tipo.includes('alto'))  return '<span class="badge alto">Alto volumen</span>';
  return '<span class="badge chico">Chico/Med</span>';
}
function focoBadge(foco) {
  if (foco === 'Si') return '<span class="badge apple">Apple</span>';
  return '<span class="badge multi">Multimarca</span>';
}

function renderLeads(leads) {
  const sec   = document.getElementById('leadsSection');
  const tbody = document.getElementById('leadsBody');
  const title = document.getElementById('leadsTitle');
  tbody.innerHTML = '';

  if (!leads || leads.length === 0) {
    sec.style.display = 'none';
    return;
  }

  title.textContent = leads.length + ' leads nuevos agregados';
  leads.forEach(function(l) {
    const tr = document.createElement('tr');
    const mapsLink = l.Maps_URL
      ? '<a class="maps-link" href="' + l.Maps_URL + '" target="_blank">Ver</a>'
      : '-';
    tr.innerHTML =
      '<td><strong>' + (l.Negocio || '') + '</strong>' +
        (l.Direccion ? '<br><span style="color:#888;font-size:11px">' + l.Direccion + '</span>' : '') +
      '</td>' +
      '<td>' + tipoBadge(l.Tipo) + '</td>' +
      '<td>' + focoBadge(l.Foco_Apple) + '</td>' +
      '<td>' + (l.Resenas || 0) + '</td>' +
      '<td style="white-space:nowrap">' + (l.Telefono || '-') + '</td>' +
      '<td>' + mapsLink + '</td>';
    tbody.appendChild(tr);
  });

  sec.style.display = 'block';
}

function filtrarLeads() {
  const q = document.getElementById('leadsFilter').value.toLowerCase();
  if (!q) { renderLeads(allLeads); return; }
  const filtrados = allLeads.filter(function(l) {
    return (l.Nombre      || '').toLowerCase().includes(q) ||
           (l.Direccion   || '').toLowerCase().includes(q) ||
           (l.Tipo        || '').toLowerCase().includes(q) ||
           (l.Telefono    || '').toLowerCase().includes(q);
  });
  renderLeads(filtrados);
}

// ── Cobertura de zonas ────────────────────────
var zonaStats = {};  // { "zona|categoria": { corridas, nuevos, ultima } }

function buildZonaStats(h) {
  zonaStats = {};
  if (!h) return;
  // historial viene ordenado mas nuevo primero
  h.filter(function(r) { return r.fuente === 'Maps' && !r.test; }).forEach(function(r) {
    var key = (r.zona || '') + '|' + (r.categoria || 'repuestos');
    if (!zonaStats[key]) {
      zonaStats[key] = {
        corridas: 0, nuevos: 0, bruto: 0, ultima: '',
        ultima_nuevos: 0, ultima_bruto: 0  // datos solo de la ultima corrida
      };
    }
    var s = zonaStats[key];
    s.corridas++;
    s.nuevos += (r.nuevos || 0);
    s.bruto  += (r.bruto  || 0);
    // Como el historial viene de mas nuevo a mas viejo, la primera vez que vemos
    // esta zona es la corrida mas reciente
    if (s.corridas === 1) {
      s.ultima        = r.fecha;
      s.ultima_nuevos = r.nuevos || 0;
      s.ultima_bruto  = r.bruto  || 0;
    }
  });
}

function onZonaSelect() {
  var sel = document.getElementById('zonaSelect');
  var val = sel.value;
  var box = document.getElementById('zonaHistorialBox');
  var content = document.getElementById('zonaHistorialContent');

  if (val === '__custom__') {
    document.getElementById('zonaCustomDiv').style.display = 'block';
    box.style.display = 'none';
  } else {
    document.getElementById('zonaCustomDiv').style.display = 'none';
  }

  if (!val || val === '__custom__') { box.style.display = 'none'; updateButtons(); return; }

  // Buscar corridas para esta zona en todas las categorias
  var cats = ['repuestos', 'fundas', 'telefonos'];
  var rows = cats.map(function(cat) {
    return zonaStats[val + '|' + cat] || null;
  });
  var tieneDatos = rows.some(function(r) { return r !== null; });

  if (!tieneDatos) { box.style.display = 'none'; updateButtons(); return; }

  var catLabels = { repuestos: 'Repuestos', fundas: 'Fundas', telefonos: 'Telefonos' };
  var html = '<div style="font-weight:600;margin-bottom:6px;color:#333">Corridas anteriores en esta zona:</div>';
  cats.forEach(function(cat, i) {
    var r = rows[i];
    if (!r) return;
    var pct = r.ultima_bruto > 0 ? Math.round((r.ultima_bruto - r.ultima_nuevos) / r.ultima_bruto * 100) : 0;
    var pctClass = pct < 40 ? 'pct-verde' : pct < 70 ? 'pct-amarillo' : 'pct-rojo';
    html += '<div class="zona-hist-row">' +
      '<span><span class="zona-hist-cat ' + cat + '">' + catLabels[cat] + '</span> ' +
      r.corridas + ' corrida' + (r.corridas > 1 ? 's' : '') + ' &mdash; ' + r.nuevos + ' leads &mdash; ' +
      '<span class="pct-badge ' + pctClass + '">' + pct + '% dup</span></span>' +
      '<span style="color:#999">' + r.ultima + '</span></div>';
  });
  content.innerHTML = html;
  box.style.display = 'block';
  updateButtons();
}

// ── Historial ─────────────────────────────────
function cargarHistorial() {
  fetch('/historial')
    .then(function(r) { return r.json(); })
    .then(function(h) {
      buildZonaStats(h);
      renderHistorial(h);
      actualizarSelectZonas();
      renderCobertura();
    });
}

function actualizarSelectZonas() {
  var sel = document.getElementById('zonaSelect');
  var opts = sel.querySelectorAll('option[value]:not([value=""]):not([value="__custom__"])');
  opts.forEach(function(opt) {
    var val = opt.value;
    var tieneCorrida = ['repuestos','fundas','telefonos'].some(function(c) {
      return !!zonaStats[val + '|' + c];
    });
    // Agrega checkmark si ya fue scrapeada
    var txt = opt.getAttribute('data-orig') || opt.textContent.replace(/\s*✓$/, '').trim();
    opt.setAttribute('data-orig', txt);
    opt.textContent = tieneCorrida ? txt + '  ✓' : txt;
  });
}

function renderHistorial(h) {
  const tbody = document.getElementById('histBody');
  if (!h || h.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="hist-empty">Sin corridas todavia.</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  h.forEach(function(r) {
    const bruto  = r.bruto  || 0;
    const nuevos = r.nuevos || 0;
    const dup    = bruto - nuevos;
    const pct    = bruto > 0 ? Math.round((dup / bruto) * 100) : 0;
    const fuente = r.fuente || 'Maps';

    let pillClass, pillText;
    if (r.test) {
      pillClass = 'test'; pillText = 'Prueba';
    } else if (fuente === 'Instagram') {
      pillClass = 'verde'; pillText = nuevos + ' cuentas';
    } else if (pct < 40) {
      pillClass = 'verde'; pillText = 'Con potencial';
    } else if (pct < 70) {
      pillClass = 'amarillo'; pillText = 'Parcial';
    } else {
      pillClass = 'rojo'; pillText = 'Agotada';
    }

    const catColors = { repuestos: '#dbeafe', fundas: '#fce7f3', telefonos: '#dcfce7' };
    const catTextColors = { repuestos: '#1d4ed8', fundas: '#be185d', telefonos: '#15803d' };
    const cat = r.categoria || 'repuestos';
    const catLabel = CATEGORIAS[cat] ? CATEGORIAS[cat].label : cat;
    const fuenteBadge = (fuente === 'Instagram'
      ? '<span class="pill" style="background:#f3e8ff;color:#6b21a8">IG</span> '
      : '<span class="pill" style="background:#f3f4f6;color:#374151">Maps</span> ') +
      '<span class="pill" style="background:' + catColors[cat] + ';color:' + catTextColors[cat] + '">' + catLabel + '</span>';

    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td style="white-space:nowrap;color:#666">' + r.fecha + '</td>' +
      '<td>' + fuenteBadge + '</td>' +
      '<td>' + r.zona + '</td>' +
      '<td><strong>' + nuevos + '</strong></td>' +
      '<td>' + bruto + '</td>' +
      '<td>' + (r.costo_real != null ? '$' + r.costo_real.toFixed(3) : '-') + '</td>' +
      '<td><span class="pill ' + pillClass + '">' + pillText + '</span></td>';
    tbody.appendChild(tr);
  });
}

function renderCobertura() {
  var tbody = document.getElementById('coberturaBody');
  var cat   = currentCat;
  var filas = [];

  Object.keys(zonaStats).forEach(function(key) {
    var parts = key.split('|');
    var zona  = parts[0];
    var kat   = parts[1];
    if (kat !== cat) return;
    filas.push({ zona: zona, stat: zonaStats[key] });
  });

  if (filas.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:#aaa;font-size:12px;padding:10px 8px;">Sin datos para esta categoria.</td></tr>';
    return;
  }

  // Ordenar: zonas con potencial primero (menor % dup), luego agotadas
  filas.sort(function(a, b) {
    var pctA = a.stat.bruto > 0 ? (a.stat.bruto - a.stat.nuevos) / a.stat.bruto : 1;
    var pctB = b.stat.bruto > 0 ? (b.stat.bruto - b.stat.nuevos) / b.stat.bruto : 1;
    return pctA - pctB;
  });

  tbody.innerHTML = '';
  filas.forEach(function(f) {
    var ub = f.stat.ultima_bruto;
    var un = f.stat.ultima_nuevos;
    var pct = ub > 0 ? Math.round((ub - un) / ub * 100) : 0;
    var pctClass = pct < 40 ? 'pct-verde' : pct < 70 ? 'pct-amarillo' : 'pct-rojo';
    var pctLabel = pct < 40 ? 'Vale volver (' + pct + '%)' : pct < 70 ? 'Parcial (' + pct + '%)' : 'Agotada (' + pct + '%)';
    var zonaNombre = f.zona
      .replace(', Ciudad Autonoma de Buenos Aires, Argentina','')
      .replace(', Buenos Aires, Argentina','')
      .replace(', Argentina','');
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td><span class="zona-dot hecha"></span>' + zonaNombre + '</td>' +
      '<td>' + f.stat.corridas + '</td>' +
      '<td><strong>' + nuevos + '</strong></td>' +
      '<td><span class="pct-badge ' + pctClass + '">' + pctLabel + '</span></td>' +
      '<td style="color:#999">' + f.stat.ultima + '</td>';
    tbody.appendChild(tr);
  });
}

// ── Instagram ─────────────────────────────────
function addIGLog(msg, cls) {
  const box = document.getElementById('igLogBox');
  const line = document.createElement('div');
  line.className   = 'log-line ' + (cls || '');
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function runInstagram(modo) {
  const configs = {
    full: { accounts: 8, mentions: 50, label: 'completa' },
    test: { accounts: 2, mentions: 10, label: 'prueba'   },
  };
  const cfg = configs[modo];

  document.getElementById('igLogBox').innerHTML = '';
  document.getElementById('igLogBox').classList.add('visible');
  document.getElementById('igResults').classList.remove('visible');
  document.getElementById('btnIGFull').disabled = true;
  document.getElementById('btnIGTest').disabled = true;

  addIGLog('Iniciando scraping Instagram ' + cfg.label + '...', 'inf');

  const url = '/run_instagram?accounts=' + cfg.accounts + '&mentions=' + cfg.mentions + '&test=' + (modo === 'test') + '&categoria=' + currentCat;
  const src = new EventSource(url);

  src.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'log') {
      const cls = data.msg.includes('[OK]') ? 'ok' : data.msg.includes('ERROR') ? 'err' : '';
      addIGLog(data.msg, cls);
    }
    if (data.type === 'done') {
      src.close();
      document.getElementById('btnIGFull').disabled = false;
      document.getElementById('btnIGTest').disabled = false;
      if (data.error) {
        addIGLog('ERROR: ' + data.error, 'err');
      } else {
        showIGResults(data.summary);
        cargarHistorial();
      }
    }
  };

  src.onerror = function() {
    src.close();
    addIGLog('Error de conexion con el servidor.', 'err');
    document.getElementById('btnIGFull').disabled = false;
    document.getElementById('btnIGTest').disabled = false;
  };
}

function showIGResults(s) {
  const nuevos = s.nuevos || 0;
  const bruto  = s.bruto  || 0;
  const costo  = s.costo_real != null ? '$' + s.costo_real.toFixed(3) : '-';

  document.getElementById('igStatNuevos').textContent = nuevos;
  document.getElementById('igStatBruto').textContent  = bruto;
  document.getElementById('igStatCosto').textContent  = costo;

  const leads = s.leads || [];
  const tbody = document.getElementById('igLeadsBody');
  const title = document.getElementById('igLeadsTitle');
  tbody.innerHTML = '';

  if (leads.length > 0) {
    title.textContent = leads.length + ' cuentas nuevas agregadas';
    leads.forEach(function(l) {
      const igLink = l.Instagram_URL
        ? '<a class="maps-link" href="' + l.Instagram_URL + '" target="_blank">Ver</a>'
        : '-';
      const seg = l.Seguidores ? Number(l.Seguidores).toLocaleString() : '0';
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td><strong>' + (l.Negocio || l.Username || '') + '</strong>' +
          (l.Username ? '<br><span style="color:#888;font-size:11px">@' + l.Username + '</span>' : '') +
        '</td>' +
        '<td>' + seg + '</td>' +
        '<td>' + focoBadge(l.Foco_Apple) + '</td>' +
        '<td style="font-size:11px;color:#666">' + (l.Tipo_contacto || 'DM') + '</td>' +
        '<td>' + igLink + '</td>';
      tbody.appendChild(tr);
    });
  }

  document.getElementById('igLeadsSection').style.display = leads.length > 0 ? 'block' : 'none';
  document.getElementById('igResults').classList.add('visible');
}

// ── Instaloader (followers) ───────────────────
function runFollowers(modo) {
  const configs = {
    full: { accounts: 8, max: 150, label: 'completa' },
    test: { accounts: 2, max: 20,  label: 'prueba'   },
  };
  const cfg = configs[modo];

  document.getElementById('igLogBox').innerHTML = '';
  document.getElementById('igLogBox').classList.add('visible');
  document.getElementById('igResults').classList.remove('visible');
  document.getElementById('ilProgressWrap').style.display = 'block';
  document.getElementById('ilProgressBar').style.width = '0%';
  document.getElementById('ilProgressLabel').textContent = '0 / ' + (cfg.accounts * cfg.max) + ' perfiles';
  ['btnIGFull','btnIGTest','btnILFull','btnILTest'].forEach(function(id) {
    document.getElementById(id).disabled = true;
  });

  addIGLog('Iniciando scraping de seguidores ' + cfg.label + ' (Instaloader)...', 'inf');

  const url = '/run_followers?accounts=' + cfg.accounts + '&max=' + cfg.max + '&test=' + (modo === 'test');
  const src = new EventSource(url);

  src.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'log') {
      const cls = data.msg.includes('[OK]') ? 'ok' : data.msg.includes('ERROR') ? 'err' : '';
      addIGLog(data.msg, cls);
    }
    if (data.type === 'progress') {
      const pct = data.total > 0 ? Math.round(data.actual / data.total * 100) : 0;
      document.getElementById('ilProgressBar').style.width = pct + '%';
      document.getElementById('ilProgressLabel').textContent = data.actual + ' / ' + data.total + ' perfiles (' + pct + '%)';
    }
    if (data.type === 'done') {
      document.getElementById('ilProgressBar').style.width = '100%';
      document.getElementById('ilProgressLabel').textContent = 'Completado';
      src.close();
      ['btnIGFull','btnIGTest','btnILFull','btnILTest'].forEach(function(id) {
        document.getElementById(id).disabled = false;
      });
      if (data.error) {
        addIGLog('ERROR: ' + data.error, 'err');
      } else {
        showIGResults(data.summary);
        cargarHistorial();
      }
    }
  };

  src.onerror = function() {
    src.close();
    addIGLog('Error de conexion con el servidor.', 'err');
    document.getElementById('ilProgressWrap').style.display = 'none';
    ['btnIGFull','btnIGTest','btnILFull','btnILTest'].forEach(function(id) {
      document.getElementById(id).disabled = false;
    });
  };
}

// ── Init ──────────────────────────────────────
document.getElementById('zonaCustom').addEventListener('input', updateButtons);
updateCost();
cargarHistorial();
</script>
</body>
</html>
"""


def agrupar_zonas():
    grupos = {}
    for label, value in ZONAS_PREDEFINIDAS:
        grupo = label.split(" — ")[0]
        grupos.setdefault(grupo, []).append((label.split(" — ")[-1], value))
    return list(grupos.items())


@app.route("/")
def index():
    import json as _json
    return render_template_string(
        HTML,
        zona_groups=agrupar_zonas(),
        search_terms_count=SEARCH_TERMS_COUNT,
        cost_per_result=COST_PER_RESULT,
        categorias_json=_json.dumps(CATEGORIAS_UI),
    )


@app.route("/historial")
def historial():
    return jsonify(leer_historial())


@app.route("/run")
def run():
    zona      = request.args.get("zona", "")
    max_res   = request.args.get("max", "150")
    terms     = request.args.get("terms", "6")
    test_mode = request.args.get("test", "false").lower() == "true"
    categoria = request.args.get("categoria", "repuestos")

    if not zona:
        return jsonify({"error": "Zona requerida"}), 400

    def generate():
        def emit(msg, tipo="log"):
            yield f"data: {json.dumps({'type': tipo, 'msg': msg})}\n\n"

        yield from emit("Preparando entorno...")

        env = os.environ.copy()
        env["APIFY_API_TOKEN"]  = os.getenv("APIFY_API_TOKEN", "")
        env["SPREADSHEET_URL"]  = os.getenv("SPREADSHEET_URL", "")
        env["PYTHONIOENCODING"] = "utf-8"

        cmd = [sys.executable, "prospector.py", "--zona", zona, "--max", max_res, "--terms", terms, "--categoria", categoria]
        if test_mode:
            cmd.append("--test")

        summary = {"bruto": 0, "nuevos": 0, "existentes": 0, "tipos": {}, "costo_real": None, "leads": []}
        error   = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue

                # Parsear metricas
                if "Total unicos:" in line:
                    try: summary["bruto"] = int(line.split(":")[1].strip().split()[0])
                    except Exception: pass
                elif "Leads ya en planilla:" in line:
                    try: summary["existentes"] = int(line.split(":")[1].strip())
                    except Exception: pass
                elif "Leads nuevos encontrados:" in line:
                    try: summary["nuevos"] = int(line.split(":")[1].strip())
                    except Exception: pass
                elif "Costo real:" in line:
                    try: summary["costo_real"] = float(line.split("~$")[1].split()[0])
                    except Exception: pass
                elif line.startswith("LEADS_JSON:"):
                    try: summary["leads"] = json.loads(line[len("LEADS_JSON:"):])
                    except Exception: pass
                elif any(t in line for t in ("Cadena:", "Independiente")):
                    try:
                        parts = line.strip().split(":")
                        if len(parts) == 2:
                            summary["tipos"][parts[0].strip()] = int(parts[1].strip())
                    except Exception: pass

                # No mostrar la línea LEADS_JSON en el log (es demasiado larga)
                if not line.startswith("LEADS_JSON:"):
                    yield from emit(line)

            proc.wait()
            if proc.returncode != 0:
                error = "El script termino con errores. Ver log arriba."

        except Exception as e:
            error = str(e)

        # Guardar en historial si fue exitoso
        if not error:
            guardar_historial({
                "fecha":      datetime.now().strftime("%d/%m/%Y %H:%M"),
                "zona":       zona,
                "bruto":      summary["bruto"],
                "nuevos":     summary["nuevos"],
                "costo_real": summary["costo_real"],
                "test":       test_mode,
                "fuente":     "Maps",
                "categoria":  categoria,
            })

        yield f"data: {json.dumps({'type': 'done', 'error': error, 'summary': summary})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/run_instagram")
def run_instagram():
    accounts  = request.args.get("accounts", "8")
    mentions  = request.args.get("mentions", "50")
    test_mode = request.args.get("test", "false").lower() == "true"
    categoria = request.args.get("categoria", "repuestos")

    def generate():
        def emit(msg, tipo="log"):
            yield f"data: {json.dumps({'type': tipo, 'msg': msg})}\n\n"

        yield from emit("Preparando entorno Instagram...")

        env = os.environ.copy()
        env["APIFY_API_TOKEN"]  = os.getenv("APIFY_API_TOKEN", "")
        env["SPREADSHEET_URL"]  = os.getenv("SPREADSHEET_URL", "")
        env["PYTHONIOENCODING"] = "utf-8"

        cmd = [sys.executable, "instagram_scraper.py",
               "--accounts", accounts, "--mentions", mentions, "--categoria", categoria]
        if test_mode:
            cmd.append("--test")

        summary = {"bruto": 0, "nuevos": 0, "costo_real": None, "leads": []}
        error   = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue

                if "Total bruto:" in line:
                    try: summary["bruto"] = int(line.split(":")[1].strip().split()[0])
                    except Exception: pass
                elif "Cuentas nuevas encontradas:" in line:
                    try: summary["nuevos"] = int(line.split(":")[1].strip())
                    except Exception: pass
                elif "Costo real:" in line:
                    try: summary["costo_real"] = float(line.split("~$")[1].split()[0])
                    except Exception: pass
                elif line.startswith("LEADS_JSON:"):
                    try: summary["leads"] = json.loads(line[len("LEADS_JSON:"):])
                    except Exception: pass

                if not line.startswith("LEADS_JSON:"):
                    yield from emit(line)

            proc.wait()
            if proc.returncode != 0:
                error = "El script termino con errores. Ver log arriba."

        except Exception as e:
            error = str(e)

        if not error:
            guardar_historial({
                "fecha":      datetime.now().strftime("%d/%m/%Y %H:%M"),
                "zona":       f"Instagram ({accounts} distribuidoras)",
                "bruto":      summary["bruto"],
                "nuevos":     summary["nuevos"],
                "costo_real": summary["costo_real"],
                "test":       test_mode,
                "fuente":     "Instagram",
            })

        yield f"data: {json.dumps({'type': 'done', 'error': error, 'summary': summary})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/run_followers")
def run_followers():
    accounts  = request.args.get("accounts", "8")
    max_foll  = request.args.get("max", "150")
    test_mode = request.args.get("test", "false").lower() == "true"

    def generate():
        def emit(msg, tipo="log"):
            yield f"data: {json.dumps({'type': tipo, 'msg': msg})}\n\n"

        yield from emit("Preparando Instaloader...")

        env = os.environ.copy()
        env["IG_USERNAME"]       = os.getenv("IG_USERNAME", "")
        env["IG_PASSWORD"]       = os.getenv("IG_PASSWORD", "")
        env["SPREADSHEET_URL"]   = os.getenv("SPREADSHEET_URL", "")
        env["PYTHONIOENCODING"]  = "utf-8"
        env["PYTHONUNBUFFERED"]  = "1"

        cmd = [sys.executable, "instagram_followers.py",
               "--accounts", accounts, "--max", max_foll]
        if test_mode:
            cmd.append("--test")

        summary = {"bruto": 0, "nuevos": 0, "costo_real": 0.0, "leads": []}
        error   = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue

                if "Total bruto:" in line:
                    try: summary["bruto"] = int(line.split(":")[1].strip().split()[0])
                    except Exception: pass
                elif "Total leads escritos:" in line:
                    try: summary["nuevos"] = int(line.split(":")[1].strip())
                    except Exception: pass
                elif line.startswith("LEADS_JSON:"):
                    try: summary["leads"] = json.loads(line[len("LEADS_JSON:"):])
                    except Exception: pass
                elif line.startswith("PROGRESS:"):
                    try:
                        partes = line[9:].split("/")
                        actual, total = int(partes[0]), int(partes[1])
                        yield f"data: {json.dumps({'type': 'progress', 'actual': actual, 'total': total})}\n\n"
                    except Exception: pass
                    continue

                if not line.startswith("LEADS_JSON:"):
                    yield from emit(line)

            proc.wait()
            if proc.returncode != 0:
                error = "El script termino con errores. Ver log arriba."

        except Exception as e:
            error = str(e)

        if not error:
            guardar_historial({
                "fecha":      datetime.now().strftime("%d/%m/%Y %H:%M"),
                "zona":       f"Instagram seguidores ({accounts} cuentas)",
                "bruto":      summary["bruto"],
                "nuevos":     summary["nuevos"],
                "costo_real": 0.0,
                "test":       test_mode,
                "fuente":     "Instagram",
            })

        yield f"data: {json.dumps({'type': 'done', 'error': error, 'summary': summary})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    import webbrowser
    print("Iniciando FixLab Lead Prospector...")
    print("Abriendo http://localhost:5000")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, port=5000, threaded=True)
