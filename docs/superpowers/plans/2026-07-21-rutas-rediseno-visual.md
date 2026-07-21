# Rediseño visual + mobile del generador de rutas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the catalogo-mayorista-b2b sky/slate design system to all 5 pages of the rutas app, add a real mobile layout (bottom nav, CRM card list + search, Mapa bottom sheet), and add free-text search to the CRM page.

**Architecture:** Everything lives in the existing `routes_app.py` (Flask blueprint, inline `render_template_string` HTML/CSS/JS) and `routes_db.py` (SQLite queries) — no new files, no new dependencies, single 768px breakpoint. The one backend change (CRM search) follows the existing parameterized-filter pattern in `routes_db.py`.

**Tech Stack:** Flask, Jinja2 (`render_template_string`), vanilla CSS (media queries), vanilla JS, SQLite. No new packages.

**Spec:** `docs/superpowers/specs/2026-07-21-rutas-rediseno-visual-design.md`

---

## Task 1: Design tokens + shared components in BASE_STYLE

**Goal:** Replace the current palette in `BASE_STYLE` with the sky/slate tokens from catalogo-mayorista-b2b, and add shared utility classes needed by later tasks.

**Files:**
- Modify: `routes_app.py:99-201` (the `BASE_STYLE` string)

**Acceptance Criteria:**
- [ ] Palette variables match the spec's token list
- [ ] Inter font loads (with system-font fallback)
- [ ] Cards/forms use 16px radius, buttons use 12px radius, badges get a subtle border
- [ ] `.card`, `.desktop-only`, `.mobile-only` utility classes exist
- [ ] `pytest -q` still shows 128 passed (no logic touched)

**Verify:** `pytest -q` → `128 passed`

**Steps:**

- [ ] **Step 1: Replace `BASE_STYLE`**

Replace the full `BASE_STYLE` block (currently `routes_app.py:99-201`) with:

```python
BASE_STYLE = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  :root {
    --blue: #0284C7;
    --blue-dark: #0369A1;
    --accent: #0EA5E9;
    --bg: #F8FAFC;
    --surface: #ffffff;
    --text: #334155;
    --text-muted: #64748B;
    --dark: #0F172A;
    --border: #D8EBF2;
    --light: #E8F4F8;
  }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 24px;
    line-height: 1.5;
  }
  h1 { font-size: 22px; font-weight: 700; margin: 0 0 16px; color: var(--dark); }
  h2 { font-size: 16px; font-weight: 700; margin-top: 24px; color: var(--dark); }
  a { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }
  form, ul {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 16px;
    list-style: none;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }
  ul { padding: 8px 16px; }
  li { padding: 6px 0; border-bottom: 1px solid var(--bg); }
  li:last-child { border-bottom: none; }
  label { display: block; margin-bottom: 10px; color: var(--text-muted); font-size: 14px; }
  input[type="text"], input[type="number"], select {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 14px;
    margin-top: 4px;
    font-family: inherit;
  }
  button, input[type="submit"] {
    background: var(--blue);
    color: white;
    border: none;
    border-radius: 12px;
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
    border-radius: 999px; padding: 7px 14px; font-size: 13px; font-weight: 600;
    text-decoration: none; white-space: nowrap;
  }
  .btn-secondary:hover { background: var(--light); text-decoration: none; }

  .table-wrap {
    max-height: 70vh; overflow: auto; border: 1px solid var(--border); border-radius: 16px;
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
  tbody tr:hover { background: var(--light); }
  tr:last-child td { border-bottom: none; }

  .cat-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; flex: none; }
  .cat-Repuestos { background: var(--blue); }
  .cat-Fundas { background: #f58231; }
  .cat-Telefonos { background: #3cb44b; }

  .badge { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid transparent; }
  .badge-ok { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }
  .badge-no { background: #fef2f2; color: #dc2626; border-color: #fecaca; }

  .estado-select {
    border: none; border-radius: 8px; padding: 3px 6px; font-size: 11.5px; font-weight: 600;
    cursor: pointer; font-family: inherit;
  }
  .estado-sin_contactar { background: var(--bg); color: var(--text-muted); }
  .estado-contactado { background: var(--light); color: var(--blue); }
  .estado-respondio { background: #fff7ed; color: #c2410c; }
  .estado-convertido { background: #ecfdf5; color: #059669; }
  .estado-form { margin: 0; padding: 0; background: none; border: none; }

  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 14px 16px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }

  .mobile-only { display: none; }
  @media (max-width: 767px) {
    .desktop-only { display: none; }
    .mobile-only { display: block; }
  }
</style>
"""
```

- [ ] **Step 2: Verify tests still pass**

Run: `cd "C:\Users\Jonathan\Desktop\fixlab-leads" && python -m pytest -q`
Expected: `128 passed`

- [ ] **Step 3: Manual visual check**

Start the local server (`python app.py` or the `fixlab-leads` launch config), open `http://localhost:5000/rutas/`, confirm the page loads with the new palette (sky-blue accents, slate text, Inter font) and nothing looks visually broken.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\Jonathan\Desktop\fixlab-leads"
git add routes_app.py
git commit -m "feat: apply sky/slate design tokens to rutas BASE_STYLE"
```

---

## Task 2: Bottom nav bar for mobile

**Goal:** Add a fixed bottom tab bar for mobile that replaces the top pill nav below 768px, highlighting the current page.

**Files:**
- Modify: `routes_app.py` (`BASE_STYLE`'s `<style>` block — append nav CSS; `NAV_LINKS` string)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] Desktop (>=768px): top pill nav unchanged, bottom bar not shown
- [ ] Mobile (<768px): top nav hidden, bottom bar fixed and visible, current page highlighted
- [ ] `pytest -q` still 128 passed

**Verify:** Manual browser check at 375px and 1280px widths on the Home page.

**Steps:**

- [ ] **Step 1: Add bottom-nav CSS to `BASE_STYLE`**

Add this block immediately before the closing `</style>` tag in `BASE_STYLE` (after the `.mobile-only` media query added in Task 1):

```css
  .bottom-nav { display: none; }
  @media (max-width: 767px) {
    .nav-row { display: none; }
    .bottom-nav {
      display: flex; position: fixed; bottom: 0; left: 0; right: 0; z-index: 50;
      background: var(--surface); border-top: 1px solid var(--border);
      box-shadow: 0 -2px 8px rgba(15, 23, 42, 0.06);
    }
    .bottom-nav a {
      flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px;
      padding: 8px 2px 10px; font-size: 10px; font-weight: 600; color: var(--text-muted);
      text-decoration: none;
    }
    .bottom-nav a.active { color: var(--blue); }
    .bn-icon { font-size: 18px; line-height: 1; }
    body { padding-bottom: 76px; }
  }
```

- [ ] **Step 2: Replace `NAV_LINKS`**

Replace the full `NAV_LINKS` string (`routes_app.py:203-211`) with:

```python
NAV_LINKS = """
<div class="nav-row">
  <a class="btn-secondary" href="{{ url_for('rutas.home') }}">Inicio</a>
  <a class="btn-secondary" href="{{ url_for('rutas.historial') }}">Historial</a>
  <a class="btn-secondary" href="{{ url_for('rutas.fallidos') }}">No geocodificables</a>
  <a class="btn-secondary" href="{{ url_for('rutas.mapa') }}">Mapa</a>
  <a class="btn-secondary" href="{{ url_for('rutas.crm') }}">CRM</a>
</div>

<nav class="bottom-nav">
  <a href="{{ url_for('rutas.home') }}"><span class="bn-icon">&#127968;</span>Inicio</a>
  <a href="{{ url_for('rutas.historial') }}"><span class="bn-icon">&#128337;</span>Historial</a>
  <a href="{{ url_for('rutas.fallidos') }}"><span class="bn-icon">&#9888;</span>Fallidos</a>
  <a href="{{ url_for('rutas.mapa') }}"><span class="bn-icon">&#128506;</span>Mapa</a>
  <a href="{{ url_for('rutas.crm') }}"><span class="bn-icon">&#128203;</span>CRM</a>
</nav>

<script>
(function() {
  var path = window.location.pathname;
  var homeHref = new URL('{{ url_for("rutas.home") }}', window.location.origin).pathname;
  document.querySelectorAll('.bottom-nav a').forEach(function(a) {
    var linkPath = new URL(a.href).pathname;
    var isMatch = linkPath === homeHref ? path === homeHref : path.indexOf(linkPath) === 0;
    if (isMatch) a.classList.add('active');
  });
})();
</script>
"""
```

- [ ] **Step 3: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `128 passed`

- [ ] **Step 4: Manual check**

Open `http://localhost:5000/rutas/` in the browser, resize to ~375px width — confirm the top pills disappear and a bottom bar with 5 icons appears, with "Inicio" highlighted in blue. Click through to Historial/Mapa/CRM and confirm each highlights correctly. Resize back to ~1280px — confirm the bottom bar disappears and the top pills return.

- [ ] **Step 5: Commit**

```bash
git add routes_app.py
git commit -m "feat: add fixed bottom nav bar for mobile"
```

---

## Task 3: CRM search backend (q parameter)

**Goal:** Add free-text search (negocio/direccion/telefono) to the CRM query functions.

**Files:**
- Modify: `routes_db.py:385-447`
- Test: `tests/test_routes_db.py`

**Acceptance Criteria:**
- [ ] `q` does partial, case-insensitive match on negocio/direccion/telefono
- [ ] Combines with existing filters via AND
- [ ] No match → empty list
- [ ] Parameterized (no string-built SQL)
- [ ] All tests pass

**Verify:** `pytest tests/test_routes_db.py -v` → all pass, including new tests below.

**Steps:**

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_routes_db.py`, right after `test_get_crm_leads_all_respects_filters` (currently ending around line 524):

```python
def test_get_crm_leads_filters_by_search_query_matching_negocio(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center Palermo", "Dir A", "")
    db.upsert_lead(conn, "P2", "Repuestos", "Otro Local", "Dir B", "")

    leads = db.get_crm_leads(conn, q="iphone")

    assert [lead["id"] for lead in leads] == [a]


def test_get_crm_leads_filters_by_search_query_matching_direccion_or_telefono(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "Local A", "Av. Santa Fe 3421", "", telefono="1122334455")
    b = db.upsert_lead(conn, "P2", "Repuestos", "Local B", "Otra Calle 100", "", telefono="1199998888")

    by_direccion = db.get_crm_leads(conn, q="santa fe")
    by_telefono = db.get_crm_leads(conn, q="9999")

    assert [lead["id"] for lead in by_direccion] == [a]
    assert [lead["id"] for lead in by_telefono] == [b]


def test_get_crm_leads_search_combines_with_other_filters(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")
    db.upsert_lead(conn, "P2", "Fundas", "iPhone Fundas", "Dir B", "")

    leads = db.get_crm_leads(conn, q="iphone", categoria="Repuestos")

    assert [lead["id"] for lead in leads] == [a]


def test_get_crm_leads_search_no_match_returns_empty(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")

    leads = db.get_crm_leads(conn, q="samsung")

    assert leads == []


def test_count_crm_leads_respects_search_query(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")
    db.upsert_lead(conn, "P2", "Repuestos", "Otro Local", "Dir B", "")

    assert db.count_crm_leads(conn, q="iphone") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_routes_db.py -k search_query -v`
Expected: FAIL — `TypeError: get_crm_leads() got an unexpected keyword argument 'q'`

- [ ] **Step 3: Update `_crm_filters_clause`**

Replace `routes_db.py:385-405` with:

```python
def _crm_filters_clause(
    categoria: str | None,
    outreach_status: str | None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    clause = ""
    params: list = []
    if categoria:
        clause += " AND categoria = ?"
        params.append(categoria)
    if outreach_status:
        clause += " AND outreach_status = ?"
        params.append(outreach_status)
    if min_reviews is not None:
        clause += " AND reviews_count >= ?"
        params.append(min_reviews)
    if min_rating is not None:
        clause += " AND rating >= ?"
        params.append(min_rating)
    if q:
        clause += " AND (negocio LIKE ? OR direccion LIKE ? OR telefono LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    return clause, params
```

- [ ] **Step 4: Update `get_crm_leads`, `count_crm_leads`, `get_crm_leads_all`**

Replace `routes_db.py:408-447` (the three functions) with:

```python
def get_crm_leads(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = CRM_PAGE_SIZE,
) -> list[sqlite3.Row]:
    """One page of leads across the 3 categories for the consolidated CRM view,
    optionally filtered by categoria, outreach_status, min_reviews, min_rating and/or q."""
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT * FROM leads_cache WHERE 1=1" + clause + " ORDER BY negocio LIMIT ? OFFSET ?"
    offset = (page - 1) * page_size
    return conn.execute(query, [*params, page_size, offset]).fetchall()


def count_crm_leads(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> int:
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT COUNT(*) AS c FROM leads_cache WHERE 1=1" + clause
    return conn.execute(query, params).fetchone()["c"]


def get_crm_leads_all(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> list[sqlite3.Row]:
    """Every matching lead, unpaginated — used for CSV export."""
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT * FROM leads_cache WHERE 1=1" + clause + " ORDER BY negocio"
    return conn.execute(query, params).fetchall()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_routes_db.py -v`
Expected: all pass (previous 40-ish in this file + 5 new)

- [ ] **Step 6: Run full suite**

Run: `python -m pytest -q`
Expected: `133 passed` (128 + 5 new)

- [ ] **Step 7: Commit**

```bash
git add routes_db.py tests/test_routes_db.py
git commit -m "feat: add free-text search to CRM lead queries"
```

---

## Task 4: CRM page — search bar, collapsible filters, mobile cards

**Goal:** Wire the search param into the CRM route/template, collapse filters behind a toggle on mobile, and render leads as cards below 768px.

**Files:**
- Modify: `routes_app.py` (`crm()` at line 877, `exportar_crm_csv()` at line 911, `PAGE_CRM` at lines 632-735)

**Depends on:** Task 1, Task 3

**Acceptance Criteria:**
- [ ] Search input works, round-trips through URL
- [ ] `q` passed through pager links and CSV export link
- [ ] Filters collapse behind "Filtros" button on mobile, always visible on desktop
- [ ] Desktop table unchanged; mobile shows `.mobile-cards` list instead
- [ ] `pytest -q` still passing

**Verify:** Manual browser check at 375px and 1280px; `pytest -q` → `133 passed`

**Steps:**

- [ ] **Step 1: Update `crm()` route**

Replace `routes_app.py:877-908` with:

```python
@rutas_bp.route("/crm", methods=["GET"])
def crm():
    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()
    min_reviews = request.args.get("min_reviews", type=int)
    min_rating = request.args.get("min_rating", type=float)
    q = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    conn = _conn()
    try:
        leads = db.get_crm_leads(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating, q=q or None, page=page,
        )
        total = db.count_crm_leads(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating, q=q or None,
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
        q=q,
        status_labels=OUTREACH_STATUS_LABELS,
        page=page,
        total_pages=total_pages,
        total=total,
    )
```

- [ ] **Step 2: Update `exportar_crm_csv()` route**

In `routes_app.py:911-922`, replace:

```python
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
```

with:

```python
@rutas_bp.route("/crm/exportar", methods=["GET"])
def exportar_crm_csv():
    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()
    min_reviews = request.args.get("min_reviews", type=int)
    min_rating = request.args.get("min_rating", type=float)
    q = request.args.get("q", "").strip()
    conn = _conn()
    try:
        leads = db.get_crm_leads_all(
            conn, categoria=categoria or None, outreach_status=estado or None,
            min_reviews=min_reviews, min_rating=min_rating, q=q or None,
        )
    finally:
        conn.close()
```

- [ ] **Step 3: Replace `PAGE_CRM`**

Replace the full `PAGE_CRM` string (`routes_app.py:632-735`) with:

```python
PAGE_CRM = """
<!doctype html>
<title>CRM de leads</title>
""" + BASE_STYLE + NAV_LINKS + """
<style>
  .crm-toolbar { margin-bottom: 12px; }
  .search-row { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
  .search-row input[type="text"] { flex: 1; margin-top: 0; }
  .filtros-toggle { display: none; }
  .filtros-panel { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
  .filtros-panel label { margin-bottom: 0; }
  .crm-export-row { margin-top: 10px; }
  .crm-summary { color: var(--text-muted); font-size: 13px; margin: 0 0 10px; }
  .pager { display: flex; justify-content: space-between; margin-top: 12px; font-size: 13px; }
  @media (max-width: 767px) {
    .filtros-toggle {
      display: inline-flex; background: var(--light); color: var(--blue);
      border: 1px solid var(--blue); border-radius: 8px; padding: 7px 12px;
      font-size: 12px; font-weight: 700; cursor: pointer;
    }
    .filtros-panel { display: none; flex-direction: column; align-items: stretch; margin-top: 10px; }
    .filtros-panel.open { display: flex; }
  }
</style>
<h1>CRM de leads</h1>

<div class="crm-toolbar">
  <form method="get" id="crmForm">
    <div class="search-row">
      <input type="text" name="q" value="{{ q or '' }}" placeholder="Buscar negocio, direccion, telefono...">
      <button type="button" class="filtros-toggle" onclick="document.getElementById('filtrosPanel').classList.toggle('open')">Filtros</button>
    </div>
    <div class="filtros-panel" id="filtrosPanel">
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
    </div>
  </form>
  <div class="crm-export-row">
    <a class="btn-secondary" href="{{ url_for('rutas.exportar_crm_csv', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating, q=q) }}">
      Exportar CSV
    </a>
  </div>
</div>

<p class="crm-summary">{{ total }} lead{{ "s" if total != 1 else "" }} — pagina {{ page }} de {{ total_pages }}</p>

<div class="table-wrap desktop-only">
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

<div class="mobile-only">
  {% for lead in leads %}
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
      <strong>{{ lead.negocio }}</strong>
      <span class="cat-dot cat-{{ lead.categoria }}"></span>
    </div>
    <div style="font-size:12px; color:var(--text-muted); line-height:1.6; margin-bottom:8px;">
      {{ lead.direccion or "-" }}<br>
      {{ lead.telefono or "-" }} &middot;
      {% if lead.rating is not none %}{{ lead.rating }} &#9733;{% if lead.reviews_count is not none %} ({{ lead.reviews_count }} reviews){% endif %}{% else %}Sin rating{% endif %}
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--bg); padding-top:8px;">
      {% if lead.lat %}<span class="badge badge-ok">Geo OK</span>{% else %}<span class="badge badge-no">Sin geo</span>{% endif %}
      <form method="post" class="estado-form" action="{{ url_for('rutas.actualizar_estado', lead_id=lead.id) }}">
        <select name="estado" class="estado-select estado-{{ lead.outreach_status }}"
                onchange="this.className = 'estado-select estado-' + this.value; this.form.submit();">
          {% for value, label in status_labels.items() %}
            <option value="{{ value }}" {% if lead.outreach_status == value %}selected{% endif %}>{{ label }}</option>
          {% endfor %}
        </select>
      </form>
    </div>
  </div>
  {% else %}
  <p style="text-align:center; color:var(--text-muted); padding:20px;">No hay leads para este filtro.</p>
  {% endfor %}
</div>

<div class="pager">
  <span>
    {% if page > 1 %}
      <a href="{{ url_for('rutas.crm', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating, q=q, page=page-1) }}">&laquo; Anterior</a>
    {% endif %}
  </span>
  <span>
    {% if page < total_pages %}
      <a href="{{ url_for('rutas.crm', categoria=categoria, estado=estado, min_reviews=min_reviews, min_rating=min_rating, q=q, page=page+1) }}">Siguiente &raquo;</a>
    {% endif %}
  </span>
</div>
"""
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 5: Manual check**

At 1280px: confirm the table still renders, search box + filters are inline and visible, searching for a known business name filters correctly, CSV export link includes `q=`.
At 375px: confirm filters are hidden behind a "Filtros" button that toggles them, and leads render as cards instead of a table.

- [ ] **Step 6: Commit**

```bash
git add routes_app.py
git commit -m "feat: add search bar and mobile card layout to CRM page"
```

---

## Task 5: Mapa page — collapsible filtros + bottom sheet detail

**Goal:** Collapse the lotes-filter checklist behind a toggle on mobile, and turn the marker-detail panel into a bottom sheet on mobile.

**Files:**
- Modify: `routes_app.py` (`PAGE_MAPA` at lines 431-622)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] Desktop layout (map + side panel) unchanged
- [ ] Mobile: map full-width, lotes filter collapses behind "Filtros de lotes" button
- [ ] Mobile: tapping a marker slides the panel up from the bottom, closable
- [ ] `pytest -q` still passing (no backend touched here)

**Verify:** Manual browser check at 375px and 1280px on `/rutas/mapa`.

**Steps:**

- [ ] **Step 1: Add mobile CSS to `PAGE_MAPA`'s `<style>` block**

In `routes_app.py`, inside `PAGE_MAPA`'s existing `<style>` block (currently `routes_app.py:437-462`), add this block right before the closing `</style>`:

```css
  .filtros-toggle-mapa { display: none; }
  @media (max-width: 767px) {
    .map-layout { flex-direction: column; }
    #map { height: 400px; width: 100%; }
    .filtros-toggle-mapa {
      display: inline-flex; background: var(--light); color: var(--blue);
      border: 1px solid var(--blue); border-radius: 8px; padding: 7px 12px;
      font-size: 12px; font-weight: 700; cursor: pointer; margin-bottom: 10px;
    }
    #filtros { display: none; }
    #filtros.open { display: block; }
    #panel {
      position: fixed; left: 0; right: 0; bottom: 0; width: auto; height: auto;
      max-height: 70vh; border-radius: 16px 16px 0 0; z-index: 60;
      transform: translateY(100%); transition: transform .25s ease;
      box-shadow: 0 -4px 12px rgba(15, 23, 42, 0.12);
    }
    #panel.open { transform: translateY(0); }
    .sheet-handle { width: 36px; height: 4px; background: var(--border); border-radius: 2px; margin: 0 auto 10px; cursor: pointer; }
  }
```

- [ ] **Step 2: Add the filtros toggle button**

In `routes_app.py`, find this line (currently `routes_app.py:475`):

```html
<div id="filtros">
```

Replace it with:

```html
<button type="button" class="filtros-toggle-mapa" onclick="document.getElementById('filtros').classList.toggle('open')">Filtros de lotes</button>
<div id="filtros">
```

- [ ] **Step 3: Update `renderPanel()` to open the sheet and add a close handle**

Find the `renderPanel` function (currently `routes_app.py:533-546`):

```javascript
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
```

Replace with:

```javascript
  function closePanel() {
    document.getElementById('panel').classList.remove('open');
  }

  function renderPanel(lead, prefix) {
    var panel = document.getElementById('panel');
    var ratingText = (lead.rating != null && lead.reviews_count != null)
      ? lead.rating + " (" + lead.reviews_count + " reviews)"
      : (lead.rating != null ? String(lead.rating) : (lead.reviews_count != null ? lead.reviews_count + " reviews" : ""));
    var categoriaText = lead.categorias ? lead.categorias.join(", ") : lead.categoria;
    var leadIds = lead.lead_ids || (lead.id ? [lead.id] : []);
    panel.innerHTML =
      '<div class="sheet-handle" onclick="closePanel()"></div>' +
      "<h3>" + (prefix || "") + escapeHtml(lead.negocio) + "</h3>" +
      panelRow("Categoria", categoriaText) +
      panelRow("Direccion", lead.direccion) +
      panelRow("Telefono", lead.telefono) +
      panelRow("Rating", ratingText) +
      (leadIds.length ? estadoSelectHtml(lead) : "");
    panel.classList.add('open');
```

(The rest of the function — the `estado-select` change listener setup after this block — stays exactly as-is.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q`
Expected: `133 passed` (this task touches no Python/backend logic)

- [ ] **Step 5: Manual check**

At 1280px: confirm map + side panel look and behave as before.
At 375px: confirm the lotes filter list is hidden behind "Filtros de lotes"; tap a marker on the map and confirm a sheet slides up from the bottom with the lead's details; tap the handle bar at the top of the sheet and confirm it slides back down.

- [ ] **Step 6: Commit**

```bash
git add routes_app.py
git commit -m "feat: add mobile bottom sheet and collapsible filtros to Mapa page"
```

---

## Task 6: Historial + Fallidos mobile card layout

**Goal:** Apply the same table→cards mobile conversion used in CRM to these two simpler table pages.

**Files:**
- Modify: `routes_app.py` (`PAGE_HISTORIAL` at lines 403-429, `PAGE_FALLIDOS` at lines 379-401)

**Depends on:** Task 1

**Acceptance Criteria:**
- [ ] Both pages' desktop tables unchanged
- [ ] Both pages render `.mobile-only` cards below 768px, from the same Jinja data
- [ ] Empty states shown correctly in both layouts
- [ ] `pytest -q` still passing

**Verify:** Manual browser check at 375px and 1280px on both pages.

**Steps:**

- [ ] **Step 1: Update `PAGE_FALLIDOS`**

Replace the full `PAGE_FALLIDOS` string (`routes_app.py:379-401`) with:

```python
PAGE_FALLIDOS = """
<!doctype html>
<title>Leads no geocodificables</title>
""" + BASE_STYLE + NAV_LINKS + """
<h1>Leads no geocodificables</h1>
<p class="crm-summary">{{ leads|length }} lead{{ "s" if leads|length != 1 else "" }} sin geocodificar.</p>
<div class="table-wrap desktop-only">
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
<div class="mobile-only">
  {% for lead in leads %}
  <div class="card">
    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
      <strong>{{ lead.negocio }}</strong>
      <span class="cat-dot cat-{{ lead.categoria }}"></span>
    </div>
    <div style="font-size:12px; color:var(--text-muted);">{{ lead.direccion or "-" }}</div>
  </div>
  {% else %}
  <p style="text-align:center; color:var(--text-muted); padding:20px;">Ninguno por ahora.</p>
  {% endfor %}
</div>
"""
```

- [ ] **Step 2: Update `PAGE_HISTORIAL`**

Replace the full `PAGE_HISTORIAL` string (`routes_app.py:403-429`) with:

```python
PAGE_HISTORIAL = """
<!doctype html>
<title>Historial de lotes</title>
""" + BASE_STYLE + NAV_LINKS + """
<h1>Historial de lotes</h1>
<div class="table-wrap desktop-only">
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
<div class="mobile-only">
  {% for lote in lotes %}
  <div class="card">
    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
      <strong>Lote #{{ lote.id }}</strong>
      {% if lote.categoria %}<span class="cat-dot cat-{{ lote.categoria }}"></span>{{ lote.categoria }}{% else %}<span style="font-size:11px;color:var(--text-muted)">Todas</span>{% endif %}
    </div>
    <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">
      {{ lote.fecha_generado }}<br>
      {{ lote.origen_texto }}<br>
      {{ lote.tamano_real }}/{{ lote.tamano_solicitado }} direcciones
    </div>
    <a class="btn-secondary" href="{{ url_for('rutas.detalle_lote', lote_id=lote.id) }}">Ver rutas</a>
  </div>
  {% else %}
  <p style="text-align:center; color:var(--text-muted); padding:20px;">Todavia no generaste ningun lote.</p>
  {% endfor %}
</div>
"""
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 4: Manual check**

At 1280px: confirm both pages show the existing tables unchanged.
At 375px: confirm both pages show cards instead, and the empty-state message appears correctly if there's no data (can check `/rutas/fallidos` if there happen to be no failed leads, or `/rutas/historial` on a fresh DB).

- [ ] **Step 5: Commit**

```bash
git add routes_app.py
git commit -m "feat: add mobile card layout to Historial and Fallidos pages"
```

---

## Notes on pages not covered by a dedicated task

`PAGE_HOME`, `PAGE_RESULTADO`, and `PAGE_ERROR` are not touched by any task above — they're simple single-column forms/content that inherit the new palette and nav automatically via `BASE_STYLE` and `NAV_LINKS` (Tasks 1–2), with no fixed-width or table layouts that need restructuring for mobile. This matches the spec's note that these are a smaller lift than CRM/Mapa.

## Deploying after this plan is done

Same as previous changes to this app: commit and push to `main`, then on PythonAnywhere run `git pull` in the Bash console and click **Reload** on the Web tab.
