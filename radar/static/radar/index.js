// Radar 30X — frontend. Sin innerHTML con datos externos: solo textContent/createElement.
import { mountScene } from "./scene.js";

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
    (t) => t.decision === "Recomendar" || t.stage === "temprana" || t.stage === "creciendo"
  ).length;
}

function renderHero(data) {
  const titleCount = document.getElementById("hero-count");
  const weekEl = document.getElementById("hero-week");
  const n = countEarlyOrRising(data.topics || []);
  titleCount.textContent = String(n);
  const date = data.generated_at ? new Date(data.generated_at) : new Date();
  const dateStr = date.toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
  weekEl.textContent = `Semana ${data.week || ""} · ${dateStr}`;
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
    el("span", { class: "decision-reason", text: topic.reason }),
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
      el("span", { class: "stage-chip", text: topic.stage }),
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
    el("p", { text: `Formato ganador: ${top.why.format_winner}. Gancho ganador: ${top.why.hook_winner}. Mejor día: ${top.why.best_day}.` }),
  ]);
  grid.appendChild(summary);

  renderBarList(grid, "Formatos (agregado)", top.why.formats);
  renderBarList(grid, "Ganchos (agregado)", top.why.hooks);
  renderBarList(grid, "Mezcla de autores", top.why.author_mix);
}

function renderCost(data) {
  const grid = document.getElementById("cost-grid");
  const t = data.totals || {};
  const items = [
    { label: "Costo por señal", value: `USD ${(t.cost_per_signal_usd || 0).toFixed(5)}` },
    { label: "Costo del profesor (LLM)", value: fmtUsd(t.teacher_cost_usd || 0) },
    { label: "Costo del estudiante", value: fmtUsd(t.student_cost_usd || 0) },
    { label: "Señales procesadas", value: String(t.signals || 0) },
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
  highlight.appendChild(document.createTextNode("Esta corrida costó "));
  const strongCost = el("strong", { text: fmtUsd(t.teacher_cost_usd || 0) });
  highlight.appendChild(strongCost);
  highlight.appendChild(document.createTextNode(". El scraping pago cuesta "));
  const strongAlt = el("strong", { text: fmtUsd(t.paid_alternative_usd_year || 0) });
  highlight.appendChild(strongAlt);
  highlight.appendChild(document.createTextNode(" al año."));
  grid.appendChild(highlight);

  const student = data.student || {};
  const accCard = el("div", { class: "cost-card" }, [
    el("span", { class: "cost-value nums", text: `${Math.round((student.accuracy_topic || 0) * 100)}%` }),
    el("span", { class: "cost-label", text: "Precisión del estudiante en tema" }),
  ]);
  grid.appendChild(accCard);
}

// --- Panel lateral ---

let lastFocused = null;

function closePanel() {
  const overlay = document.getElementById("panel-overlay");
  const panel = document.getElementById("panel");
  overlay.classList.remove("open");
  panel.classList.remove("open");
  panel.setAttribute("aria-hidden", "true");
  if (lastFocused) lastFocused.focus();
}

function renderThreshold(p) {
  const track = el("div", { class: "threshold-track" });
  const fill = el("div", { class: "threshold-fill" });
  fill.style.width = `${Math.max(0, Math.min(1, p)) * 100}%`;
  track.appendChild(fill);
  for (const [value, label] of [[0.8, "0.80 Recomendar"], [0.5, "0.50 Aprender"]]) {
    const mark = el("div", { class: "threshold-mark" });
    mark.style.left = `${value * 100}%`;
    mark.appendChild(el("span", { class: "mark-label", text: label }));
    track.appendChild(mark);
  }
  return track;
}

function renderSignal(sig) {
  const item = el("div", { class: "signal-item" });
  const link = el("a", { href: sig.url, target: "_blank", rel: "noopener noreferrer", text: sig.title });
  item.appendChild(link);
  item.appendChild(
    el("div", {
      class: "signal-meta",
      text: `${sig.source} · ${sig.format} · ${sig.hook}`,
    })
  );
  return item;
}

function openPanel(topic, triggerEl) {
  lastFocused = triggerEl || document.activeElement;
  const overlay = document.getElementById("panel-overlay");
  const panel = document.getElementById("panel");
  const title = document.getElementById("panel-title");
  const meta = document.getElementById("panel-meta");
  const body = document.getElementById("panel-body");

  title.textContent = topic.name;
  meta.textContent = "";
  meta.appendChild(el("span", { class: "stage-chip", text: topic.stage }));
  meta.appendChild(el("span", { class: "growth nums", text: fmtGrowth(topic.growth) }));
  meta.appendChild(el("span", { class: `decision-label decision-${topic.decision}`, text: topic.decision }));

  body.textContent = "";

  const resumen = el("div", { class: "panel-section" }, [
    el("h3", { text: "Resumen" }),
    el("p", { text: topic.reason }),
    renderThreshold(topic.p),
    el("p", { class: "nums", text: `p = ${topic.p.toFixed(2)} · momentum ${topic.momentum.toFixed(2)} · exec_fit ${topic.exec_fit.toFixed(2)} · z ${topic.z.toFixed(2)}` }),
  ]);
  body.appendChild(resumen);

  const adapt = topic.adapt || {};
  const beats = el("ol", { class: "beats-list" });
  for (const beat of adapt.beats || []) {
    beats.appendChild(el("li", { text: beat }));
  }
  const guionText = [
    adapt.title,
    `Gancho: ${adapt.hook}`,
    `Formato: ${adapt.format}`,
    ...(adapt.beats || []).map((b, i) => `${i + 1}. ${b}`),
    `CTA: ${adapt.cta}`,
  ].join("\n");

  const copyBtn = el("button", {
    class: "copy-btn",
    text: "Copiar guion",
    onclick: async () => {
      try {
        await navigator.clipboard.writeText(guionText);
        copyBtn.textContent = "Copiado";
        setTimeout(() => (copyBtn.textContent = "Copiar guion"), 1600);
      } catch (e) {
        copyBtn.textContent = "No se pudo copiar";
      }
    },
  });

  const adaptSection = el("div", { class: "panel-section" }, [
    el("h3", { text: "Cómo adaptarlo" }),
    el("p", { text: adapt.title }),
    el("p", { class: "signal-meta", text: `${adapt.hook} · ${adapt.format}` }),
    beats,
    el("p", { text: adapt.cta }),
    copyBtn,
  ]);
  body.appendChild(adaptSection);

  const signalsSection = el("div", { class: "panel-section" }, [el("h3", { text: "Señales principales" })]);
  for (const sig of topic.top_signals || []) {
    signalsSection.appendChild(renderSignal(sig));
  }
  body.appendChild(signalsSection);

  overlay.classList.add("open");
  panel.classList.add("open");
  panel.setAttribute("aria-hidden", "false");
  document.getElementById("panel-close").focus();
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
    const color = t.decision === "Recomendar" ? "#EBFF6F" : t.decision === "Aprender" ? "#FFCC6E" : "#525252";
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
  renderHero(data);

  setupPanelClosers();

  const onOpen = (slug) => {
    const topic = data.topics.find((t) => t.slug === slug);
    if (topic) openPanel(topic, document.activeElement);
  };

  renderRanking(data, onOpen);
  renderWhy(data);
  renderCost(data);

  const canvas = document.getElementById("scene-canvas");
  if (canvas) {
    try {
      mountScene(canvas, data.topics || [], onOpen);
    } catch (e) {
      renderFallback2D(canvas, data.topics || []);
    }
  }
}

main();
