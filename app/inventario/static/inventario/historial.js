(() => {
  const $ = id => document.getElementById(id);
  const csrf = () => (document.cookie.split("; ").find(c => c.startsWith("csrftoken=")) || "").split("=")[1] || "";
  function toast(msg, ok = true) {
    const t = $("toast"); t.textContent = msg; t.className = "show " + (ok ? "ok" : "ko");
    clearTimeout(t._t); t._t = setTimeout(() => t.className = "", 3500);
  }
  function filtrar() {
    const q = $("h-buscar").value.toLowerCase().trim(), t = $("h-tipo").value, u = $("h-user").value;
    document.querySelectorAll("#hist tbody tr[data-q]").forEach(tr => {
      tr.hidden = !(tr.dataset.q.includes(q) && (!t || tr.dataset.tipo === t) && (!u || tr.dataset.user === u));
    });
  }
  ["h-buscar", "h-tipo", "h-user"].forEach(id => $(id).addEventListener("input", filtrar));

  document.addEventListener("click", async e => {
    const b = e.target.closest("button[data-deshacer]"); if (!b) return;
    if (!confirm("Se revertirá esta operación completa y el stock volverá a como estaba. Continuar?")) return;
    b.disabled = true;
    try {
      const r = await fetch(`/api/historial/${b.dataset.deshacer}/deshacer/`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: "{}" });
      let j = {}; try { j = await r.json(); } catch (x) {}
      if (!r.ok) throw new Error(j.error || "Error de comunicación con el servidor.");
      toast("Operación deshecha");
      setTimeout(() => location.reload(), 800);
    } catch (err) { toast(err.message, false); b.disabled = false; }
  });
})();
