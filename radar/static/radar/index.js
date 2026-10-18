// EstelarIA — frontend. Sin innerHTML con datos externos: solo textContent/createElement.
import { mountScene, sourceCounts } from "./scene.js";

const STATIC_SAMPLE_URL = (() => {
  // index.js vive junto a sample.json; funciona en Django (static) y en preview.html (relativo).
  const self = document.currentScript || Array.from(document.scripts).find((s) => s.src.includes("index.js"));
  if (self && self.src) {
    return new URL("sample.json", self.src).toString();
  }
  return "sample.json";
})();

const DECISION_COLOR = {
  Recomendar: "var(--lima)",
  Aprender: "var(--ambar)",
  Descartar: "var(--apagado)",
};

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function fmtGrowth(g) {
  return `x${g.toFixed(1)}`;
}

// Etapa en lenguaje simple (Temprano, Despegando, Estable, Pico/saturado, Cayendo).
function etapa(topic) {
  return topic.early_label || cap(topic.stage);
}

function cap(str) {
  const x = String(str || "");
  return x.charAt(0).toUpperCase() + x.slice(1);
}

// USD con los decimales justos: 0.000011 -> "USD 0.00001".
function fmtUsdSmall(n) {
  if (!n) return "USD 0";
  return `USD ${n.toFixed(Math.max(2, Math.min(8, -Math.floor(Math.log10(n)))))}`;
}

function fmtUsd(n) {
  if (n >= 1000) return `USD ${Math.round(n).toLocaleString("es-CO")}`;
  return `USD ${n.toFixed(2)}`;
}

function sparklineSvg(series, width = 90, height = 28) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "sparkline");
  svg.setAttribute("aria-hidden", "true");
  if (!series || series.length < 2) return svg;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = max - min || 1;
  const step = width / (series.length - 1);
  const points = series.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y];
  });
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "var(--lima)");
  path.setAttribute("stroke-width", "1.6");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

function countEarlyOrRising(topics) {
  return topics.filter(
    (t) => t.decision === "Recomendar"
  ).length; // ponytail: el titular promete solo lo que el radar recomienda producir ya
}

// Titular con plural correcto; se arma con nodos (el template trae el texto fijo).
function renderTitle(n) {
  const h1 = document.getElementById("hero-title");
  h1.textContent = "";
  if (n === 0) {
    h1.textContent = "Esta semana ningún tema de IA pide contenido urgente: esto es lo que se mueve.";
    return;
  }
  h1.appendChild(document.createTextNode("Esta semana, "));
  h1.appendChild(el("span", { class: "accent", id: "hero-count", text: String(n) }));
  h1.appendChild(document.createTextNode(n === 1 ? " tema de IA pide contenido ya." : " temas de IA piden contenido ya."));
}

function renderHero(data) {
  const weekEl = document.getElementById("hero-week");
  const n = countEarlyOrRising(data.topics || []);
  renderTitle(n);
  const date = data.generated_at ? new Date(data.generated_at) : new Date();
  const dateStr = date.toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
  weekEl.textContent = `Semana ${data.week || ""} · ${dateStr}`;
}

// Microguía "toca una estrella": se muestra hasta el primer clic (localStorage opcional).
const CLAVE_GUIA = "radar_guia_vista";
function guiaVista() {
  try { return localStorage.getItem(CLAVE_GUIA) === "1"; } catch (e) { return false; }
}
function setupGuide() {
  const guide = document.getElementById("hero-guide");
  if (guide && !guiaVista()) guide.hidden = false;
}
function hideGuide() {
  const guide = document.getElementById("hero-guide");
  if (guide) guide.hidden = true;
  try { localStorage.setItem(CLAVE_GUIA, "1"); } catch (e) { /* sin almacenamiento: se oculta solo esta visita */ }
}

// "Esta semana produce:" las 2-3 tarjetas Recomendar, todo desde radar.json.
function renderProduce(data, onOpen) {
  const sec = document.getElementById("produce");
  const grid = document.getElementById("produce-grid");
  const recs = (data.topics || []).filter((t) => t.decision === "Recomendar").slice(0, 3);
  if (!sec || !grid || !recs.length) return;
  for (const t of recs) {
    const src = (t.top_signals || [])[0];
    const plat = (t.adapt && t.adapt.platform) || (src && (PLATFORM_NAME[src.source] || src.source)) || "";
    const porQue = String(t.reason || "").split(";")[0];
    grid.appendChild(
      el("article", { class: "produce-card" }, [
        el("span", { class: "produce-plat", text: plat }),
        el("h3", { text: t.name }),
        el("p", { text: `${porQue}.` }),
        el("button", { class: "produce-btn", type: "button", text: "Ver guion", "aria-label": `Ver guion de ${t.name}`, onclick: () => onOpen(t.slug) }),
      ])
    );
  }
  sec.hidden = false;
}

function renderRankingRow(topic, onOpen) {
  const pct = Math.max(0, Math.min(1, topic.p)) * 100;
  const color = DECISION_COLOR[topic.decision] || "var(--gris)";

  const pBar = el("div", { class: "p-bar-track" }, [
    el("div", { class: "p-bar-fill", style: `width:${pct}%; background:${color};` }),
  ]);
  pBar.style.cssText = `position:relative;height:6px;border-radius:999px;background:var(--linea);overflow:hidden;`;
  pBar.firstChild.style.cssText = `position:absolute;inset:0 auto 0 0;height:100%;border-radius:999px;background:${color};width:${pct}%;`;

  const decisionCell = el("div", { class: "decision-cell" }, [
    el("span", { class: `decision-label decision-${topic.decision}`, text: topic.decision }),
    el("span", { class: "decision-reason", text: topic.reason, title: topic.reason }),
  ]);

  const row = el(
    "button",
    {
      class: "ranking-row",
      role: "listitem",
      "aria-label": `Abrir detalle de ${topic.name}`,
      onclick: () => onOpen(topic.slug),
    },
    [
      el("span", { class: "rank nums", text: `#${topic.rank}` }),
      el("span", { class: "name", text: topic.name }),
      el("span", { class: "stage-chip", text: etapa(topic) }),
      el("span", { class: "growth nums", text: fmtGrowth(topic.growth) }),
      sparklineSvg(topic.series),
      pBar,
      decisionCell,
    ]
  );
  return row;
}

function renderRanking(data, onOpen) {
  const list = document.getElementById("ranking-list");
  const top10 = (data.topics || []).slice(0, 10);
  for (const topic of top10) {
    list.appendChild(renderRankingRow(topic, onOpen));
  }
}

function renderBarList(container, titleText, entries) {
  const card = el("div", { class: "why-card" }, [el("h3", { text: titleText })]);
  const sorted = Object.entries(entries || {}).sort((a, b) => b[1] - a[1]);
  const max = sorted.length ? sorted[0][1] : 1;
  for (const [label, value] of sorted) {
    const pct = Math.max(2, (value / (max || 1)) * 100);
    const fill = el("div", { class: "bar-fill" });
    fill.style.width = `${pct}%`;
    const row = el("div", { class: "bar-row" }, [
      el("span", { class: "bar-label", text: label }),
      el("div", { class: "bar-track" }, [fill]),
      el("span", { class: "bar-value nums", text: `${Math.round(value * 100)}%` }),
    ]);
    card.appendChild(row);
  }
  container.appendChild(card);
}

function renderWhy(data) {
  const grid = document.getElementById("why-grid");
  const top = (data.topics || [])[0];
  if (!top) return;

  const summary = el("div", { class: "why-card" }, [
    el("h3", { text: `Tema #1: ${top.name}` }),
    el("p", { text: `Formato ganador: ${legible(top.why.format_winner)}. Gancho ganador: ${legible(top.why.hook_winner)}. Mejor día: ${top.why.best_day}.` }),
  ]);
  grid.appendChild(summary);

  renderBarList(grid, "Formatos (agregado)", top.why.formats);
  renderBarList(grid, "Ganchos (agregado)", top.why.hooks);
  renderBarList(grid, "Mezcla de autores", top.why.author_mix);
}

const NOMBRE_LEGIBLE = {"reel-cara": "Reel/short con cara hablando a cámara", "carrusel": "Carrusel / PDF documento", "post-texto": "Post de texto largo", "caso-paso-a-paso": "Caso de uso paso a paso / demo de proceso", "herramienta-60s": "Herramienta X en 60 segundos", "noticia-explicada": "Noticia explicada (qué significa para tu empresa)", "entrevista-clip": "Entrevista / clip de charla", "lista-ranking": "Lista / ranking", "opinion": "Opinión / predicción", "evento-live": "Live / webinar / evento", "resultado-numero": "Resultado cuantificado", "error-confesion": "Error o confesión", "pregunta": "Pregunta provocadora", "contrarian": "Contrarian / rompe un mito", "promesa-proceso": "Promesa de proceso (paso a paso)", "autoridad": "Autoridad / nombre propio", "urgencia-novedad": "Urgencia / novedad", "miedo-riesgo": "Miedo / riesgo", "lista-numerada": "Lista numerada", "antes-despues": "Antes / después"};
const legible = (k) => NOMBRE_LEGIBLE[k] || k || "sin datos";

function renderCost(data) {
  const grid = document.getElementById("cost-grid");
  const t = data.totals || {};
  const perSignal = t.cost_per_signal_usd || 0;
  const items = [
    { label: "Costo por señal", value: fmtUsdSmall(perSignal) },
    { label: "USD por 1.000 señales", value: fmtUsdSmall(perSignal * 1000) },
    { label: `Costo de la IA de entrenamiento (${t.teacher_model || "LLM"})`, value: fmtUsd(t.teacher_cost_usd || 0) },
    { label: "Costo del modelo propio", value: fmtUsd(t.student_cost_usd || 0) },
    { label: "Señales procesadas", value: (t.signals || 0).toLocaleString("es-CO") },
  ];
  for (const item of items) {
    grid.appendChild(
      el("div", { class: "cost-card" }, [
        el("span", { class: "cost-value nums", text: item.value }),
        el("span", { class: "cost-label", text: item.label }),
      ])
    );
  }
  const highlight = el("p", { class: "cost-highlight" });
  const semanal = t.weekly_cost_usd ?? 0;
  highlight.appendChild(document.createTextNode("Cada semana cuesta "));
  highlight.appendChild(el("strong", { text: fmtUsd(semanal) }));
  highlight.appendChild(document.createTextNode(` (Instagram y TikTok vía Apify, ${t.apify_cost_source && t.apify_cost_source !== "estimado" ? "medido" : "estimado"}; el modelo propio clasifica gratis), unos ${fmtUsd(semanal * 52)} al año. El entrenamiento inicial con el LLM costó ${fmtUsd(t.teacher_cost_usd || 0)} una sola vez. El scraping pago cuesta `));
  highlight.appendChild(el("strong", { text: fmtUsd(t.paid_alternative_usd_year || 0) }));
  highlight.appendChild(document.createTextNode(" al año."));
  grid.appendChild(highlight);

  // Precisión del modelo propio por tarea: solo se presenta como mérito donde supera la base por >= 3 puntos.
  const student = data.student || {};
  const pct = (v) => `${Math.round(v * 100)}%`;
  // ponytail: la home muestra el modelo del radar (offline, el que clasifica todo); el escáner tiene su propia cifra en /como-funciona
  const mt = (student.topic && student.topic.offline) || student.topic || {};
  const tarjetas = [
    [mt.holdout_accuracy, "Acierta el tema de una pieza (prueba aparte)"],
    [mt.holdout_top3, "El tema correcto está entre sus 3 primeras opciones"],
    [mt.safe_accuracy, `Acierto cuando está seguro (${typeof mt.safe_coverage === "number" ? pct(mt.safe_coverage) : "?"} de las piezas)`],
  ];
  for (const [v, txt] of tarjetas) {
    if (typeof v !== "number") continue;
    grid.appendChild(el("div", { class: "cost-card" }, [
      el("span", { class: "cost-value nums", text: pct(v) }),
      el("span", { class: "cost-label", text: `${txt}. Adivinando: ${typeof mt.holdout_baseline === "number" ? pct(mt.holdout_baseline) : "?"}` }),
    ]));
  }
}

// --- Lo que mejor le funcionó a 30X (top 3 del benchmark) ---
function renderBench(data) {
  const grid = document.getElementById("bench-grid");
  const items = (data.benchmark_30x || []).slice(0, 3);
  if (!grid || !items.length) {
    const sec = document.getElementById("bench-30x");
    if (sec) sec.hidden = true;
    return;
  }
  for (const b of items) {
    const real = typeof b.metric_value === "number" ? b.metric_value : b.views;
    const label = b.metric_label || "vistas";
    grid.appendChild(
      el("div", { class: "bench-card" }, [
        el("span", { class: "bench-x nums", text: `${b.outlier}x` }),
        el("span", { class: "bench-meta", text: `sus ${label} normales · ${real.toLocaleString("es-CO")} ${label} reales` }),
        el("a", { href: b.url, target: "_blank", rel: "noopener noreferrer", text: b.title }),
        el("span", { class: "bench-meta", text: `${b.platform || b.source} · ${b.format_name || b.format || ""}` }),
        el("span", { class: "bench-meta", text: `Gancho: ${b.hook_name || b.hook || ""}` }),
      ])
    );
  }
}

// --- Panel lateral ---

let lastFocused = null;

let onPanelClose = null; // la escena borra los rayos y vuelve a la vista general

function closePanel() {
  if (onPanelClose) onPanelClose();
  const overlay = document.getElementById("panel-overlay");
  const panel = document.getElementById("panel");
  overlay.classList.remove("open");
  panel.classList.remove("open");
  panel.setAttribute("aria-hidden", "true");
  if (lastFocused) lastFocused.focus();
}

let UMBRALES = [0.8, 0.5]; // se reemplaza con data.calibration.thresholds

function renderThreshold(p) {
  const track = el("div", { class: "threshold-track" });
  const fill = el("div", { class: "threshold-fill" });
  fill.style.width = `${Math.max(0, Math.min(1, p)) * 100}%`;
  track.appendChild(fill);
  for (const [value, label] of [[UMBRALES[0], `${UMBRALES[0].toFixed(2)} Recomendar`], [UMBRALES[1], `${UMBRALES[1].toFixed(2)} Aprender`]]) {
    const mark = el("div", { class: "threshold-mark" });
    mark.style.left = `${value * 100}%`;
    mark.appendChild(el("span", { class: "mark-label", text: label }));
    track.appendChild(mark);
  }
  return track;
}

// --- De dónde viene la info ---
const SRC_ORDER = ["linkedin", "instagram", "tiktok", "youtube", "hn", "gnews", "wiki"];
const SRC_NAME = { linkedin: "LinkedIn", instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube", hn: "Hacker News", gnews: "Google News", wiki: "Wikipedia" };
const SRC_HOW = {
  linkedin: "Titulares de Google News sobre publicaciones de LinkedIn (no se entra a LinkedIn).",
  instagram: "Contenido público de Instagram recogido con Apify.",
  tiktok: "Contenido público de TikTok recogido con Apify.",
  youtube: "API pública de YouTube: videos recientes por tema.",
  hn: "API pública de Hacker News: historias con puntos y comentarios.",
  gnews: "Titulares de Google News vía RSS.",
  wiki: "API pública de Wikipedia: visitas diarias de los artículos del tema.",
};
const nf = (n) => Number(n).toLocaleString("es-CO");

function metricText(sig) {
  const m = sig.metrics || {};
  const out = [];
  if (m.views > 0) out.push(`${nf(m.views)} vistas`);
  if (m.points > 0) out.push(`${nf(m.points)} ${sig.source === "hn" ? "puntos" : "me gusta"}`);
  if (m.comments > 0) out.push(`${nf(m.comments)} comentarios`);
  return out.join(" · ");
}

function renderOrigin(topic) {
  const sec = el("div", { class: "panel-section" }, [el("h3", { text: "De dónde viene" })]);
  const counts = sourceCounts(topic);
  const sigs = topic.top_signals || [];
  const keys = [...SRC_ORDER, ...Object.keys(counts).filter((k) => !SRC_ORDER.includes(k))].filter((k) => counts[k] > 0);
  if (!keys.length) {
    sec.appendChild(el("p", { class: "guion-meta", text: "Sin piezas registradas esta semana." }));
    return sec;
  }
  const max = Math.max(...keys.map((k) => counts[k]));
  for (const k of keys) {
    const bar = el("div", { class: "origin-bar" }, [el("i")]);
    bar.firstChild.style.width = `${(counts[k] / max) * 100}%`;
    const group = el("div", { class: "origin-group" }, [
      el("div", { class: "origin-head" }, [
        el("b", { text: SRC_NAME[k] || k }),
        el("span", { class: "nums", text: `${counts[k]} ${counts[k] === 1 ? "pieza" : "piezas"}` }),
      ]),
      bar,
    ]);
    for (const sig of sigs.filter((x) => x.source === k)) {
      const mt = metricText(sig);
      group.appendChild(
        el("div", { class: "signal-item" }, [
          el("a", { href: sig.url, target: "_blank", rel: "noopener noreferrer", text: sig.title }),
          el("div", { class: "signal-meta", text: [mt, sig.format, sig.hook].filter(Boolean).join(" · ") }),
        ])
      );
    }
    sec.appendChild(group);
  }
  return sec;
}

// Planeta tocado: qué trae esa red y sus 3 temas principales.
function openSourcePanel(data, name, onOpen) {
  const info = (data.sources || []).find((x) => x.name === name) || {};
  const ranked = (data.topics || [])
    .map((t) => ({ t, c: sourceCounts(t)[name] || 0 }))
    .filter((x) => x.c > 0)
    .sort((a, b) => b.c - a.c || (b.t.p || 0) - (a.t.p || 0))
    .slice(0, 3);
  const list = el("div", { class: "panel-section" }, [el("h3", { text: "Sus 3 temas principales" })]);
  if (!ranked.length) list.appendChild(el("p", { class: "guion-meta", text: "Sin temas con piezas de esta red." }));
  for (const { t, c } of ranked) {
    list.appendChild(
      el("button", { type: "button", class: "origin-topic", onclick: () => onOpen(t.slug) }, [
        el("b", { text: t.name }),
        el("span", { class: "nums", text: `${c} ${c === 1 ? "pieza" : "piezas"}` }),
      ])
    );
  }
  showPanel(
    SRC_NAME[name] || name,
    [el("span", { class: "stage-chip", text: "Red" })],
    [
      el("div", { class: "panel-section" }, [
        el("h3", { text: "Qué trae esta red" }),
        el("p", { class: "nums", text: `${nf(info.signals || 0)} piezas esta semana.` }),
      ]),
      el("div", { class: "panel-section" }, [el("h3", { text: "Cómo se obtiene" }), el("p", { text: SRC_HOW[name] || "Fuente pública." })]),
      list,
    ],
    document.activeElement
  );
}

// Guiones del tema en pestañas: LinkedIn/YouTube y Reel IG/TikTok, cada uno con "Copiar".
function copyBtn(getText) {
  const btn = el("button", {
    class: "copy-btn",
    text: "Copiar guion",
    onclick: async () => {
      try {
        await navigator.clipboard.writeText(getText());
        btn.textContent = "Copiado";
        setTimeout(() => (btn.textContent = "Copiar guion"), 1600);
      } catch (e) {
        btn.textContent = "No se pudo copiar";
      }
    },
  });
  return btn;
}

function guionLinkedin(a) {
  const text = [a.title, `Plataforma: ${a.platform} · ${a.format}`, `Gancho: ${a.hook}`, ...a.beats.map((b) => `- ${b}`), `CTA: ${a.cta}`].join("\n");
  const beats = el("ol", { class: "beats-list" }, a.beats.map((b) => el("li", { text: b })));
  return el("div", {}, [
    el("p", { class: "guion-titulo", text: a.title }),
    el("p", { class: "guion-meta", text: `${a.platform} · ${a.format}` }),
    el("p", { text: `Gancho de 3 segundos: ${a.hook}` }),
    beats,
    el("p", { class: "acento", text: a.cta }),
    copyBtn(() => text),
  ]);
}

function guionReel(r) {
  const text = [`Reel ${r.platform} · ${r.duration}`, `Gancho (0-3 s): ${r.hook}`, ...r.shots.map((s) => `${s.seg} s: ${s.visual} | Texto: ${s.texto}`), `CTA: ${r.cta}`].join("\n");
  const shots = el("ol", { class: "beats-list" }, r.shots.map((s) => el("li", {}, [el("strong", { text: `${s.seg} s` }), ` · ${s.visual}`, el("br"), el("span", { class: "guion-meta", text: `En pantalla: ${s.texto}` })])));
  return el("div", {}, [
    el("p", { class: "guion-meta", text: `${r.platform} · reel vertical de ${r.duration}` }),
    el("p", { text: `Gancho (0-3 s): ${r.hook}` }),
    shots,
    el("p", { class: "acento", text: r.cta }),
    copyBtn(() => text),
  ]);
}

function renderGuiones(topic) {
  const sec = el("div", { class: "panel-section" }, [el("h3", { text: "Así lo haría 30X" })]);
  if (!topic.adapt) {
    sec.appendChild(el("p", { class: "guion-meta", text: "Guion en preparación." }));
    return sec;
  }
  const panes = [["LinkedIn / YouTube", guionLinkedin(topic.adapt)]];
  if (topic.adapt_reel) panes.push(["Reel IG / TikTok", guionReel(topic.adapt_reel)]);
  else if (topic.decision !== "Descartar") panes.push(["Reel IG / TikTok", el("p", { class: "guion-meta", text: "Guion en preparación." })]);
  const bar = el("div", { class: "tab-bar", role: "tablist" });
  const tabs = panes.map(([name, node], i) => {
    node.hidden = i !== 0;
    const t = el("button", {
      type: "button", class: i === 0 ? "tab on" : "tab", role: "tab", text: name,
      onclick: () => panes.forEach(([, n], j) => { n.hidden = j !== i; tabs[j].classList.toggle("on", j === i); }),
    });
    return t;
  });
  tabs.forEach((t) => bar.appendChild(t));
  sec.appendChild(bar);
  panes.forEach(([, n]) => sec.appendChild(n));
  return sec;
}

function showPanel(titleText, metaNodes, bodyNodes, triggerEl) {
  lastFocused = triggerEl || document.activeElement;
  const overlay = document.getElementById("panel-overlay");
  const panel = document.getElementById("panel");
  document.getElementById("panel-title").textContent = titleText;
  const meta = document.getElementById("panel-meta");
  const body = document.getElementById("panel-body");
  meta.textContent = "";
  metaNodes.forEach((n) => meta.appendChild(n));
  body.textContent = "";
  bodyNodes.forEach((n) => body.appendChild(n));
  body.scrollTop = 0;
  overlay.classList.add("open");
  panel.classList.add("open");
  panel.setAttribute("aria-hidden", "false");
  document.getElementById("panel-close").focus();
}

function openPanel(topic, triggerEl) {
  const resumen = el("div", { class: "panel-section" }, [
    el("h3", { text: "Resumen" }),
    el("p", { text: topic.reason, title: topic.reason }),
    renderThreshold(topic.p),
    el("p", { class: "nums", text: `Qué tan listo está para publicar: ${Math.round(topic.p * 100)} de 100 · le sirve a tu audiencia: ${Math.round(topic.exec_fit * 100)} de 100` }),
  ]);
  showPanel(
    topic.name,
    [
      el("span", { class: "stage-chip", text: etapa(topic) }),
      el("span", { class: "growth nums", text: fmtGrowth(topic.growth) }),
      el("span", { class: `decision-label decision-${topic.decision}`, text: topic.decision }),
    ],
    [resumen, renderOrigin(topic), renderGuiones(topic)],
    triggerEl
  );
}

function setupPanelClosers() {
  const overlay = document.getElementById("panel-overlay");
  const panel = document.getElementById("panel");
  document.getElementById("panel-close").addEventListener("click", closePanel);
  overlay.addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("open")) closePanel();
    if (e.key === "Tab" && panel.classList.contains("open")) {
      const focusables = panel.querySelectorAll("a, button, [tabindex]");
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
}

function renderFallback2D(canvas, topics) {
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("class", "hero-fallback");
  svg.setAttribute("viewBox", "0 0 800 450");
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
  const n = Math.min(topics.length, 12) || 1;
  topics.slice(0, 12).forEach((t, i) => {
    const angle = (i / n) * Math.PI * 2;
    const r = 120 + (t.p || 0.3) * 140;
    const cx = 400 + Math.cos(angle) * r;
    const cy = 225 + Math.sin(angle) * r * 0.6;
    const radius = 6 + (t.volume || 10) / 10;
    const color = t.decision === "Recomendar" ? "#6f94ff" : t.decision === "Aprender" ? "#FFCC6E" : "#6e6a9e";
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", cx.toFixed(1));
    circle.setAttribute("cy", cy.toFixed(1));
    circle.setAttribute("r", radius.toFixed(1));
    circle.setAttribute("fill", color);
    circle.setAttribute("opacity", "0.85");
    svg.appendChild(circle);
  });
  canvas.replaceWith(svg);
  return svg;
}

// --- Descubrimiento en vivo (hero) ---
const PLATFORMS = ["linkedin", "youtube", "hn", "gnews"];
const PLATFORM_NAME = { linkedin: "LinkedIn", youtube: "YouTube", hn: "Hacker News", gnews: "Google News" };
const SVG_NS = "http://www.w3.org/2000/svg";

// Un hallazgo por tema (por p, Recomendar/Aprender primero) rotando plataforma entre hallazgos consecutivos.
function buildQueue(topics) {
  const rank = { Recomendar: 0, Aprender: 1 };
  const sorted = [...topics].sort(
    (a, b) => (rank[a.decision] ?? 2) - (rank[b.decision] ?? 2) || (b.p || 0) - (a.p || 0)
  );
  const queue = [];
  let ptr = 0;
  let prev = null;
  for (const topic of sorted) {
    const sigs = topic.top_signals || [];
    const avail = [0, 1, 2, 3]
      .map((o) => (ptr + o) % PLATFORMS.length)
      .filter((i) => sigs.some((s) => s.source === PLATFORMS[i]));
    if (!avail.length) continue;
    const pick = avail.find((i) => PLATFORMS[i] !== prev) ?? avail[0];
    prev = PLATFORMS[pick];
    ptr = pick + 1;
    queue.push({ topic, signal: sigs.find((s) => s.source === prev) });
  }
  return queue;
}

function ago(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  if (!iso || !isFinite(ms) || ms < 0) return "";
  const min = Math.round(ms / 60000);
  if (min < 60) return ` · hace ${Math.max(1, min)} min`;
  const h = Math.round(min / 60);
  return h < 48 ? ` · hace ${h} h` : ` · hace ${Math.round(h / 24)} d`;
}

function growthText(g) {
  if (g > 1.15) return `Crece ${g.toFixed(1)}x`;
  if (g < 0.9) return "Cae";
  return "Ritmo constante";
}

function setupDiscovery(hero, data, scene, onOpen) {
  const queue = buildQueue(data.topics || []);
  if (!queue.length) return;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const total = (data.totals && data.totals.signals) || 0;

  const line = document.createElementNS(SVG_NS, "line");
  const dot = document.createElementNS(SVG_NS, "circle");
  dot.setAttribute("r", "3");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "disc-line");
  svg.setAttribute("aria-hidden", "true");
  svg.append(line, dot);

  const status = el("p", { class: "disc-status" });
  status.append("Escaneando LinkedIn, Instagram, TikTok, YouTube, Hacker News y Google News");
  status.appendChild(el("span", { class: "disc-dots" }, [el("i"), el("i"), el("i")]));
  const stack = el("div", { class: "disc-stack" });
  const counter = el("p", { class: "disc-count nums" });
  const box = el("div", { class: "disc" }, [status, stack, counter]);
  hero.append(svg, box);

  let found = 0;
  let scanned = reduced ? total : 0;
  const paintCount = () => {
    counter.textContent = `${found} ${found === 1 ? "hallazgo" : "hallazgos"} · ${scanned.toLocaleString("es-CO")} señales escaneadas`;
  };
  paintCount();

  let current = null; // { node, slug }
  let hover = false;
  const panelOpen = () => document.getElementById("panel").classList.contains("open");
  const paused = () => hover || document.hidden || panelOpen() || document.getElementById("hero").classList.contains("exploring");

  function drawLine() {
    requestAnimationFrame(drawLine);
    if (!current || !scene || !current.node.isConnected) return svg.classList.remove("on");
    const pos = scene.screenPos(current.slug);
    if (!pos) return svg.classList.remove("on");
    const h = hero.getBoundingClientRect();
    const c = current.node.getBoundingClientRect();
    const cx = Math.max(c.left - h.left, Math.min(pos.x, c.right - h.left));
    const cy = Math.max(c.top - h.top, Math.min(pos.y, c.bottom - h.top));
    line.setAttribute("x1", cx);
    line.setAttribute("y1", cy);
    line.setAttribute("x2", pos.x);
    line.setAttribute("y2", pos.y);
    dot.setAttribute("cx", pos.x);
    dot.setAttribute("cy", pos.y);
    svg.classList.add("on");
  }
  if (scene) drawLine();

  function showCard({ topic, signal }) {
    const color = DECISION_COLOR[topic.decision] || "var(--gris)";
    const dec = el("span", { class: "disc-chip", text: topic.decision });
    dec.style.color = color;
    dec.style.borderColor = color;
    const node = el(
      "button",
      { class: "disc-card", "aria-label": `Abrir ${topic.name}`, onclick: () => onOpen(topic.slug) },
      [
        el("span", { class: "disc-src" }, [
          el("b", { text: PLATFORM_NAME[signal.source] || signal.source }),
          ago(signal.published_at),
        ]),
        el("span", { class: "disc-title", text: `Nueva estrella descubierta: ${topic.name}` }),
        el("span", { class: "disc-sig", text: signal.title }),
        el("span", { class: "disc-chips" }, [
          el("span", { class: "disc-chip", text: etapa(topic) }),
          el("span", { class: "disc-chip", text: growthText(topic.growth || 1) }),
          dec,
        ]),
      ]
    );
    const old = current && current.node;
    if (old) {
      old.classList.add("out");
      setTimeout(() => old.remove(), 220);
    }
    node.classList.add("enter");
    stack.appendChild(node);
    requestAnimationFrame(() => requestAnimationFrame(() => node.classList.remove("enter")));
    current = { node, slug: topic.slug };
    found += 1;
    paintCount();
  }

  for (const ev of ["mouseenter", "focusin"]) box.addEventListener(ev, () => (hover = true));
  for (const ev of ["mouseleave", "focusout"]) box.addEventListener(ev, () => (hover = false));

  if (reduced) {
    status.hidden = true;
    showCard(queue[0]);
    return;
  }

  // Espera que se congela mientras paused().
  const wait = (ms) =>
    new Promise((resolve) => {
      let left = ms;
      const id = setInterval(() => {
        if (paused()) return;
        left -= 100;
        if (left <= 0) {
          clearInterval(id);
          resolve();
        }
      }, 100);
    });

  (async () => {
    // 1 s de "buscando": el contador de señales sube.
    const t0 = performance.now();
    await new Promise((resolve) => {
      const step = () => {
        const k = Math.min(1, (performance.now() - t0) / 1000);
        scanned = Math.round(total * k);
        paintCount();
        if (k < 1) requestAnimationFrame(step);
        else resolve();
      };
      step();
    });
    for (let i = 0; ; i = (i + 1) % queue.length) {
      if (current) await wait(3000);
      if (scene) await scene.discover(queue[i].topic.slug, queue[i].signal.source);
      showCard(queue[i]);
    }
  })();
}

// Modo explorar: cámara libre (OrbitControls), sin textos del hero; Esc o "Volver" salen.
function setupExplore(hero, scene) {
  const btn = document.getElementById("explore-btn");
  const back = document.getElementById("explore-back");
  if (!btn || !back) return;
  if (!scene) {
    btn.hidden = true;
    return;
  }
  const set = (on) => {
    if (on) closePanel();
    scene.setExplore(on);
    hero.classList.toggle("exploring", on);
    if (on) hero.scrollIntoView({ block: "start", behavior: "auto" });
    (on ? back : btn).focus();
  };
  btn.addEventListener("click", () => set(true));
  back.addEventListener("click", () => set(false));
  document.addEventListener(
    "keydown",
    (e) => {
      const panelOpen = document.getElementById("panel").classList.contains("open");
      if (e.key === "Escape" && scene.isExplore() && !panelOpen) set(false);
    },
    true
  );
}

async function loadData() {
  try {
    const res = await fetch("/api/radar.json");
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.topics) && data.topics.length) return data;
    }
  } catch (e) {
    // sigue con el sample
  }
  const res2 = await fetch(STATIC_SAMPLE_URL);
  return res2.json();
}

async function main() {
  const data = await loadData();
  const th = data.calibration && data.calibration.thresholds;
  if (Array.isArray(th) && th.length === 2) UMBRALES = th;
  renderHero(data);
  setupGuide();

  setupPanelClosers();

  let scene = null;
  // Desde la escena (ya vuela y dibuja rayos) o desde listas (vuela además a la estrella).
  const onOpen = (slug) => {
    const topic = data.topics.find((t) => t.slug === slug);
    if (topic) {
      hideGuide();
      openPanel(topic, document.activeElement);
    }
  };
  const onOpenList = (slug) => {
    if (scene) scene.focus(slug);
    onOpen(slug);
  };

  renderProduce(data, onOpenList);
  renderRanking(data, onOpenList);
  renderWhy(data);
  renderBench(data);
  renderCost(data);

  const canvas = document.getElementById("scene-canvas");
  if (canvas) {
    const hero = document.getElementById("hero");
    try {
      scene = mountScene(canvas, data.topics || [], onOpen, data.sources, {
        onPlanet: (name) => openSourcePanel(data, name, onOpenList),
      });
      onPanelClose = () => scene.release();
    } catch (e) {
      renderFallback2D(canvas, data.topics || []);
    }
    setupExplore(hero, scene);
    setupDiscovery(hero, data, scene, onOpenList);
  }
}

main();
