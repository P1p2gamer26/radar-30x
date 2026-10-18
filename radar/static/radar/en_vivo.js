// EstelarIA — /en-vivo/. Sin innerHTML: solo textContent/createElement.
const D = JSON.parse(document.getElementById("datos-vivo").textContent);
const $ = (id) => document.getElementById(id);
const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;
const f2 = (x) => Number(x).toFixed(2).replace(".", ",");
const pct = (x) => Math.round(x * 100) + " %";
const FUENTE = { hn: "HN", gnews: "Google News", linkedin: "LinkedIn", youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok", wiki: "Wikipedia" };
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

import { iniciarSim } from "./simulacion.js";

// ---- diagrama
const pipe = $("pipe"), nodos = {};
D.etapas.forEach((e, i) => {
  const b = el("button", "pnode");
  b.type = "button"; b.setAttribute("role", "listitem"); b.setAttribute("aria-expanded", "false");
  b.append(el("span", "pn", "ETAPA " + (i + 1)), el("span", "pt", e.nombre), el("span", "pv", e.valor), el("span", "nv", ""));
  b.addEventListener("click", () => abrir(e, b));
  pipe.append(b); nodos[e.id] = b;
});
function abrir(e, b) {
  const abierto = b.getAttribute("aria-expanded") === "true";
  Object.values(nodos).forEach((n) => n.setAttribute("aria-expanded", "false"));
  $("detalle").hidden = abierto;
  if (abierto) return;
  b.setAttribute("aria-expanded", "true");
  $("det-t").textContent = e.nombre + " — " + e.valor;
  $("det-p").textContent = e.texto;
  $("det-f").textContent = e.archivo;
}
const val = (id, t) => { nodos[id].querySelector(".nv").textContent = t; };
const limpiar = () => Object.values(nodos).forEach((n) => { n.classList.remove("lit", "esc"); n.querySelector(".nv").textContent = ""; });

// ---- valores por etapa para una señal (o una traza)
function valores(x) {
  const t = D.temas[x.tema];
  const seg = x.conf >= D.tau;
  const nombre = D.nombres[x.tema] || "fuera del radar";
  const decision = t ? t.decision : "Descartar";
  return [
    ["fuentes", x.fuente ? `${FUENTE[x.fuente] || x.fuente} · ${x.fecha}` : "texto pegado"],
    ["etiquetado", "ya aprendido de 2 LLM"],
    ["modelo", x.top3.map((q) => `${q.slug} ${pct(q.p)}`).join(" · ")],
    ["seguro", seg ? `${f2(x.conf)} ≥ τ ${f2(D.tau)}: seguro` : `${f2(x.conf)} < τ ${f2(D.tau)}: escalaría al LLM`, seg ? "" : "esc"],
    ["tendencia", t ? `${nombre}: ${t.stage}, ${f2(t.growth)}x` : "sin tema"],
    ["decision", t ? `p del tema ${f2(t.p)} → ${decision}` : "→ Descartar"],
    ["guiones", `${x.formato} · ${x.gancho}`],
    ["verificacion", "cifras contra piezas reales"],
    ["plan", decision === "Descartar" ? "fuera del plan" : "entra al plan"],
  ];
}
function iluminar(x, animar) {
  limpiar();
  const vs = valores(x);
  const paso = (i) => {
    const [id, txt, cls] = vs[i];
    nodos[id].classList.add(cls === "esc" ? "esc" : "lit"); val(id, txt);
  };
  if (!animar) { vs.forEach((_, i) => paso(i)); return; }
  vs.forEach((_, i) => setTimeout(() => paso(i), i * 170));
}

// ---- simulación (canvas) + log
const sim = iniciarSim($("sim-vivo"), D, { onSenal(s) {
  const seg = s.conf >= D.tau;
  iluminar(s, !reducido);
  const t = s.titulo.length > 70 ? s.titulo.slice(0, 70) + "…" : s.titulo;
  const li = el("li", seg ? "" : "esc", `[${(FUENTE[s.fuente] || s.fuente)}] '${t}' → tema: ${s.tema} (${f2(s.conf)}, ${seg ? "seguro" : "escalaría al LLM"}) · formato: ${s.formato} · gancho: ${s.gancho}`);
  $("log").prepend(li);
  while ($("log").children.length > 8) $("log").lastChild.remove();
} });

// ---- prueba la tuya
$("traza-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const err = $("traza-err"), res = $("traza-res");
  err.textContent = ""; res.replaceChildren();
  const texto = $("traza-texto").value.trim();
  if (!texto || texto.length > 2000) { err.textContent = "Escribe un texto de hasta 2000 caracteres."; return; }
  $("traza-btn").disabled = true;
  try {
    const r = await fetch("/api/traza/", { method: "POST", headers: { "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value }, body: new URLSearchParams({ texto }) });
    const j = await r.json();
    if (!r.ok) { err.textContent = j.error || "No se pudo analizar."; return; }
    const x = { fuente: "", tema: j.tema, top3: j.top3, conf: j.conf, formato: j.formato, gancho: j.gancho };
    const tema = D.temas[j.tema];
    iluminar(x, false);
    sim.inyectar({ ...x, tema_nombre: j.tema_nombre });
    val("tendencia", tema ? `${j.tema_nombre}: ${j.etapa}, ${f2(j.growth)}x` : "fuera del radar");
    val("decision", j.regla.split(";")[0]);
    val("plan", j.decision === "Descartar" ? "fuera del plan" : "entra al plan");
    const filas = [
      ["Texto limpio (sin emails, @usuarios, links)", j.limpio],
      ["Top-3 del modelo propio", j.top3.map((q) => `${q.slug} ${pct(q.p)}`).join(" · ")],
      ["¿Seguro?", `confianza ${f2(j.conf)} ${j.escala ? "<" : "≥"} τ ${f2(j.tau)} → ${j.escala ? "escalaría al LLM" : "responde el modelo propio"}`],
      ["Formato y gancho", `${j.formato} · ${j.gancho}`],
      ["Tema, etapa y crecimiento", `${j.tema_nombre} · ${j.etapa}` + (j.growth != null ? ` · ${f2(j.growth)}x` : "")],
      ["Decisión", j.regla],
    ];
    filas.forEach(([k, v]) => { const li = el("li"); li.append(el("b", "", k + ": "), document.createTextNode(v)); res.append(li); });
  } catch (e) { err.textContent = "No se pudo conectar."; } finally { $("traza-btn").disabled = false; }
});
