// Nova: mascota flotante con comentarios sacados de los datos (sin LLM, sin cifras inventadas). textContent siempre.
const KEY = "estrellita-mute";
let muted = false;
try { muted = sessionStorage.getItem(KEY) === "1"; } catch (e) { /* sin storage */ }

const root = document.createElement("aside");
root.className = "estrellita";
root.setAttribute("aria-label", "Nova, la mascota de EstelarIA");
const img = document.createElement("img");
img.className = "estrellita-img";
img.alt = "";
const bubble = document.createElement("div");
bubble.className = "estrellita-bubble";
bubble.hidden = true;
bubble.setAttribute("aria-live", "polite");
const who = document.createElement("b");
who.className = "estrellita-who"; who.textContent = "Nova";
const txt = document.createElement("span");
const x = document.createElement("button");
x.type = "button"; x.className = "estrellita-x"; x.textContent = "×"; x.setAttribute("aria-label", "Cerrar comentario");
const mute = document.createElement("button");
mute.type = "button"; mute.className = "estrellita-mute"; mute.textContent = "🔇"; mute.title = "Silenciar en esta sesión"; mute.setAttribute("aria-label", "Silenciar a Nova en esta sesión");
bubble.append(who, txt, x, mute);
root.append(img, bubble);

let timer = 0;
function say(text) {
  if (muted || !text) return;
  txt.textContent = String(text).slice(0, 140);
  bubble.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => { bubble.hidden = true; }, 12000);
}
x.onclick = () => { bubble.hidden = true; };
mute.onclick = () => {
  muted = true; bubble.hidden = true;
  try { sessionStorage.setItem(KEY, "1"); } catch (e) { /* ok */ }
};

const num = (v) => (Math.round(v * 10) / 10).toString().replace(".", ",");
const ETAPA = { temprana: "está en etapa temprana", emergente: "está emergiendo", pico: "está en su pico", saturada: "ya está saturada" };

function ideaDe(t) {
  const w = t.why || {};
  const dia = w.best_day ? ` el ${w.best_day}` : "";
  return `Esta semana ${t.name} despega ${num(t.growth)}x: ${w.format_label ? w.format_label.toLowerCase() : "un reel"}${dia} 😉`;
}

window.estrellita = {
  say,
  // home: primer comentario a los 4 s y hasta 3 consejos si el usuario sigue ahí
  home(data) {
    const ts = (data.topics || []).filter((t) => t.growth > 0);
    if (!ts.length) return;
    const rec = ts.filter((t) => t.decision === "Recomendar");
    const top = (rec.length ? rec : ts).slice().sort((a, b) => b.growth - a.growth);
    const tips = [ideaDe(top[0])];
    if (top[1]) tips.push(`${top[1].name} también sube (${num(top[1].growth)}x). Toca su estrella y mira el guion.`);
    if (data.totals && data.totals.signals) tips.push(`Leí ${data.totals.signals} señales públicas esta semana. ¿Pruebas Analizar con tu idea?`);
    let i = 0;
    const next = () => { if (i < tips.length && !document.hidden) say(tips[i++]); if (i < tips.length) setTimeout(next, 45000); };
    setTimeout(next, 4000);
  },
  // tema seleccionado: se llama tras abrir el panel
  topic(t) {
    const w = t.why || {};
    const partes = [`${t.name} ${ETAPA[t.stage] || "tiene su propio ritmo"}`];
    if (t.decision) partes.push(`decisión: ${t.decision}`);
    if (w.format_label) partes.push(`gana ${w.format_label.toLowerCase()}`);
    if (w.best_day) partes.push(`mejor día: ${w.best_day}`);
    setTimeout(() => say(partes.join(" · ") + "."), 2800);
  },
  planet(label, signals, top) {
    setTimeout(() => say(`${label} trae ${signals} piezas esta semana${top ? `; su tema fuerte es ${top}` : ""}.`), 1200);
  },
};

document.body.appendChild(root);
img.src = document.querySelector("link[rel=icon]").href.replace("favicon.svg", "mascota.svg");

// /analizar: comentario sobre el veredicto ya renderizado
const v = document.querySelector("[data-estrellita-accion]");
if (v) {
  const d = v.dataset;
  setTimeout(() => say(`Veredicto: ${d.estrellitaAccion}${d.estrellitaTema ? ` para ${d.estrellitaTema}` : ""}. ${d.estrellitaSeguro === "1" ? "Estoy segura del tema." : "Revísalo antes de producir."}`), 3500);
}
