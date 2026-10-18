"""Comunidad como sensor: el equipo pega el texto de una pieza pública (LinkedIn, IG, TikTok) y el radar la clasifica.

Cascada de costo: estudiante (USD 0) -> si duda, profesor LLM vía decide() -> si no hay LLM, regla por keywords.
No se guarda el texto ni datos personales: se quitan emails, @handles, teléfonos y URLs antes de clasificar.
"""
import re

from django.conf import settings

from decision.decide import Question, decide

from . import student
from .taxonomy import FORMATS, HOOKS, TOPICS, match_topics, normalizar

_PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"), (re.compile(r"(?<!\w)@\w{2,}"), "[usuario]"),
        (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "[telefono]"), (re.compile(r"https?://\S+"), "[link]")]
UMBRAL_ESTUDIANTE = 0.5
# ponytail: el encaje del estudiante no supera la base (usable=False); palabras de trabajo/ejecutivo suben el piso a 0.6
TRABAJO = re.compile(r"\b(informes?|reportes?|excel|presentacion(es)?|reunion(es)?|equipos?|empresas?|negocios?|trabajo|gerentes?|"
                     r"ejecutivos?|ventas|comercial(es)?|clientes|en 5 minutos|correos?)\b")

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
    if r["topic"] != "otro" and TRABAJO.search(normalizar(texto)):
        r["exec_fit"] = max(r["exec_fit"], 0.6)
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


# --- Plataforma: prior transparente sobre la predicción del modelo (ponytail: reglas simples, sin entrenar nada más)
VIDEO_CORTO = ("reel-cara", "caso-paso-a-paso", "herramienta-60s")
FORMATOS_EXTRA = {"humor-pov": "Humor / POV (sketch corto)"}
HOOKS_EXTRA = {"humor-pov": "Humor: situación reconocible"}
_LISTA = re.compile(r"(?m)^\s*(\d+[.)\-:]|[-•*▪✅👉➡️])\s+\S")
_LISTA_N = re.compile(r"\b\d+\s+(prompts?|ideas|herramientas|trucos|formas|pasos|consejos|tips|errores|razones)\b")
_HUMOR = re.compile(r"\b(pov|jajaj\w*|meme|cuando tu jefe|cuando tu|nadie:)\b|😂|🤣")


_OPINION = re.compile(r"\b(no van a|la clave|creo que|opino|mito|error|nadie te|el problema|no es )")


def es_lista(texto: str) -> bool:
    n = normalizar(texto)
    return len(_LISTA.findall(texto)) >= 3 or bool(_LISTA_N.search(n))


def es_humor(texto: str) -> bool:
    return bool(_HUMOR.search(normalizar(texto)) or _HUMOR.search(texto))


def ajustar_plataforma(r: dict, texto: str, plataforma: str) -> None:
    """Combina la predicción del modelo con lo que se espera en cada red; deja en r['prior'] qué regla pesó."""
    fmt, lista, humor = r["format"], es_lista(texto), es_humor(texto)
    nuevo, regla = fmt, ""
    if humor and plataforma in ("Instagram", "TikTok", "YouTube"):
        nuevo, regla = "humor-pov", "tono de humor/POV -> sketch corto"
        r["hook"] = "humor-pov"
    elif plataforma == "Instagram":
        if lista:
            nuevo, regla = "carrusel", "lista en Instagram -> carrusel"
        elif fmt not in VIDEO_CORTO + ("carrusel",):
            nuevo, regla = "reel-cara", "en Instagram el modelo no ve formato visual -> reel"
    elif plataforma == "TikTok":
        if fmt not in VIDEO_CORTO:
            nuevo, regla = "reel-cara", "TikTok es video corto -> reel"
    elif plataforma == "LinkedIn":
        if lista:
            nuevo, regla = "carrusel", "lista en LinkedIn -> carrusel/PDF"
        elif fmt in VIDEO_CORTO and fmt != "caso-paso-a-paso":
            nuevo, regla = "post-texto", "LinkedIn es texto -> post"
    elif plataforma == "YouTube":
        if fmt not in VIDEO_CORTO + ("entrevista-clip", "noticia-explicada", "evento-live"):
            nuevo, regla = "caso-paso-a-paso", "YouTube es video -> tutorial"
    if fmt == "noticia-explicada" and nuevo == fmt and _OPINION.search(normalizar(texto)):
        nuevo, regla = "opinion", "tono de opinión -> opinión/predicción"
    if lista and not humor and r["hook"] != "lista-numerada" and _LISTA_N.search(normalizar(texto)):
        r["hook"] = "lista-numerada"
    r["format"], r["prior"] = nuevo, regla


def _frases(texto: str) -> list:
    partes = re.split(r"(?<=[.!?])\s+|\n+", texto)
    out = []
    for f in partes:
        f = re.sub(r"^\s*(\d+[.)\-:]|[-•*▪✅👉➡️])\s*", "", f).strip()
        if len(f) >= 8 and not re.fullmatch(r"[\[\]\w\s]*(email|usuario|link|telefono)\]?", f):
            out.append(f)
    return out


def _corta(f: str, n: int) -> str:
    return f if len(f) <= n else f[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def tu_version(texto: str, plataforma: str, fmt: str = "") -> dict:
    """Guion hecho SOLO con la pieza pegada. Carrusel = slides (portada, 3-5 puntos, cierre); POV/reel = tomas 0-3, 3-10, 10-20 s. Nada inventado."""
    fr = _frases(texto)
    lista = es_lista(texto)
    gancho = _corta(fr[0], 90) if fr else "(la pieza no trae texto suficiente)"
    cta = "Comenta QUIERO y te mando la guía paso a paso (CTA genérico de 30X)."
    if fmt == "carrusel":
        if len(fr) > 2 and normalizar(fr[-1]).startswith("comenta"):  # el CTA de su propia pieza es el cierre
            cta, fr = _corta(fr[-1], 120), fr[:-1]
        tomas = [{"seg": f"Slide {i}", "texto": _corta(f, 120)} for i, f in enumerate(fr[1:6], 2)]
        return {"gancho": gancho, "formato": "Carrusel: portada, una lámina por punto y cierre", "tomas": tomas, "cta": cta,
                "gancho_label": "Portada", "cta_label": "Cierre (CTA)"}
    if fmt in ("humor-pov", "reel-cara", "herramienta-60s", "caso-paso-a-paso") and plataforma in ("Instagram", "TikTok"):
        segs = ("3-10 s", "10-20 s")
        tomas = [{"seg": sg, "texto": _corta(f, 120)} for sg, f in zip(segs, fr[1:3])]
        return {"gancho": gancho, "formato": "Sketch POV de 3 tomas" if fmt == "humor-pov" else "Reel vertical de 20 s", "tomas": tomas, "cta": cta,
                "gancho_label": "Toma 0-3 s", "cta_label": "CTA"}
    formato = {"Instagram": "Carrusel de láminas, una por punto" if lista else "Reel vertical de 30-45 s",
               "TikTok": "Video vertical de 20-30 s", "LinkedIn": "Carrusel PDF" if lista else "Post de texto",
               "YouTube": "Video de 3-5 min con capítulos"}.get(plataforma, "Post de texto o reel corto")
    segs = ("3-12", "12-25", "25-40")
    tomas = [{"seg": f"{sg} s", "texto": _corta(f, 120)} for sg, f in zip(segs, fr[1:4])]
    return {"gancho": gancho, "formato": formato, "tomas": tomas, "cta": cta, "gancho_label": "Gancho", "cta_label": "CTA"}


def veredicto(r: dict, tema: dict | None) -> dict:
    """Veredicto en lenguaje de acción + el porqué en una frase."""
    fit = r["fit_pct"]
    if tema is None:
        return {"accion": "Descártalo", "porque": "No encaja con ningún tema del radar, así que no es para tu audiencia."}
    if r["no_audiencia"]:
        return {"accion": "Descártalo", "porque": f"Roza {r['topic_name']}, pero le sirve poco a un ejecutivo que aprende IA (encaje {fit}%)."}
    if r["decision"] == "Recomendar":
        return {"accion": "Publícalo esta semana", "porque": f"{r['topic_name']} está en {r['early_label'].lower()} y le sirve a tu audiencia (encaje {fit}%)."}
    if r["exec_fit"] >= 0.6 and tema["stage"] in ("bajando", "estable"):  # buen tema, mal momento
        return {"accion": "Guárdalo para después", "porque": "Guárdalo: le sirve a tu audiencia, pero este tema no está creciendo ahora."}
    if r["decision"] == "Aprender":
        return {"accion": "Guárdalo para después", "porque": f"Tiene potencial (encaje {fit}%), pero no es la prioridad de esta semana."}
    motivo = "el tema está cayendo" if r["cayendo"] else "el encaje con tu audiencia es bajo" if r["exec_fit"] < 0.5 else "hay temas mejores esta semana"
    return {"accion": "Descártalo", "porque": f"Por ahora no vale la pena: {motivo}."}


def decision_pieza(tema: dict | None, fit: float) -> str:
    """Combina el tema con el encaje de la PIEZA: lo que no es para la audiencia se descarta aunque el tema suba."""
    if tema is None or fit < 0.2:
        return "Descartar"
    d = tema["decision"]
    if d == "Recomendar":
        return "Recomendar" if fit >= 0.5 else "Aprender"
    # ponytail: pieza con buen encaje en tema plano (no cayendo) vale al menos como aprendizaje; así "POV con ChatGPT" no se castiga por el tema
    return "Aprender" if fit >= 0.6 and (d == "Aprender" or tema["stage"] != "bajando") else "Descartar"


def analizar(texto: str, plataforma: str = "Otro") -> dict:
    from .views import cargar_radar

    limpio = limpiar(texto)
    r = clasificar(limpio)
    ajustar_plataforma(r, limpio, plataforma)
    radar = cargar_radar()
    r["texto_limpio"] = limpio
    r["claves"] = palabras_clave(limpio, r["topic"])
    tema = next((t for t in radar.get("topics", []) if t["slug"] == r["topic"]), None)
    momentum = tema["momentum"] if tema else 0.0
    p_raw = round(0.5 * momentum + 0.5 * r["exec_fit"], 3)
    crudos = [t["p_raw"] for t in cargar_radar().get("topics", []) if "p_raw" in t]  # mismo min-max semanal del radar
    lo, hi = (min(crudos), max(crudos)) if crudos else (0.0, 1.0)
    p = round(min(1.0, max(0.0, (p_raw - lo) / (hi - lo))), 3) if hi > lo else p_raw
    r["decision"] = decision_pieza(tema, r["exec_fit"])
    r["baja_confianza"] = r["engine"] == "regla" or r["confidence"] < 0.5
    modelo = student.cargar()  # "Seguro" = la probabilidad del tema supera el umbral con el que el modelo acierta >= 90 % (train)
    r["seguro"] = bool(r["engine"] != "regla" and modelo and student.seguro(modelo, "topic", r["confidence"]))
    r["tau_pct"] = round(((modelo or {}).get("eval", {}).get("topic", {}).get("tau") or 0) * 100)
    r["p"] = p
    r["topic_name"] = TOPICS[r["topic"]]["name"] if r["topic"] in TOPICS else "Fuera del radar"
    r["format_name"] = {**FORMATS, **FORMATOS_EXTRA}.get(r["format"], r["format"])
    r["hook_name"] = {**HOOKS, **HOOKS_EXTRA}.get(r["hook"], r["hook"])
    etapa = tema["stage"] if tema else "sin datos"
    r["reason"] = (f"Tema '{r['topic_name']}': {tema['early_label'].lower() if tema else 'fuera del radar'}, impulso {momentum:.0%}; encaje con tu audiencia {r['exec_fit']:.0%}. "
                   f"Formato: {r['format_name']}; gancho: {r['hook_name']}.")
    if tema and tema["why"].get("format_winner") and tema["why"]["format_winner"] != r["format"]:
        r["reason"] += f" En este tema funciona mejor: {FORMATS.get(tema['why']['format_winner'])}."
    r["adapt"], r["adapt_reel"] = (tema["adapt"], tema["adapt_reel"]) if tema else (None, None)
    # Un guion por formato: IG/TikTok -> reel; LinkedIn/YouTube -> el normal; "Otro" -> ambos. Si falta, NO se usa el de otro formato.
    r["modo_guion"] = "reel" if plataforma in ("Instagram", "TikTok") else "normal" if plataforma in ("LinkedIn", "YouTube") else ""
    if r["adapt"] and plataforma in ("LinkedIn", "YouTube"):
        r["adapt"] = {**r["adapt"], "platform": plataforma}
    if r["adapt_reel"] and plataforma in ("Instagram", "TikTok"):
        r["adapt_reel"] = {**r["adapt_reel"], "platform": plataforma}
    if plataforma in ("Instagram", "TikTok"):
        r["adapt"] = None
    elif plataforma in ("LinkedIn", "YouTube"):
        r["adapt_reel"] = None
    r["tu_version"] = tu_version(limpio, plataforma, r["format"])
    r["stage"], r["growth"] = etapa, (tema["growth"] if tema else None)
    r["early_label"] = tema["early_label"] if tema else "Sin datos"
    r["slug_ok"] = tema is not None
    r["cayendo"] = bool(tema and tema["stage"] == "bajando")
    r["no_audiencia"] = tema is not None and r["exec_fit"] < 0.2
    r["similares"] = sorted(tema["top_signals"], key=lambda s: -s.get("velocity", 0))[:3] if tema else []
    bench = radar.get("benchmark_30x") or []
    r["benchmark"] = next((b for b in bench if b["format"] == r["format"]), None) or next((b for b in bench if b["hook"] == r["hook"]), None) or (bench[0] if bench else None)
    r["momento_pct"] = round(min(1.0, (tema["growth"] if tema else 0) / 2) * 100)
    r["fit_pct"], r["conf_pct"] = round(r["exec_fit"] * 100), round(r["confidence"] * 100)
    r["veredicto"] = veredicto(r, tema)
    r["p_pct"] = round(p * 100)
    return r
