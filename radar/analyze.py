"""Comunidad como sensor: el equipo pega el texto de una pieza pública (LinkedIn, IG, TikTok) y el radar la clasifica.

Cascada de costo: estudiante (USD 0) -> si duda, profesor LLM vía decide() -> si no hay LLM, regla por keywords.
No se guarda el texto ni datos personales: se quitan emails, @handles, teléfonos y URLs antes de clasificar.
"""
import re

from django.conf import settings

from decision.decide import Question, decide

from . import student
from .build import decision
from .taxonomy import FORMATS, HOOKS, TOPICS, match_topics, normalizar

_PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"), (re.compile(r"(?<!\w)@\w{2,}"), "[usuario]"),
        (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "[telefono]"), (re.compile(r"https?://\S+"), "[link]")]
UMBRAL_ESTUDIANTE = 0.5

PREGUNTAS = [
    Question("topic", "¿De qué tema de IA trata la pieza? ('otro' si no es de IA)", "choice", tuple(TOPICS) + ("otro",)),
    Question("format", "¿Qué formato de pieza es?", "choice", tuple(FORMATS)),
    Question("hook", "¿Cuál es su gancho principal?", "choice", tuple(HOOKS)),
    Question("exec_fit", "¿Le sirve a un ejecutivo de una empresa en Latinoamérica que aprende a usar IA en su negocio?",
             "score"),
]


def limpiar(texto: str) -> str:
    for patron, reemplazo in _PII:
        texto = patron.sub(reemplazo, texto)
    return texto


def _top(probs: dict) -> tuple:
    clase = max(probs, key=lambda k: probs[k])
    return clase, round(probs[clase], 3)


def clasificar(texto: str) -> dict:
    modelo = student.cargar()
    kw = match_topics(texto)
    pred = student.predecir(modelo, student.tokens(texto, "comunidad"), texto) if modelo else None
    r = None
    # si el modelo dice "otro" pero hay palabras clave del radar, no confiamos en él (cae al profesor o a la regla)
    if pred and pred["topic"][1] >= UMBRAL_ESTUDIANTE and not (pred["topic"][0] == "otro" and kw):
        fit_c, fit_p = pred["fit"]
        r = {"topic": pred["topic"][0], "format": pred["format"][0], "hook": pred["hook"][0],
             "exec_fit": round(fit_p if fit_c == "alto" else 1 - fit_p, 2), "engine": "estudiante",
             "confidence": pred["topic"][1], "cost_usd": 0.0}
    if r is None:
        d = None if settings.DECISION_MODE == "replay" else decide(texto, PREGUNTAS, referencia="analizar")  # replay = producción: cero LLM
        if d is None or d.engine == "fallback":  # sin LLM ni grabación: regla por keywords, confianza baja a propósito
            r = {"topic": kw[0] if kw else "otro", "format": pred["format"][0] if pred else "post-texto",
                 "hook": pred["hook"][0] if pred else ("pregunta" if "?" in texto else "urgencia-novedad"),
                 "exec_fit": 0.5, "engine": "regla", "confidence": 0.3, "cost_usd": 0.0}
        else:
            topic, conf = _top(d.answers["topic"].probs)
            r = {"topic": topic, "format": _top(d.answers["format"].probs)[0], "hook": _top(d.answers["hook"].probs)[0],
                 "exec_fit": round(d.answers["exec_fit"].p, 2), "engine": f"profesor ({d.engine})", "confidence": conf,
                 "cost_usd": round(d.cost_usd, 6)}
    if "paso a paso" in normalizar(texto):
        r["format"] = "caso-paso-a-paso"
    return r


def palabras_clave(texto: str, topic: str) -> list:
    """Palabras del texto que más pesaron para el tema (log-verosimilitud vs. las otras clases); si no hay modelo, keywords del tema."""
    modelo = student.cargar()
    clases = modelo["tasks"]["topic"] if modelo else {}
    if topic in clases:
        otras = [m for c, m in clases.items() if c != topic]
        peso = {}
        for t in set(student.tokens(texto)):
            if "_" in t or t.startswith("src:") or t not in clases[topic]["ll"]:
                continue
            peso[t] = clases[topic]["ll"][t] - max(m["ll"].get(t, m["unk"]) for m in otras)
        top = [t for t, w in sorted(peso.items(), key=lambda kv: -kv[1]) if w > 0][:6]
        if top:
            return top
    norm = normalizar(texto)  # ponytail: keywords de varias palabras se parten en palabras sueltas
    kws = TOPICS.get(topic, {}).get("keywords", [])
    return sorted({w for k in kws if k in norm for w in k.split() if len(w) > 2})[:6]


def analizar(texto: str) -> dict:
    from .views import cargar_radar

    limpio = limpiar(texto)
    r = clasificar(limpio)
    radar = cargar_radar()
    r["texto_limpio"] = limpio
    r["claves"] = palabras_clave(limpio, r["topic"])
    tema = next((t for t in radar.get("topics", []) if t["slug"] == r["topic"]), None)
    momentum = tema["momentum"] if tema else 0.0
    p_raw = round(0.5 * momentum + 0.5 * r["exec_fit"], 3)
    crudos = [t["p_raw"] for t in cargar_radar().get("topics", []) if "p_raw" in t]  # mismo min-max semanal del radar
    lo, hi = (min(crudos), max(crudos)) if crudos else (0.0, 1.0)
    p = round(min(1.0, max(0.0, (p_raw - lo) / (hi - lo))), 3) if hi > lo else p_raw
    r["decision"] = decision(p, tema["stage"] if tema else None, tema.get("exec_fit") if tema else None)
    r["baja_confianza"] = r["engine"] == "regla" or r["confidence"] < 0.5
    r["p"] = p
    r["topic_name"] = TOPICS[r["topic"]]["name"] if r["topic"] in TOPICS else "Fuera del radar"
    r["format_name"], r["hook_name"] = FORMATS.get(r["format"], r["format"]), HOOKS.get(r["hook"], r["hook"])
    etapa = tema["stage"] if tema else "sin datos"
    r["reason"] = (f"Tema '{r['topic_name']}': {tema['early_label'].lower() if tema else 'fuera del radar'}, impulso {momentum:.0%}; encaje con tu audiencia {r['exec_fit']:.0%}. "
                   f"Formato: {r['format_name']}; gancho: {r['hook_name']}.")
    if tema and tema["why"].get("format_winner") and tema["why"]["format_winner"] != r["format"]:
        r["reason"] += f" En este tema funciona mejor: {FORMATS.get(tema['why']['format_winner'])}."
    r["adapt"], r["adapt_reel"] = (tema["adapt"], tema["adapt_reel"]) if tema else (None, None)
    r["stage"], r["growth"] = etapa, (tema["growth"] if tema else None)
    r["early_label"] = tema["early_label"] if tema else "Sin datos"
    r["slug_ok"] = tema is not None
    r["similares"] = sorted(tema["top_signals"], key=lambda s: -s.get("velocity", 0))[:3] if tema else []
    bench = radar.get("benchmark_30x") or []
    r["benchmark"] = next((b for b in bench if b["format"] == r["format"]), None) or next((b for b in bench if b["hook"] == r["hook"]), None) or (bench[0] if bench else None)
    r["momento_pct"] = round(min(1.0, (tema["growth"] if tema else 0) / 2) * 100)
    r["fit_pct"], r["conf_pct"] = round(r["exec_fit"] * 100), round(r["confidence"] * 100)
    return r
