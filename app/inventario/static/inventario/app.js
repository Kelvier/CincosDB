(() => {
  const $ = id => document.getElementById(id);
  const B = document.body, TABLA = B.dataset.tabla, UNIDAD = B.dataset.unidad;
  const ADMIN = B.dataset.admin === "1", RAPIDA = B.dataset.rapida === "1";
  const META = JSON.parse($("meta").textContent), META_C = JSON.parse($("meta-contador").textContent);
  const csrf = () => (document.cookie.split("; ").find(c => c.startsWith("csrftoken=")) || "").split("=")[1] || "";
  const tb = el => el.classList.contains("card") ? "contador" : TABLA;
  const fmt = n => Number(n).toLocaleString("es-ES");
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  async function post(url, data) {
    const r = await fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(data) });
    let j = {}; try { j = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error(j.error || "Error de comunicación con el servidor.");
    return j;
  }
  function toast(msg, ok = true) {
    const t = $("toast"); t.textContent = msg; t.className = "show " + (ok ? "ok" : "ko");
    clearTimeout(t._t); t._t = setTimeout(() => t.className = "", 3200);
  }
  function pintar(el, f) {
    el.dataset.json = JSON.stringify(f);
    el.querySelectorAll("[data-campo]").forEach(td => {
      const c = td.dataset.campo;
      if (c === "estado") td.innerHTML = f.bajo ? '<span class="pill rojo">POCO</span>' : '<span class="pill verde">OK</span>';
      else if (c in f.texto) td.textContent = f.texto[c];
    });
    el.classList.toggle("bajo", f.bajo);
    el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 900);
  }
  function resumen(r) {
    Object.entries(r || {}).forEach(([k, v]) =>
      document.querySelectorAll(`[data-resumen="${k}"]`).forEach(e => e.textContent = v));
  }
  function aplicar(j) {
    (j.filas || []).forEach(f => {
      const tr = document.querySelector(`#tabla tr[data-pk="${f.pk}"]`); if (tr) pintar(tr, f);
    });
    if (j.contador) {
      const c = document.querySelector(`.card[data-pk="${j.contador.pk}"]`); if (c) pintar(c, j.contador);
    }
    resumen(j.resumen);
  }
  const piezas = () => [...document.querySelectorAll("#tabla tbody tr")].map(tr => {
    const f = JSON.parse(tr.dataset.json); return { pk: f.pk, d: f.datos };
  });

  // ----- reparación (ajuste rápido) -----
  async function ajustar(el, delta, btn) {
    btn.disabled = true;
    try {
      const j = await post(`/api/${tb(el)}/${el.dataset.pk}/ajustar/`, { delta });
      pintar(el, j.fila); resumen(j.resumen); toast("Guardado ");
      const i = el.querySelector(".cant"); if (i) i.value = 1;
    } catch (e) { toast(e.message, false); } finally { btn.disabled = false; }
  }

  // ----- edición avanzada -----
  let actual = null, metaAct = META;
  function construir(meta, datos) {
    metaAct = meta;
    const cont = $("dlg-campos"); cont.innerHTML = "";
    meta.forEach(m => {
      const w = document.createElement("label"); w.className = "campo";
      const s = document.createElement("span"); s.textContent = m.label; w.appendChild(s);
      let i;
      if (m.type === "select") {
        i = document.createElement("select"); m.choices.forEach(c => i.add(new Option(c, c)));
        i.value = datos[m.name] ?? m.choices[0];
      } else if (m.type === "bool") {
        i = document.createElement("input"); i.type = "checkbox"; i.checked = !!datos[m.name];
      } else {
        i = document.createElement("input"); i.type = m.type === "number" ? "number" : "text";
        if (m.type === "number") i.step = "1";
        i.value = datos[m.name] ?? (m.type === "number" ? 0 : "");
      }
      i.name = m.name; w.appendChild(i); cont.appendChild(w);
    });
    $("dlg-err").textContent = ""; $("dlg").showModal();
  }
  function abrirEditar(el) {
    const f = JSON.parse(el.dataset.json); actual = { el, nuevo: false };
    $("dlg-t").textContent = "Editar " + (f.datos.codigo || el.querySelector(".card-label").textContent);
    construir(el.classList.contains("card") ? META_C : META, f.datos);
  }
  $("frm").addEventListener("submit", async e => {
    e.preventDefault();
    const datos = {};
    metaAct.forEach(m => { const i = $("frm").elements[m.name]; datos[m.name] = m.type === "bool" ? i.checked : i.value; });
    try {
      if (actual.nuevo) { await post(`/api/${TABLA}/nuevo/`, { datos }); location.reload(); return; }
      const f = JSON.parse(actual.el.dataset.json);
      const j = await post(`/api/${tb(actual.el)}/${f.pk}/editar/`, { datos, version: f.version });
      pintar(actual.el, j.fila); resumen(j.resumen); $("dlg").close(); toast("Guardado ");
    } catch (err) { $("dlg-err").textContent = err.message; }
  });
  $("dlg-cancel").onclick = () => $("dlg").close();
  const bn = $("btn-nuevo");
  if (bn) bn.onclick = () => { actual = { nuevo: true }; $("dlg-t").textContent = "Nueva pieza"; construir(META, {}); };

  async function borrar(el) {
    const f = JSON.parse(el.dataset.json);
    if (!confirm(`¿Borrar ${f.datos.codigo} - ${f.datos.nombre}? Esta acción no se puede deshacer.`)) return;
    try { await post(`/api/${TABLA}/${f.pk}/borrar/`, {}); location.reload(); }
    catch (e) { toast(e.message, false); }
  }

  document.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    const el = b.closest("#tabla tr[data-pk], .card[data-pk]");
    if (!el) return;
    if (b.dataset.signo) {
      const cant = parseInt(el.querySelector(".cant").value, 10);
      if (!cant || cant < 1) return toast("Escribe una cantidad mayor que 0", false);
      ajustar(el, parseInt(b.dataset.signo, 10) * cant, b);
    } else if (b.dataset.ajuste) ajustar(el, parseInt(b.dataset.ajuste, 10), b);
    else if ("editar" in b.dataset) abrirEditar(el);
    else if ("borrar" in b.dataset) borrar(el);
  });

  // ----- filtros de la tabla -----
  function filtrar() {
    const q = $("buscar").value.toLowerCase().trim(), w = $("f-quien").value, bajo = $("f-bajo").checked;
    document.querySelectorAll("#tabla tbody tr").forEach(tr => {
      tr.hidden = !(tr.dataset.q.includes(q) && (!w || tr.dataset.quien === w) && (!bajo || tr.classList.contains("bajo")));
    });
  }
  ["buscar", "f-quien", "f-bajo"].forEach(id => $(id).addEventListener("input", filtrar));

  // ----- montar -----
  const nVal = id => Math.max(1, Math.min(1000, parseInt($(id).value, 10) || 1));
  function renderMontar() {
    const n = nVal("m-n"), forzar = $("m-forzar") && $("m-forzar").checked;
    let faltan = 0;
    $("m-body").innerHTML = piezas().filter(p => p.d.por_unidad > 0).map(p => {
      const need = p.d.por_unidad * n, queda = p.d.restante - need, ko = queda < 0;
      if (ko) faltan++;
      return `<tr class="${ko ? "bajo" : ""}"><td>${esc(p.d.codigo)}</td><td><b>${esc(p.d.nombre)}</b></td>
        <td>${fmt(need)}</td><td>${fmt(p.d.restante)}</td><td><b>${fmt(queda)}</b></td>
        <td><span class="pill ${ko ? "rojo" : "verde"}">${ko ? "FALTA" : "OK"}</span></td></tr>`;
    }).join("");
    const av = $("m-aviso");
    if (faltan) { av.className = "aviso ko"; av.textContent = ` Falta material en ${faltan} pieza${faltan > 1 ? "s" : ""}. No se puede montar ${n} ${UNIDAD}(s) con el stock actual.`; }
    else { av.className = "aviso ok"; av.textContent = ` Hay material suficiente para montar ${n} ${UNIDAD}(s).`; }
    $("m-ok").disabled = !!faltan && !forzar;
  }
  async function montar() {
    const n = nVal("m-n"), forzar = !!($("m-forzar") && $("m-forzar").checked);
    if (!confirm(`¿Montar ${n} ${UNIDAD}(s)? Se restarán los materiales del stock.`)) return;
    $("m-ok").disabled = true;
    try {
      const j = await post(`/api/${TABLA}/montar/`, { n, forzar });
      aplicar(j); toast(`${n} ${UNIDAD}(s) montada(s) `);
    } catch (e) { toast(e.message, false); }
    renderMontar();
  }

  // ----- reciclar -----
  const rec = {};
  function totalRec() {
    const v = Object.values(rec).filter(x => x > 0);
    $("r-total").textContent = v.length ? `${v.length} pieza(s) · ${fmt(v.reduce((a, b) => a + b, 0))} unidades recuperadas` : "Ninguna pieza marcada todavía";
  }
  function renderReciclar() {
    const n = nVal("r-n"), q = $("r-buscar").value.toLowerCase().trim();
    $("r-body").innerHTML = piezas().filter(p => p.d.por_unidad > 0 &&
      `${p.d.codigo} ${p.d.nombre}`.toLowerCase().includes(q)).map(p => {
      const max = p.d.por_unidad * n, v = Math.min(rec[p.pk] || 0, max); rec[p.pk] = v;
      return `<tr data-pk="${p.pk}" data-max="${max}"><td>${esc(p.d.codigo)}</td><td><b>${esc(p.d.nombre)}</b></td>
        <td>${fmt(max)}</td>
        <td><div class="stepper sm"><button type="button" data-r="-1">&#45;</button>
        <input type="number" class="rq" min="0" max="${max}" value="${v}" inputmode="numeric">
        <button type="button" data-r="1">+</button></div></td><td>${fmt(p.d.restante)}</td></tr>`;
    }).join("");
    totalRec();
  }
  function setRec(tr, val) {
    const max = parseInt(tr.dataset.max, 10);
    val = Math.max(0, Math.min(max, parseInt(val, 10) || 0));
    tr.querySelector(".rq").value = val; rec[tr.dataset.pk] = val; totalRec();
  }
  async function reciclar() {
    const n = nVal("r-n"), items = {};
    piezas().forEach(p => { const m = p.d.por_unidad * n, v = Math.min(rec[p.pk] || 0, m); if (v > 0) items[p.pk] = v; });
    if (!Object.keys(items).length) return toast("Marca al menos una pieza recuperada", false);
    if (!confirm(`¿Guardar el reciclaje de ${n} ${UNIDAD}(s)? Las piezas marcadas se sumarán al stock.`)) return;
    $("r-ok").disabled = true;
    try {
      const j = await post(`/api/${TABLA}/reciclar/`, { n, items });
      aplicar(j); Object.keys(rec).forEach(k => delete rec[k]); renderReciclar(); toast("Reciclaje guardado ");
    } catch (e) { toast(e.message, false); } finally { $("r-ok").disabled = false; }
  }

  if (RAPIDA) {
    document.querySelectorAll("[data-nstep]").forEach(b => b.onclick = () => {
      const i = $(b.dataset.target);
      i.value = Math.max(1, Math.min(1000, (parseInt(i.value, 10) || 1) + parseInt(b.dataset.nstep, 10)));
      b.dataset.target === "m-n" ? renderMontar() : renderReciclar();
    });
    $("m-n").addEventListener("input", renderMontar);
    if ($("m-forzar")) $("m-forzar").addEventListener("input", renderMontar);
    $("m-ok").onclick = montar;
    $("r-n").addEventListener("input", renderReciclar);
    $("r-buscar").addEventListener("input", renderReciclar);
    $("r-ok").onclick = reciclar;
    $("r-todas").onclick = () => { const n = nVal("r-n"); piezas().forEach(p => { if (p.d.por_unidad > 0) rec[p.pk] = p.d.por_unidad * n; }); renderReciclar(); };
    $("r-ninguna").onclick = () => { Object.keys(rec).forEach(k => delete rec[k]); renderReciclar(); };
    $("r-body").addEventListener("click", e => {
      const b = e.target.closest("button[data-r]"); if (!b) return;
      const tr = b.closest("tr"); setRec(tr, (parseInt(tr.querySelector(".rq").value, 10) || 0) + parseInt(b.dataset.r, 10));
    });
    $("r-body").addEventListener("input", e => { if (e.target.classList.contains("rq")) setRec(e.target.closest("tr"), e.target.value); });
  }

  // ----- pestañas -----
  const VISTAS = { rapida: "vista-tabla", avanzada: "vista-tabla", ver: "vista-tabla", montar: "vista-montar", reciclar: "vista-reciclar" };
  const permitido = m => m === "avanzada" ? ADMIN : ["rapida", "montar", "reciclar"].includes(m) ? RAPIDA : m === "ver";
  function modo(m) {
    B.className = "modo-" + m;
    document.querySelectorAll(".tab").forEach(b => b.classList.toggle("act", b.dataset.modo === m));
    new Set(Object.values(VISTAS)).forEach(id => { const v = $(id); if (v) v.hidden = id !== VISTAS[m]; });
    if (m === "montar") renderMontar();
    if (m === "reciclar") renderReciclar();
    history.replaceState(null, "", "#" + m);
  }
  document.querySelectorAll(".tab").forEach(b => b.onclick = () => modo(b.dataset.modo));
  let m0 = location.hash.slice(1);
  if (!permitido(m0)) m0 = RAPIDA ? "rapida" : ADMIN ? "avanzada" : "ver";
  modo(m0);
})();
