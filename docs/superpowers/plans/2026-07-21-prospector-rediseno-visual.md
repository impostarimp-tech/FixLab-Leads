# Rediseño visual + mobile del Lead Prospector (app.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the sky/slate design tokens from the Rutas redesign to `app.py`'s Lead Prospector page, and add a real mobile layout (responsive grids, table→cards for all four data tables), without touching its scraping/sync logic or its own separate nav.

**Architecture:** Everything lives in `app.py`'s single `HTML` template string (CSS in a `<style>` block, JS at the bottom). Unlike Rutas, this page renders its tables entirely client-side via JS (`renderLeads`, `renderHistorial`, `renderCobertura`, `showIGResults`) after SSE events or fetches — so the mobile "dual render" happens inside those same JS functions, not as a second Jinja loop.

**Tech Stack:** Flask (`render_template_string`), vanilla CSS/JS (same as Rutas). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-21-prospector-rediseno-visual-design.md`

---

## Task 1: Palette/typography + utility classes in app.py style block

**Goal:** Replace app.py's hardcoded palette with the sky/slate tokens (as direct hex values, no CSS variables), and add shared utility classes for later tasks.

**Files:**
- Modify: `app.py:180-309` (the `<style>` block)

**Acceptance Criteria:**
- [ ] Neutral/brand colors replaced; semantic status colors (semaforo, pill, badge) left unchanged
- [ ] Inter font imported and applied
- [ ] `.desktop-only`, `.mobile-only`, `.item-card` classes added
- [ ] `pytest -q` still 133 passed

**Verify:** `pytest -q` → `133 passed`

**Steps:**

- [ ] **Step 1: Replace the full `<style>` block**

Replace `app.py:180-309` (everything between `<style>` and `</style>`, keeping those two tags) with:

```css
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
```

- [ ] **Step 2: Verify tests still pass**

Run: `cd "C:\Users\Jonathan\Desktop\fixlab-leads" && python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 3: Manual visual check**

Start the app (`python app.py`), open `http://localhost:5000/`, confirm the page loads with the new palette (sky-blue buttons/active tab, slate text, dark header, Inter font) and nothing looks visually broken.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\Jonathan\Desktop\fixlab-leads"
git add app.py
git commit -m "feat: apply sky/slate design tokens to Prospector page"
```

---

## Task 2: Responsive form row + stat grids

**Goal:** Stack the max-resultados/terminos row on mobile, and make both stat-grids collapse to 2 columns — fixing the IG stat-grid's inline style first.

**Files:**
- Modify: `app.py` (style block, and the IG stat-grid div)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] IG stat-grid's inline style replaced with a `.stat-grid-3` class
- [ ] Mobile: `.row` becomes 1 column, both stat-grids become 2 columns
- [ ] Desktop: unchanged
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check at 375px and 1280px.

**Steps:**

- [ ] **Step 1: Replace the IG stat-grid's inline style with a class**

Find this line in `app.py` (inside the Instagram section):

```html
      <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr);">
```

Replace with:

```html
      <div class="stat-grid stat-grid-3">
```

- [ ] **Step 2: Add `.stat-grid-3` and the mobile media query**

Add this immediately before the closing `</style>` tag (after the `.mobile-only`/media-query block added in Task 1):

```css
  .stat-grid-3 { grid-template-columns: repeat(3, 1fr); }

  @media (max-width: 767px) {
    .row { grid-template-columns: 1fr; }
    .stat-grid, .stat-grid-3 { grid-template-columns: repeat(2, 1fr); }
  }
```

- [ ] **Step 3: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 4: Manual check**

At 1280px: confirm the main stats show 4 across, IG stats show 3 across, the max-resultados/terminos inputs sit side by side.
At 375px: confirm both stat-grids show 2 across, and the max-resultados/terminos inputs stack vertically.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: make form row and stat grids responsive on mobile"
```

---

## Task 3: Leads results table mobile card layout

**Goal:** Add a mobile card list for the search-results leads table, generated client-side by `renderLeads()`.

**Files:**
- Modify: `app.py` (leads table HTML, `renderLeads()` JS function)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] Desktop table wrapped in `.desktop-only`, new `#leadsCards` mobile-only div added
- [ ] `renderLeads()` populates both the table and `#leadsCards` from the same data
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check at 375px and 1280px after a test search.

**Steps:**

- [ ] **Step 1: Update the leads table HTML**

Find this block in `app.py` (the "TABLA LEADS NUEVOS" section):

```html
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
```

Replace with:

```html
      <!-- TABLA LEADS NUEVOS -->
      <div id="leadsSection" style="display:none;">
        <div class="leads-header">
          <h3 id="leadsTitle">Leads nuevos</h3>
          <input class="leads-filter" type="text" id="leadsFilter" placeholder="Filtrar..." oninput="filtrarLeads()">
        </div>
        <div class="leads-table-wrap desktop-only">
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
        <div class="mobile-only" id="leadsCards"></div>
      </div>
```

- [ ] **Step 2: Update `renderLeads()`**

Replace the full `renderLeads` function in `app.py` with:

```javascript
function renderLeads(leads) {
  const sec   = document.getElementById('leadsSection');
  const tbody = document.getElementById('leadsBody');
  const cards = document.getElementById('leadsCards');
  const title = document.getElementById('leadsTitle');
  tbody.innerHTML = '';
  cards.innerHTML = '';

  if (!leads || leads.length === 0) {
    sec.style.display = 'none';
    return;
  }

  title.textContent = leads.length + ' leads nuevos agregados';
  leads.forEach(function(l) {
    const mapsLink = l.Maps_URL
      ? '<a class="maps-link" href="' + l.Maps_URL + '" target="_blank">Ver</a>'
      : '-';

    const tr = document.createElement('tr');
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

    const card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML =
      '<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">' +
        '<strong>' + (l.Negocio || '') + '</strong>' +
        focoBadge(l.Foco_Apple) +
      '</div>' +
      (l.Direccion ? '<div style="color:#64748B;font-size:12px;margin-bottom:6px;">' + l.Direccion + '</div>' : '') +
      '<div style="display:flex; justify-content:space-between; align-items:center;">' +
        tipoBadge(l.Tipo) +
        '<span style="font-size:12px;color:#64748B;">' + (l.Resenas || 0) + ' reviews &middot; ' + (l.Telefono || '-') + '</span>' +
      '</div>' +
      (mapsLink !== '-' ? '<div style="margin-top:8px;">' + mapsLink + '</div>' : '');
    cards.appendChild(card);
  });

  sec.style.display = 'block';
}
```

- [ ] **Step 3: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 4: Manual check**

Run a "Prueba" search (cheapest option) from the UI to populate results. At 1280px: confirm the leads table renders as before. At 375px: confirm cards render instead, with negocio, direccion, tipo/foco badges, resenas, telefono, and a Maps link when available.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add mobile card layout to leads results table"
```

---

## Task 4: Historial + Cobertura tables mobile card layout

**Goal:** Add mobile card lists for "Historial de corridas" and "Cobertura de zonas", generated client-side. Also fixes a pre-existing bug in `renderCobertura()` (undefined `nuevos` reference) hit while rewriting it.

**Files:**
- Modify: `app.py` (historial/cobertura HTML, `renderHistorial()` and `renderCobertura()` JS functions)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] Both tables wrapped in `.desktop-only`, new mobile-only card containers added
- [ ] `renderHistorial()`/`renderCobertura()` populate both table and cards from the same data
- [ ] `renderCobertura()` uses `f.stat.nuevos` (not the undefined bare `nuevos`) in both the table row and the card
- [ ] Empty states render correctly in both layouts
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check at 375px and 1280px after a test search.

**Steps:**

- [ ] **Step 1: Update the Historial and Cobertura HTML**

Find this block in `app.py`:

```html
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
```

Replace with:

```html
  <!-- HISTORIAL -->
  <div class="card">
    <h2>Historial de corridas</h2>
    <div class="hist-table-wrap desktop-only">
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
    <div class="mobile-only" id="histCards">
      <p class="hist-empty">Sin corridas todavia. Ejecuta una busqueda para ver el historial.</p>
    </div>
  </div>

  <!-- COBERTURA DE ZONAS -->
  <div class="card">
    <h2>Cobertura de zonas</h2>
    <p style="font-size:12px;color:#888;margin-bottom:14px;">Zonas que ya fueron scrapeadas en la categoria activa. ✓ = al menos una corrida real.</p>
    <div id="coberturaWrap" class="desktop-only">
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
    <div class="mobile-only" id="coberturaCards">
      <p class="hist-empty">Sin datos todavia.</p>
    </div>
  </div>
```

- [ ] **Step 2: Update `renderHistorial()`**

Replace the full `renderHistorial` function in `app.py` with:

```javascript
function renderHistorial(h) {
  const tbody = document.getElementById('histBody');
  const cards = document.getElementById('histCards');
  if (!h || h.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="hist-empty">Sin corridas todavia.</td></tr>';
    cards.innerHTML = '<p class="hist-empty">Sin corridas todavia.</p>';
    return;
  }
  tbody.innerHTML = '';
  cards.innerHTML = '';
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

    const card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML =
      '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">' +
        '<span style="font-size:12px;color:#64748B;">' + r.fecha + '</span>' +
        '<span class="pill ' + pillClass + '">' + pillText + '</span>' +
      '</div>' +
      '<div style="margin-bottom:6px;">' + fuenteBadge + '</div>' +
      '<div style="font-size:13px;color:#334155;margin-bottom:6px;">' + r.zona + '</div>' +
      '<div style="font-size:12px;color:#64748B;">' +
        '<strong style="color:#0F172A;">' + nuevos + '</strong> nuevos &middot; ' + bruto + ' encontrados' +
        (r.costo_real != null ? ' &middot; $' + r.costo_real.toFixed(3) : '') +
      '</div>';
    cards.appendChild(card);
  });
}
```

- [ ] **Step 3: Update `renderCobertura()`**

Replace the full `renderCobertura` function in `app.py` with:

```javascript
function renderCobertura() {
  var tbody = document.getElementById('coberturaBody');
  var cards = document.getElementById('coberturaCards');
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
    cards.innerHTML = '<p class="hist-empty">Sin datos para esta categoria.</p>';
    return;
  }

  // Ordenar: zonas con potencial primero (menor % dup), luego agotadas
  filas.sort(function(a, b) {
    var pctA = a.stat.bruto > 0 ? (a.stat.bruto - a.stat.nuevos) / a.stat.bruto : 1;
    var pctB = b.stat.bruto > 0 ? (b.stat.bruto - b.stat.nuevos) / b.stat.bruto : 1;
    return pctA - pctB;
  });

  tbody.innerHTML = '';
  cards.innerHTML = '';
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
      '<td><strong>' + f.stat.nuevos + '</strong></td>' +
      '<td><span class="pct-badge ' + pctClass + '">' + pctLabel + '</span></td>' +
      '<td style="color:#999">' + f.stat.ultima + '</td>';
    tbody.appendChild(tr);

    var card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML =
      '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">' +
        '<span><span class="zona-dot hecha"></span>' + zonaNombre + '</span>' +
        '<span class="pct-badge ' + pctClass + '">' + pctLabel + '</span>' +
      '</div>' +
      '<div style="font-size:12px;color:#64748B;">' +
        f.stat.corridas + ' corridas &middot; <strong style="color:#0F172A;">' + f.stat.nuevos + '</strong> nuevos &middot; ultima: ' + f.stat.ultima +
      '</div>';
    cards.appendChild(card);
  });
}
```

Note: `f.stat.nuevos` replaces the bare `nuevos` that appeared in the original table-row code (an undefined-variable bug, since no `nuevos` exists in this function's scope) — both the table row and the new card use the correct `f.stat.nuevos`.

- [ ] **Step 4: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 5: Manual check**

Run a test search to populate historial/cobertura data. At 1280px: confirm both tables render as before (and that "Leads nuevos" in Cobertura now shows a real number, not blank/error). At 375px: confirm both render as cards instead, with correct data and no console errors.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add mobile card layout to Historial and Cobertura tables

Also fixes an undefined 'nuevos' reference in renderCobertura(),
hit while rewriting the function to add card rendering."
```

---

## Task 5: Instagram results table mobile card layout

**Goal:** Add a mobile card list for the Instagram results table, generated client-side.

**Files:**
- Modify: `app.py` (IG results HTML, `showIGResults()` JS function)

**Depends on:** Task 1, Task 2

**Acceptance Criteria:**
- [ ] Desktop table wrapped in `.desktop-only`, new `#igLeadsCards` mobile-only div added
- [ ] `showIGResults()` populates both the table and `#igLeadsCards` from the same data
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check at 375px and 1280px.

**Steps:**

- [ ] **Step 1: Update the IG results HTML**

Find this block in `app.py`:

```html
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
```

Replace with:

```html
      <div id="igLeadsSection" style="display:none; margin-top:16px;">
        <div class="leads-header">
          <h3 id="igLeadsTitle">Cuentas nuevas</h3>
        </div>
        <div class="leads-table-wrap desktop-only">
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
        <div class="mobile-only" id="igLeadsCards"></div>
      </div>
```

- [ ] **Step 2: Update `showIGResults()`**

Replace the full `showIGResults` function in `app.py` with:

```javascript
function showIGResults(s) {
  const nuevos = s.nuevos || 0;
  const bruto  = s.bruto  || 0;
  const costo  = s.costo_real != null ? '$' + s.costo_real.toFixed(3) : '-';

  document.getElementById('igStatNuevos').textContent = nuevos;
  document.getElementById('igStatBruto').textContent  = bruto;
  document.getElementById('igStatCosto').textContent  = costo;

  const leads = s.leads || [];
  const tbody = document.getElementById('igLeadsBody');
  const cards = document.getElementById('igLeadsCards');
  const title = document.getElementById('igLeadsTitle');
  tbody.innerHTML = '';
  cards.innerHTML = '';

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

      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML =
        '<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">' +
          '<strong>' + (l.Negocio || l.Username || '') + '</strong>' +
          focoBadge(l.Foco_Apple) +
        '</div>' +
        (l.Username ? '<div style="color:#64748B;font-size:12px;margin-bottom:6px;">@' + l.Username + '</div>' : '') +
        '<div style="display:flex; justify-content:space-between; align-items:center;">' +
          '<span style="font-size:12px;color:#64748B;">' + seg + ' seguidores &middot; ' + (l.Tipo_contacto || 'DM') + '</span>' +
        '</div>' +
        (igLink !== '-' ? '<div style="margin-top:8px;">' + igLink + '</div>' : '');
      cards.appendChild(card);
    });
  }

  document.getElementById('igLeadsSection').style.display = leads.length > 0 ? 'block' : 'none';
  document.getElementById('igResults').classList.add('visible');
}
```

- [ ] **Step 3: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 4: Manual check**

At 1280px: confirm the IG results table renders as before. At 375px: confirm cards render instead, with cuenta/username, seguidores, foco badge, contacto, and Instagram link when available.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add mobile card layout to Instagram results table"
```

---

## Notes

- **Tab-bar and header nav**: intentionally untouched structurally per the approved spec — only recolored via Task 1's palette. Repuestos/Fundas/Telefonos/Rutas stays a 4-item flex row, same shape as Mapa's category tabs which already work at 375px.
- **Log boxes**: intentionally untouched structurally — already a simple scrollable dark box, just recolored via Task 1.
- **No shared CSS variables with `routes_app.py`**: per the approved spec, this page keeps its own hardcoded-hex style block rather than importing `BASE_STYLE`, to minimize the diff on a page not touched until now.

## Deploying after this plan is done

Same as previous changes: commit and push to `main`, then on PythonAnywhere run `git pull` in the Bash console and click **Reload** on the Web tab.
