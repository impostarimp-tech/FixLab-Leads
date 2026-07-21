# Geolocalización del celular en Rutas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a rep use their phone's GPS to (1) generate a route starting from their current location, and (2) find the single nearest geocoded lead on the Mapa page — both entirely client-side, no backend changes.

**Architecture:** Both features call `navigator.geolocation.getCurrentPosition()` client-side. The route-origin feature reuses `_resolve_origen()`'s existing `guardado|lat|lng|texto` value format (already parsed server-side, untouched). The nearest-lead feature reuses data already loaded into the page (`allLeads`, with lat/lng) and a small new JS haversine function — no round-trip to the server.

**Tech Stack:** Vanilla JS (Geolocation API), Flask/Jinja templates (`routes_app.py`). No new dependencies, no backend changes.

**Spec:** `docs/superpowers/specs/2026-07-21-geolocalizacion-rutas-design.md`

---

## Task 1: "Usar mi ubicacion" origin button on Home page

**Goal:** Add a GPS-based origin option to the route-generation form.

**Files:**
- Modify: `routes_app.py` (`PAGE_HOME`)

**Acceptance Criteria:**
- [ ] Button calls `navigator.geolocation.getCurrentPosition()`
- [ ] On success: adds+selects a `guardado|<lat>|<lng>|Mi ubicacion (GPS)` option, triggers `onOrigenSelectChange()`
- [ ] On failure/unsupported: inline error message, form otherwise unaffected
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check with mocked geolocation.

**Steps:**

- [ ] **Step 1: Add the button and error message to the origin field**

In `routes_app.py`, find this block in `PAGE_HOME`:

```html
      <option value="otro">Otra direccion (escribir)...</option>
    </select>
  </label>
  <div id="origenLibreWrap" style="display:none;">
```

Replace with:

```html
      <option value="otro">Otra direccion (escribir)...</option>
    </select>
  </label>
  <button type="button" class="btn-secondary" id="btnUsarUbicacion" onclick="usarMiUbicacion()">Usar mi ubicacion</button>
  <p id="ubicacionError" style="display:none; color:#dc2626; font-size:12px; margin-top:6px;"></p>
  <div id="origenLibreWrap" style="display:none;">
```

- [ ] **Step 2: Add `usarMiUbicacion()` to the script block**

Find this block in `PAGE_HOME`:

```html
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
```

Replace with:

```html
<script>
function onOrigenSelectChange() {
  var sel = document.getElementById('origenSelect');
  var wrap = document.getElementById('origenLibreWrap');
  var libre = document.getElementById('origenLibre');
  var esOtro = sel.value === 'otro';
  wrap.style.display = esOtro ? 'block' : 'none';
  libre.required = esOtro;
}

function usarMiUbicacion() {
  var errorMsg = document.getElementById('ubicacionError');
  errorMsg.style.display = 'none';
  if (!navigator.geolocation) {
    errorMsg.textContent = 'Tu navegador no soporta geolocalizacion.';
    errorMsg.style.display = 'block';
    return;
  }
  navigator.geolocation.getCurrentPosition(function(pos) {
    var lat = pos.coords.latitude;
    var lng = pos.coords.longitude;
    var sel = document.getElementById('origenSelect');
    var value = 'guardado|' + lat + '|' + lng + '|Mi ubicacion (GPS)';
    var option = document.createElement('option');
    option.value = value;
    option.textContent = 'Mi ubicacion (GPS)';
    sel.appendChild(option);
    sel.value = value;
    onOrigenSelectChange();
  }, function() {
    errorMsg.textContent = 'No se pudo obtener tu ubicacion -- revisa los permisos del navegador.';
    errorMsg.style.display = 'block';
  });
}
</script>
```

- [ ] **Step 3: Verify tests still pass**

Run: `cd "C:\Users\Jonathan\Desktop\fixlab-leads" && python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 4: Manual check with mocked geolocation**

Start the app (`python app.py`), open `http://localhost:5000/rutas/`. In the browser devtools console, run:

```js
navigator.geolocation.getCurrentPosition = function(success) {
  success({coords: {latitude: -34.5875, longitude: -58.4205}});
};
```

Then click "Usar mi ubicacion". Confirm: the origin `<select>` now shows "Mi ubicacion (GPS)" selected, and the free-text address field (`origenLibreWrap`) stays hidden. Then also test the failure path:

```js
navigator.geolocation.getCurrentPosition = function(success, error) {
  error({code: 1, message: 'denied'});
};
```

Click the button again, confirm the red error message appears below it.

- [ ] **Step 5: Commit**

```bash
git add routes_app.py
git commit -m "feat: add GPS-based origin option to route generation form"
```

---

## Task 2: "Cerca de mi" nearest-lead lookup on Mapa page

**Goal:** Find the nearest geocoded lead to the phone's GPS position, center the map on it, and show its detail with distance.

**Files:**
- Modify: `routes_app.py` (`PAGE_MAPA`)

**Acceptance Criteria:**
- [ ] Button calls `navigator.geolocation.getCurrentPosition()`
- [ ] Haversine distance computed to every lead in `allLeads` (all categories), finds the minimum
- [ ] Map centers on the nearest lead, `renderPanel()` opens with a distance row
- [ ] Empty `allLeads` or geolocation failure shows inline error
- [ ] `pytest -q` still 133 passed

**Verify:** Manual browser check with mocked geolocation.

**Steps:**

- [ ] **Step 1: Add the button and error message near the category tabs**

Find this block in `PAGE_MAPA`:

```html
<div class="cat-tabs">
  <button type="button" class="cat-tab active" data-cat="Todos" onclick="onCatTabClick(this)">Todos</button>
  <button type="button" class="cat-tab" data-cat="Repuestos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#0071e3;"></span>Repuestos</button>
  <button type="button" class="cat-tab" data-cat="Fundas" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#f58231;"></span>Fundas</button>
  <button type="button" class="cat-tab" data-cat="Telefonos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#3cb44b;"></span>Telefonos</button>
</div>

<button type="button" class="filtros-toggle-mapa" onclick="document.getElementById('filtros').classList.toggle('open')">Filtros de lotes</button>
```

Replace with:

```html
<div class="cat-tabs">
  <button type="button" class="cat-tab active" data-cat="Todos" onclick="onCatTabClick(this)">Todos</button>
  <button type="button" class="cat-tab" data-cat="Repuestos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#0071e3;"></span>Repuestos</button>
  <button type="button" class="cat-tab" data-cat="Fundas" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#f58231;"></span>Fundas</button>
  <button type="button" class="cat-tab" data-cat="Telefonos" onclick="onCatTabClick(this)">
    <span class="cat-dot" style="background:#3cb44b;"></span>Telefonos</button>
</div>

<button type="button" class="btn-secondary" id="btnCercaDeMi" onclick="cercaDeMi()">Cerca de mi</button>
<p id="ubicacionError" style="display:none; color:#dc2626; font-size:12px; margin-top:6px;"></p>

<button type="button" class="filtros-toggle-mapa" onclick="document.getElementById('filtros').classList.toggle('open')">Filtros de lotes</button>
```

- [ ] **Step 2: Add distance support to `renderPanel()`**

Find this in `PAGE_MAPA`'s script:

```javascript
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

Replace with:

```javascript
  function renderPanel(lead, prefix, distanciaTexto) {
    var panel = document.getElementById('panel');
    var ratingText = (lead.rating != null && lead.reviews_count != null)
      ? lead.rating + " (" + lead.reviews_count + " reviews)"
      : (lead.rating != null ? String(lead.rating) : (lead.reviews_count != null ? lead.reviews_count + " reviews" : ""));
    var categoriaText = lead.categorias ? lead.categorias.join(", ") : lead.categoria;
    var leadIds = lead.lead_ids || (lead.id ? [lead.id] : []);
    panel.innerHTML =
      '<div class="sheet-handle" onclick="closePanel()"></div>' +
      "<h3>" + (prefix || "") + escapeHtml(lead.negocio) + "</h3>" +
      (distanciaTexto ? panelRow("Distancia", distanciaTexto) : "") +
      panelRow("Categoria", categoriaText) +
      panelRow("Direccion", lead.direccion) +
      panelRow("Telefono", lead.telefono) +
      panelRow("Rating", ratingText) +
      (leadIds.length ? estadoSelectHtml(lead) : "");
    panel.classList.add('open');
```

(The rest of the function — the `estado-select` change-listener setup after this block — stays exactly as-is. Existing calls to `renderPanel(lead)` and `renderPanel(p, i === 0 ? "Origen — " : (i + ". "))` elsewhere are unaffected since `distanciaTexto` is optional.)

- [ ] **Step 3: Add haversine + `cercaDeMi()` functions**

Find this in `PAGE_MAPA`'s script (right after the `map.fitBounds`/`setView` block near the end):

```javascript
  if (allLeads.length > 0) {
    const bounds = L.latLngBounds(allLeads.map(function(l) { return [l.lat, l.lng]; }));
    map.fitBounds(bounds, {padding: [20, 20]});
  } else {
    map.setView([-34.6, -58.4], 12);
  }
```

Add this immediately after that block (still inside the same `<script>` tag):

```javascript

  function haversineMetros(lat1, lng1, lat2, lng2) {
    var R = 6371000;
    var toRad = function(d) { return d * Math.PI / 180; };
    var dLat = toRad(lat2 - lat1);
    var dLng = toRad(lng2 - lng1);
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function formatDistancia(metros) {
    if (metros < 1000) return Math.round(metros) + 'm';
    return (metros / 1000).toFixed(1) + 'km';
  }

  function cercaDeMi() {
    var errorMsg = document.getElementById('ubicacionError');
    errorMsg.style.display = 'none';
    if (!navigator.geolocation) {
      errorMsg.textContent = 'Tu navegador no soporta geolocalizacion.';
      errorMsg.style.display = 'block';
      return;
    }
    if (allLeads.length === 0) {
      errorMsg.textContent = 'No hay leads geocodificados para buscar.';
      errorMsg.style.display = 'block';
      return;
    }
    navigator.geolocation.getCurrentPosition(function(pos) {
      var lat = pos.coords.latitude;
      var lng = pos.coords.longitude;
      var closest = null;
      var closestDist = Infinity;
      allLeads.forEach(function(lead) {
        var dist = haversineMetros(lat, lng, lead.lat, lead.lng);
        if (dist < closestDist) {
          closestDist = dist;
          closest = lead;
        }
      });
      if (!closest) return;
      map.setView([closest.lat, closest.lng], 16);
      renderPanel(closest, "", formatDistancia(closestDist) + " de tu ubicacion");
    }, function() {
      errorMsg.textContent = 'No se pudo obtener tu ubicacion -- revisa los permisos del navegador.';
      errorMsg.style.display = 'block';
    });
  }
```

- [ ] **Step 4: Verify tests still pass**

Run: `python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 5: Manual check with mocked geolocation**

Open `http://localhost:5000/rutas/mapa`. First, find real coordinates of a known lead to mock near it — in the browser console:

```js
console.log(allLeads[0])
```

Note its `lat`/`lng`. Then mock geolocation close to that point (offset by a tiny amount so it's not an exact match):

```js
navigator.geolocation.getCurrentPosition = function(success) {
  success({coords: {latitude: allLeads[0].lat + 0.001, longitude: allLeads[0].lng + 0.001}});
};
```

Click "Cerca de mi". Confirm: the map centers/zooms on `allLeads[0]`'s location, and the detail panel/bottom-sheet opens showing its info plus a "Distancia" row with a small distance (under a few hundred meters). Then test the failure path the same way as Task 1's Step 4, confirming the error message appears.

- [ ] **Step 6: Commit**

```bash
git add routes_app.py
git commit -m "feat: add nearest-lead GPS lookup to Mapa page"
```

---

## Notes

- **Category filter is ignored on purpose** (per the approved spec) — "Cerca de mi" always searches all leads regardless of the active category tab. One consequence: if the nearest lead belongs to a category tab that isn't currently selected, its marker layer won't be visible on the map even though the detail panel opens and the map centers on its coordinates. This is accepted, not a bug — switching tabs automatically was not part of the approved design.
- **No reverse geocoding**: the GPS-based origin is always labeled literally "Mi ubicacion (GPS)", never a real street address.
- **No new tests**: both features are pure client-side JS with no backend logic changes; verification is manual only, per the approved spec.

## Deploying after this plan is done

Same as previous changes: commit and push to `main`, then on PythonAnywhere run `git pull` in the Bash console and click **Reload** on the Web tab.
