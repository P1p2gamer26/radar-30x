"""Página /en-vivo/: el pipeline con cifras reales, una repetición de señales de la semana y la traza de un texto pegado.
Solo stdlib + lo que ya usa la app. Cero datos personales: los títulos pasan por analyze.limpiar."""
import json
from functools import lru_cache

from django.conf import settings

from . import student
from .taxonomy import TOPICS

MAX_TRAZA = 2000
N_REPLAY = 60
ORDEN_FUENTES = ("hn", "gnews", "linkedin", "youtube", "instagram", "tiktok", "x", "reddit", "arxiv")


def n(x) -> str:
    return f"{x:,}".replace(",", ".")


def c(x, d=2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def tau_servidor(modelo) -> float:
    return ((modelo or {}).get("eval", {}).get("topic", {}).get("tau")) or 0.0


def top3(modelo, texto: str, fuente: str) -> list:
    """Top-3 de temas con el mismo método que usa el servidor (student.predecir)."""
    if not modelo:
        return []
    d = student.distribucion(modelo, student.tokens(texto, fuente), "topic", modelo.get("best", {}).get("topic", "nb"), texto)
    return [{"slug": k, "p": round(v, 3)} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:3]]


@lru_cache(maxsize=1)
def _snapshot():
    archivos = sorted((settings.DATA_DIR / "snapshots").glob("*.json"))
    return json.loads(archivos[-1].read_text(encoding="utf-8")).get("signals", []) if archivos else []


@lru_cache(maxsize=1)
def _meta_labels() -> dict:
    f = settings.DATA_DIR / "labels.json"
    return json.loads(f.read_text(encoding="utf-8")).get("meta", {}) if f.exists() else {}


def replay(modelo) -> list:
    from .analyze import limpiar

    if not modelo:
        return []
    por_fuente = {f: sorted((s for s in _snapshot() if s["source"] == f), key=lambda s: s["published_at"], reverse=True) for f in ORDEN_FUENTES}
    elegidas = []
    for i in range(N_REPLAY):  # reparto por turnos entre fuentes para que se vea variedad
        for f in ORDEN_FUENTES:
            if len(elegidas) < N_REPLAY and i < len(por_fuente[f]):
                elegidas.append(por_fuente[f][i])
    tau = tau_servidor(modelo)
    out = []
    for s in elegidas:
        titulo = limpiar(s["title"])[:120]
        p = student.predecir(modelo, student.tokens(s["title"], s["source"]), s["title"])
        conf = p["topic"][1]
        out.append({"fuente": s["source"], "titulo": titulo, "fecha": s["published_at"][:10], "tema": p["topic"][0],
                    "top3": top3(modelo, s["title"], s["source"]), "conf": conf, "seguro": conf >= tau,
                    "formato": p["format"][0], "gancho": p["hook"][0]})
    return out


def etapas(radar, modelo, llm_vs) -> list:
    t, ev = radar.get("totals", {}), radar.get("student", {}).get("topic", {})
    off = ev.get("offline", {})
    fuentes = {s["name"]: s["signals"] for s in radar.get("sources", [])}
    nom = {"hn": "Hacker News", "gnews": "Google News", "linkedin": "LinkedIn vía Google News", "youtube": "YouTube",
           "wiki": "Wikipedia", "instagram": "Instagram (Apify)", "tiktok": "TikTok (Apify)", "x": "X (Apify)", "reddit": "Reddit", "arxiv": "arXiv"}
    lista = "; ".join(f"{nom[k]} {n(v)}" for k, v in fuentes.items() if k in nom)
    meta = _meta_labels()
    prof, rev = t.get("teacher_model", "LLM profesor"), meta.get("reviewer", "LLM revisor")
    tau_off, tau_srv = off.get("tau", 0), tau_servidor(modelo)
    cas = (llm_vs or {}).get("cascada") or {}
    cas_txt = (f"En la prueba de {llm_vs['n']} piezas, la cascada acierta {c(cas['top1'] * 100, 1)} % contra {c(llm_vs['llm_top1'] * 100, 1)} % del LLM solo, "
               f"y solo llama al LLM en {round((1 - cas['resuelve_estudiante']) * 100)} % de los casos.") if cas.get("top1") else ""
    return [
        {"id": "fuentes", "nombre": "Fuentes", "valor": f"{n(t.get('signals', 0))} piezas", "archivo": "radar/sources.py",
         "texto": f"Cada semana se recogen señales públicas: {lista}. Redes por Apify: USD {c(t.get('apify_cost_usd', 0))} por semana. Sin datos personales."},
        {"id": "etiquetado", "nombre": "Etiquetado (2 LLM)", "valor": f"{n(t.get('labeled', 0))} etiquetas", "archivo": "radar/label.py",
         "texto": f"Dos LLM distintos ({prof} y {rev}) etiquetan cada pieza una sola vez: tema, formato, gancho y encaje. Solo vale el consenso. Costo total: USD {c(t.get('teacher_cost_usd', 0))}."},
        {"id": "modelo", "nombre": "Modelo propio", "valor": f"{round(off.get('holdout_accuracy', 0) * 100)} % acierto", "archivo": "radar/student.py",
         "texto": f"Aprende de esas etiquetas. Versión completa (embeddings + regresión logística): {round(off.get('holdout_accuracy', 0) * 100)} % top-1 y {round(off.get('holdout_top3', 0) * 100)} % top-3 en {ev.get('n_holdout', 0)} piezas que nunca vio. "
                  f"En el servidor corre una versión liviana sin embeddings. Tarda ~0,1 ms por pieza y cuesta USD 0."},
        {"id": "seguro", "nombre": "¿Seguro?", "valor": f"τ servidor = {c(tau_srv)}", "archivo": "radar/analyze.py",
         "texto": f"Si la probabilidad del tema es ≥ τ, responde el modelo propio. Si no, la pieza escala a un LLM grande gratis. τ se eligió para acertar ≥ 90 % cuando responde solo "
                  f"(versión completa: {c(tau_off)}; en el servidor: {c(tau_srv)}). {cas_txt}"},
        {"id": "tendencia", "nombre": "Tendencia", "valor": "14 días", "archivo": "radar/trend.py",
         "texto": "Mide el share de voz diario del tema (su peso sobre el total del día) y el crecimiento = media de los últimos 3 días contra la de los anteriores. "
                  "Etapa: bajando si crecimiento < 0,8; temprana si crece ≥ 1,5 (o z ≥ 2), con poco volumen y acelerando; creciendo si ≥ 1,2; saturada si el volumen está en el 25 % más alto; si no, estable."},
        {"id": "decision", "nombre": "Decisión", "valor": f"≥ {c(settings.AUTO_THRESHOLD)} recomendar", "archivo": "radar/build.py",
         "texto": f"p = 0,5 × impulso del tema + 0,5 × encaje con la audiencia, normalizado en la semana. Recomendar si p ≥ {c(settings.AUTO_THRESHOLD)}, Aprender si p ≥ {c(settings.REVIEW_THRESHOLD)}, Descartar si no. "
                  "Un tema que baja siempre se descarta; uno estable o saturado como mucho es Aprender."},
        {"id": "guiones", "nombre": "Guiones", "valor": "4 tipos", "archivo": "radar/build.py",
         "texto": "Para cada tema se arman cuatro guiones: reel corto, video largo, post de LinkedIn y recomendación. Se escriben con datos del tema, sin inventar."},
        {"id": "verificacion", "nombre": "Verificación de cifras", "valor": "cada número", "archivo": "radar/verificar.py",
         "texto": "Antes de mostrar un guion se revisa, sin LLM, que cada cifra que cita aparezca en las piezas reales del tema. Si no aparece, la frase se quita."},
        {"id": "plan", "nombre": "Plan", "valor": "CSV · JSON · MCP", "archivo": "radar/plan.py",
         "texto": "El resultado sale como plan de la semana: tabla en la web, descarga CSV, JSON en /api/semana.json y herramienta MCP (mcp_radar.py) para que otro agente lo use."},
    ]


def contexto(radar, llm_vs) -> dict:
    modelo = student.cargar()
    topics = {t["slug"]: {"name": t["name"], "stage": t["stage"], "growth": t["growth"], "p": t["p"], "decision": t["decision"]} for t in radar.get("topics", [])}
    return {"tau": tau_servidor(modelo), "etapas": etapas(radar, modelo, llm_vs), "temas": topics, "senales": replay(modelo),
            "fuentes": {x["name"]: x["signals"] for x in radar.get("sources", [])},
            "umbrales": {"recomendar": settings.AUTO_THRESHOLD, "aprender": settings.REVIEW_THRESHOLD},
            "nombres": {k: v["name"] for k, v in TOPICS.items()}}


def traza(texto: str) -> dict:
    from .analyze import analizar

    r = analizar(texto, "Otro")
    modelo = student.cargar()
    tau = tau_servidor(modelo)
    conf = r["confidence"]
    rec, apr = settings.AUTO_THRESHOLD, settings.REVIEW_THRESHOLD
    nivel = "Recomendar" if r["p"] >= rec else "Aprender" if r["p"] >= apr else "Descartar"
    umbral = rec if nivel == "Recomendar" else apr
    regla = f"p = {c(r['p'])} {'≥' if nivel != 'Descartar' else '<'} {c(umbral)} → {nivel}"
    if nivel != r["decision"]:
        regla += f"; con el encaje de tu pieza ({c(r['exec_fit'])}) y la etapa «{r['stage']}» queda en {r['decision']}"
    return {"limpio": r["texto_limpio"], "engine": r["engine"], "top3": top3(modelo, r["texto_limpio"], "comunidad"),
            "conf": conf, "tau": round(tau, 4), "escala": conf < tau, "formato": r["format"], "gancho": r["hook"],
            "tema": r["topic"], "tema_nombre": r["topic_name"], "etapa": r["stage"], "growth": r["growth"], "p": r["p"], "fit": r["exec_fit"],
            "decision": r["decision"], "regla": regla}
