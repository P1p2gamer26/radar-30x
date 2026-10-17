"""Comunidad como sensor: el equipo pega el texto de una pieza pública (LinkedIn, IG, TikTok) y el radar la clasifica.

Cascada de costo: estudiante (USD 0) -> si duda, profesor LLM vía decide() -> si no hay LLM, regla por keywords.
No se guarda el texto ni datos personales: se quitan emails, @handles, teléfonos y URLs antes de clasificar.
"""
import re

from django.conf import settings

from decision.decide import Question, decide

from . import student
from .taxonomy import FORMATS, HOOKS, TOPICS, match_topics

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
    if modelo:
        pred = student.predecir(modelo, student.tokens(texto, "comunidad"))
        if pred["topic"][1] >= UMBRAL_ESTUDIANTE:
            fit_c, fit_p = pred["fit"]
            return {"topic": pred["topic"][0], "format": pred["format"][0], "hook": pred["hook"][0],
                    "exec_fit": round(fit_p if fit_c == "alto" else 1 - fit_p, 2), "engine": "estudiante",
                    "confidence": pred["topic"][1], "cost_usd": 0.0}
    d = decide(texto, PREGUNTAS, referencia="analizar")
    if d.engine == "fallback":  # sin LLM ni grabación: regla por keywords, confianza baja a propósito
        kw = match_topics(texto)
        return {"topic": kw[0] if kw else "otro", "format": "post-texto", "hook": "pregunta" if "?" in texto else "urgencia-novedad",
                "exec_fit": 0.5, "engine": "regla", "confidence": 0.3, "cost_usd": 0.0}
    topic, conf = _top(d.answers["topic"].probs)
    return {"topic": topic, "format": _top(d.answers["format"].probs)[0], "hook": _top(d.answers["hook"].probs)[0],
            "exec_fit": round(d.answers["exec_fit"].p, 2), "engine": f"profesor ({d.engine})", "confidence": conf,
            "cost_usd": round(d.cost_usd, 6)}


def analizar(texto: str) -> dict:
    from .views import cargar_radar

    r = clasificar(limpiar(texto))
    tema = next((t for t in cargar_radar().get("topics", []) if t["slug"] == r["topic"]), None)
    momentum = tema["momentum"] if tema else 0.0
    p = round(0.5 * momentum + 0.5 * r["exec_fit"], 3)
    r["decision"] = "Recomendar" if p >= settings.AUTO_THRESHOLD else "Aprender" if p >= settings.REVIEW_THRESHOLD else "Descartar"
    r["p"] = p
    r["topic_name"] = TOPICS[r["topic"]]["name"] if r["topic"] in TOPICS else "Fuera del radar"
    r["format_name"], r["hook_name"] = FORMATS.get(r["format"], r["format"]), HOOKS.get(r["hook"], r["hook"])
    etapa = tema["stage"] if tema else "sin datos"
    r["reason"] = (f"Tema '{r['topic_name']}' en etapa {etapa} (momentum {momentum:.0%}); encaje ejecutivo {r['exec_fit']:.0%}. "
                   f"Formato: {r['format_name']}; gancho: {r['hook_name']}.")
    if tema and tema["why"].get("format_winner") and tema["why"]["format_winner"] != r["format"]:
        r["reason"] += f" En este tema funciona mejor: {FORMATS.get(tema['why']['format_winner'])}."
    r["adapt"] = tema["adapt"] if tema else None
    return r
