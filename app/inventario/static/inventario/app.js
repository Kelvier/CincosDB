(() => {
  const $ = id => document.getElementById(id);
  const B = document.body, TABLA = B.dataset.tabla;
  const ADMIN = B.dataset.admin === "1", RAPIDA = B.dataset.rapida === "1";
  const META = JSON.parse($("meta").textContent), META_C = JSON.parse($("meta-contador").textContent);
  const csrf = () => (document.cookie.split("; ").find(c => c.startsWith("csrftoken=")) || "").split("=")[1] || "";
  const tb = el => el.classList.contains("card") ? "contador" : TABLA;

  async function post(url, data) {
    const r = await fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(data) });
    let j = {}; try { j = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error(j.error || "Error de comunicación con el servidor.");
    return j;
  }
  function toast(msg, ok = true) {
    const t = $("toast"); t.textContent = msg; t.className = "show " + (ok ? "ok" : "ko");
    clearTimeout(t._t); t._t = setTimeout(() => t.className = "", 2500);
  }
  function pintar(el, f) {
    el.dataset.json = JSON.stringify(f);
    el.querySelectorAll("[data-campo]").forEach(td => {
      const c = td.dataset.campo;
      if (c === "estado") td.innerHTML = f.bajo ? '<span class="pill rojo">POCO</span>' : '<span class="pill verde">OK</span>';
      else if (c in f.texto) td.textContent = f.texto[c];
    });
    el.classList.toggle("bajo", f.bajo);
    el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 800);
  }
  function resumen(r) {
    Object.entries(r).forEach(([k, v]) =>
      document.querySelectorAll(`[data-resumen="${k}"]`).forEach(e => e.textContent = v));
  }

  // ----- edición rápida -----
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
    const el = b.closest("tr[data-pk], .card[data-pk]");
    if (!el) return;
    if (b.dataset.signo) {
      const cant = parseInt(el.querySelector(".cant").value, 10);
      if (!cant || cant < 1) return toast("Escribe una cantidad mayor que 0", false);
      ajustar(el, parseInt(b.dataset.signo, 10) * cant, b);
    } else if (b.dataset.ajuste) ajustar(el, parseInt(b.dataset.ajuste, 10), b);
    else if ("editar" in b.dataset) abrirEditar(el);
    else if ("borrar" in b.dataset) borrar(el);
  });

  // ----- filtros -----
  function filtrar() {
    const q = $("buscar").value.toLowerCase().trim(), w = $("f-quien").value, bajo = $("f-bajo").checked;
    document.querySelectorAll("#tabla tbody tr").forEach(tr => {
      tr.hidden = !(tr.dataset.q.includes(q) && (!w || tr.dataset.quien === w) && (!bajo || tr.classList.contains("bajo")));
    });
  }
  ["buscar", "f-quien", "f-bajo"].forEach(id => $(id).addEventListener("input", filtrar));

  // ----- modos -----
  function modo(m) {
    B.className = "modo-" + m;
    document.querySelectorAll(".modo").forEach(b => b.classList.toggle("act", b.dataset.modo === m));
    try { localStorage.setItem("modo", m); } catch (e) {}
  }
  document.querySelectorAll(".modo").forEach(b => b.onclick = () => modo(b.dataset.modo));
  let m = "rapida"; try { m = localStorage.getItem("modo") || "rapida"; } catch (e) {}
  if (m === "avanzada" && !ADMIN) m = "rapida";
  if (m === "rapida" && !RAPIDA) m = ADMIN ? "avanzada" : "ver";
  modo(m);
})();
