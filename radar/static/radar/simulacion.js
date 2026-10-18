// EstelarIA — simulación en vivo (canvas 2D, vanilla). Sin innerHTML: solo textContent/createElement.
// iniciarSim(contenedor, D, {onSenal}) -> {inyectar(x), siguiente(), play(on)}
const FUENTES = ["hn", "gnews", "linkedin", "youtube", "wiki", "instagram", "tiktok", "reddit", "arxiv"];
const NOM = { hn: "Hacker News", gnews: "Google News", linkedin: "LinkedIn", youtube: "YouTube", wiki: "Wikipedia", instagram: "Instagram", tiktok: "TikTok", reddit: "Reddit", arxiv: "arXiv" };
const CORTO = { hn: "HN", gnews: "GNews", linkedin: "LinkedIn", youtube: "YouTube", wiki: "Wiki", instagram: "IG", tiktok: "TikTok", reddit: "Reddit", arxiv: "arXiv" };
const COL = { Recomendar: "#FFC07A", Aprender: "#6f94ff", Descartar: "#8a85c4" };
const VIOLETA = "#9b6bff", MAGENTA = "#e07bd6", HUESO = "#f1efff", GRIS = "#a09ec4";
const f2 = (x) => Number(x).toFixed(2).replace(".", ",");
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

export function iniciarSim(cont, D, opc = {}) {
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const orden = { Recomendar: 0, Aprender: 1, Descartar: 2 };
  const slugs = Object.keys(D.temas).sort((a, b) => orden[D.temas[a].decision] - orden[D.temas[b].decision] || D.temas[b].p - D.temas[a].p);
  const cuenta = D.fuentes || {}, maxC = Math.max(1, ...FUENTES.map((f) => cuenta[f] || 0));
  const cnt = { total: 0, seg: 0, esc: 0 }, porTema = {}, flash = {};

  // ---- DOM
  cont.replaceChildren();
  cont.classList.add("sim");
  const barra = el("div", "sim-bar");
  const bPlay = el("button", "btn-vivo", "Pausar"), bStep = el("button", "btn-vivo", "Siguiente señal");
  bPlay.type = bStep.type = "button"; bPlay.hidden = reducido; bStep.hidden = !reducido;
  const mk = (txt) => { const d = el("div", "vivo-cnt"), b = el("b", "", "0"); d.append(b, el("span", "", txt)); barra.append(d); return b; };
  barra.append(bPlay, bStep);
  const cT = mk("piezas procesadas"), cS = mk("respondió el modelo propio"), cE = mk("escaló al LLM grande");
  const actual = el("p", "sim-actual", "Esperando la primera señal…"); actual.setAttribute("aria-live", "off");
  const cv = el("canvas", "sim-canvas"); cv.setAttribute("role", "img");
  cv.setAttribute("aria-label", "Diagrama animado: señales reales salen de sus fuentes, pasan por el modelo propio y llegan a su tema; si el modelo duda, dan un rodeo por el LLM grande.");
  const top = el("p", "sim-top");
  const leyenda = el("p", "sim-ley");
  ["Recomendar", "Aprender", "Descartar"].forEach((k) => { const s = el("span", "", "★ " + k); s.style.color = COL[k]; leyenda.append(s); });
  const l2 = el("span", "", "● rodeo por el LLM"); l2.style.color = MAGENTA; leyenda.append(l2);
  cont.append(barra, actual, cv, top, leyenda);
  const ctx = cv.getContext("2d");

  // ---- layout
  let L = null;
  function layout() {
    const W = Math.max(280, cont.clientWidth), horiz = W >= 720, H = horiz ? 480 : 610;
    const dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const P = {}, rMax = horiz ? 22 : 14, rMin = horiz ? 8 : 6;
    FUENTES.forEach((f, i) => {
      const r = rMin + (rMax - rMin) * Math.sqrt((cuenta[f] || 0) / maxC);
      P["src:" + f] = horiz ? { x: 150, y: 50 + i * ((H - 100) / (FUENTES.length - 1)), r } : { x: 28 + i * ((W - 56) / (FUENTES.length - 1)), y: 62, r };
    });
    P.model = horiz ? { x: W * 0.45, y: H * 0.38, r: 38 } : { x: W / 2, y: 235, r: 32 };
    P.llm = horiz ? { x: W * 0.45, y: H - 80, r: 24 } : { x: W * 0.8, y: 350, r: 20 };
    P.tu = horiz ? { x: 40, y: H / 2, r: 8 } : { x: W / 2, y: 135, r: 8 };
    const n = slugs.length;
    slugs.forEach((s, i) => {
      if (horiz) P["tema:" + s] = { x: W - 270, y: 24 + i * ((H - 48) / (n - 1)), r: 6 };
      else { const fila = i < 10 ? 0 : 1, k = i % 10; P["tema:" + s] = { x: 24 + k * ((W - 48) / 9), y: 450 + fila * 56, r: 6 }; }
    });
    L = { W, H, horiz, P };
  }
  const pos = (k) => L.P[k];

  // ---- partículas
  const parts = [];
  let i = 0, corriendo = !reducido, spawnT = 0.3, pausaHasta = 0, reloj = 0, ultima = null;
  function ruta(x, origen) {
    const seg = x.conf >= D.tau, t = "tema:" + x.tema;
    const e = [{ a: origen, b: "model", d: 1.5 }, { a: "model", b: "model", d: 0.45, decide: true }];
    if (seg || !L.P[t]) e.push({ a: "model", b: L.P[t] ? t : "model", d: 1.4 });
    else e.push({ a: "model", b: "llm", d: 1.1 }, { a: "llm", b: "llm", d: 0.5 }, { a: "llm", b: t, d: 1.2 });
    return e;
  }
  function crear(x, tuya) {
    const origen = tuya ? "tu" : "src:" + x.fuente;
    if (!L.P[origen]) return;
    const p = { x, tuya, seg: x.conf >= D.tau, e: ruta(x, origen), k: 0, t: 0, cola: [], viva: true };
    ultima = p;
    if (reducido) { p.e.forEach((e) => evento(p, e)); p.k = p.e.length - 1; p.t = 1; return; }
    parts.push(p);
  }
  function evento(p, e) {
    if (e.b === "model" && e.a !== "model") cnt.total++;
    if (e.decide) { p.seg ? cnt.seg++ : cnt.esc++; p.modelo = 1; }
    if (e.b.startsWith("tema:")) { const s = e.b.slice(5); porTema[s] = (porTema[s] || 0) + 1; flash[s] = 1; actualizarTop(); }
    cT.textContent = cnt.total; cS.textContent = cnt.seg; cE.textContent = cnt.esc;
  }
  function actualizarTop() {
    const a = slugs.filter((s) => porTema[s]).sort((u, v) => porTema[v] - porTema[u]).slice(0, 4);
    top.textContent = a.length ? "Temas más activos: " + a.map((s) => `${D.nombres[s] || s} (${porTema[s]})`).join(" · ") : "";
  }
  function spawn() {
    if (!D.senales.length) return;
    const s = D.senales[i++ % D.senales.length];
    const t = s.titulo.length > 90 ? s.titulo.slice(0, 90) + "…" : s.titulo;
    actual.textContent = `[${NOM[s.fuente] || s.fuente}] «${t}» → ${D.nombres[s.tema] || s.tema} (${f2(s.conf)} ${s.conf >= D.tau ? "≥" : "<"} τ ${f2(D.tau)})`;
    crear(s, false);
    if (opc.onSenal) opc.onSenal(s);
    if (reducido) dibujar();
  }
  function inyectar(x) {
    pausaHasta = reloj + 5;
    const seg = x.conf >= D.tau;
    actual.textContent = `Tu texto → ${x.tema_nombre || D.nombres[x.tema] || x.tema} (${f2(x.conf)} ${seg ? "≥" : "<"} τ ${f2(D.tau)}): ${seg ? "responde el modelo propio" : "da el rodeo por el LLM grande"}`;
    crear(x, true);
    if (reducido) dibujar();
  }

  // ---- dibujo
  function punto(p) {
    const e = p.e[p.k], a = pos(e.a), b = pos(e.b), u = p.t, s = u * u * (3 - 2 * u);
    let x = a.x + (b.x - a.x) * s, y = a.y + (b.y - a.y) * s;
    if (a !== b) { const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, c = Math.sin(Math.PI * s) * 0.12 * d; x += (-dy / d) * c; y += (dx / d) * c; }
    return { x, y };
  }
  function estrella(x, y, r, col, glow) {
    ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = glow; ctx.fillStyle = col; ctx.beginPath();
    for (let q = 0; q < 8; q++) { const rr = q % 2 ? r * 0.35 : r, an = (q * Math.PI) / 4 - Math.PI / 2; ctx.lineTo(x + rr * Math.cos(an), y + rr * Math.sin(an)); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  function linea(a, b, col, ancho, dash) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = ancho; if (dash) ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); ctx.restore();
  }
  function texto(t, x, y, col, px, align, bold) {
    ctx.fillStyle = col; ctx.font = `${bold ? "600 " : ""}${px}px Geist, Inter, system-ui, sans-serif`; ctx.textAlign = align || "left"; ctx.textBaseline = "middle"; ctx.fillText(t, x, y);
  }
  function nodo(k, col, fill, dash) {
    const n = pos(k); ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = 16; ctx.fillStyle = fill; ctx.strokeStyle = col; ctx.lineWidth = 1.5;
    if (dash) ctx.setLineDash(dash);
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.2832); ctx.fill(); ctx.stroke(); ctx.restore();
  }
  function dibujar() {
    if (!L) return;
    const { W, H, horiz } = L, m = pos("model"), ll = pos("llm");
    ctx.clearRect(0, 0, W, H);
    FUENTES.forEach((f) => linea(pos("src:" + f), m, "rgba(155,107,255,.22)", 1));
    slugs.forEach((s) => linea(m, pos("tema:" + s), COL[D.temas[s].decision] + "30", 1));
    linea(m, ll, "rgba(224,123,214,.45)", 1.2, [5, 5]);
    slugs.forEach((s) => linea(ll, pos("tema:" + s), "rgba(224,123,214,.10)", 1));
    FUENTES.forEach((f, i) => {
      const n = pos("src:" + f), c = cuenta[f];
      nodo("src:" + f, VIOLETA, "#17123a");
      if (horiz) {
        texto(NOM[f], n.x - n.r - 10, n.y - (c ? 7 : 0), HUESO, 13, "right", true);
        if (c) texto(c.toLocaleString("es-CO") + " piezas", n.x - n.r - 10, n.y + 8, GRIS, 11, "right");
      } else texto(CORTO[f], n.x, n.y - n.r - (i % 2 ? 22 : 9), HUESO, 10.5, "center", true);
    });
    const pulso = 1 + 0.04 * Math.sin(reloj * 3);
    ctx.save(); ctx.translate(m.x, m.y); ctx.scale(pulso, pulso); ctx.translate(-m.x, -m.y); nodo("model", "#6f94ff", "#10205a"); ctx.restore();
    texto("Modelo", m.x, m.y - 8, HUESO, horiz ? 14 : 12, "center", true); texto("propio", m.x, m.y + 8, HUESO, horiz ? 14 : 12, "center", true);
    texto("responde si conf ≥ τ " + f2(D.tau), m.x, m.y + m.r + 16, GRIS, 11.5, "center");
    nodo("llm", MAGENTA, "#2a0f3a", [4, 4]);
    texto("LLM grande", ll.x, ll.y + ll.r + 14, HUESO, horiz ? 13 : 11, "center", true); texto("(solo si duda)", ll.x, ll.y + ll.r + 29, GRIS, horiz ? 11.5 : 10, "center");
    slugs.forEach((s) => {
      const t = pos("tema:" + s), col = COL[D.temas[s].decision], fl = flash[s] || 0, c = porTema[s] || 0;
      estrella(t.x, t.y, 6 + fl * 6 + Math.min(c, 8) * 0.35, col, 6 + fl * 22);
      if (horiz) texto(`${(D.nombres[s] || s).slice(0, 40)}${c ? "  ·  " + c : ""}`, t.x + 16, t.y, fl > 0.2 || c ? HUESO : GRIS, 12);
    });
    if (!horiz) texto("Temas", 24, 425, GRIS, 11, "left");
    if (reducido && ultima) {
      const ks = [ultima.e[0].a]; ultima.e.forEach((e) => { if (e.b !== ks[ks.length - 1]) ks.push(e.b); });
      for (let q = 1; q < ks.length; q++) linea(pos(ks[q - 1]), pos(ks[q]), ultima.seg ? "#6f94ff" : MAGENTA, 3);
      const f = pos(ks[ks.length - 1]); estrella(f.x, f.y, 14, HUESO, 20);
    }
    parts.forEach((p) => {
      const q = punto(p), col = p.tuya ? "#ffffff" : p.seg || !p.modelo ? "#8fb0ff" : MAGENTA, r = p.tuya ? 6.5 : 4;
      p.cola.forEach((c, j) => { ctx.globalAlpha = (j / p.cola.length) * 0.4; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(c.x, c.y, r * 0.7, 0, 6.2832); ctx.fill(); });
      ctx.globalAlpha = 1; ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = p.tuya ? 24 : 12; ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(q.x, q.y, r, 0, 6.2832); ctx.fill(); ctx.restore();
      if (p.tuya) texto("tu texto", q.x, q.y - 15, HUESO, 12, "center", true);
    });
  }

  let ultimoT = 0;
  function frame(ts) {
    const dt = Math.min(0.1, (ts - ultimoT) / 1000 || 0); ultimoT = ts;
    if (corriendo) {
      reloj += dt;
      if (reloj >= pausaHasta) { spawnT -= dt; if (spawnT <= 0) { spawn(); spawnT = 0.7 + Math.random() * 0.3; } }
      parts.forEach((p) => {
        p.t += dt / p.e[p.k].d;
        const pt = punto(p); p.cola.push(pt); if (p.cola.length > 9) p.cola.shift();
        if (p.t >= 1) { evento(p, p.e[p.k]); p.k++; p.t = 0; if (p.k >= p.e.length) p.viva = false; }
      });
      for (let q = parts.length - 1; q >= 0; q--) if (!parts[q].viva) parts.splice(q, 1);
      for (const s in flash) flash[s] = Math.max(0, flash[s] - dt * 1.2);
    }
    dibujar();
    requestAnimationFrame(frame);
  }
  function play(on) { corriendo = on; bPlay.textContent = on ? "Pausar" : "Reanudar"; }
  bPlay.addEventListener("click", () => play(!corriendo));
  bStep.addEventListener("click", spawn);
  layout();
  new ResizeObserver(() => { layout(); dibujar(); }).observe(cont);
  if (reducido) { dibujar(); spawn(); } else requestAnimationFrame(frame);
  return { inyectar, siguiente: spawn, play };
}
