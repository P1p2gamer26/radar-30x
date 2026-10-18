import json

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render

from . import plan, student

MAX_TEXTO = 3000
MAX_PRELLENADO = 500
LIMITE_HORA = 20  # ponytail: contador en LocMem por proceso; en varios workers se multiplica, usar caché compartida si hace falta


def _excede_limite(request) -> bool:
    ip = request.META.get("REMOTE_ADDR", "?")  # ponytail: sin X-Forwarded-For (falsificable); detrás de proxy usar la IP real del proxy
    clave = f"analizar:{ip}"
    cache.add(clave, 0, 3600)
    return cache.incr(clave) > LIMITE_HORA


def cargar_radar() -> dict:
    ruta = settings.DATA_DIR / "radar.json"
    if not ruta.exists():
        return {"topics": [], "sources": [], "totals": {}}
    radar = json.loads(ruta.read_text(encoding="utf-8"))
    modelo = student.cargar()
    if modelo and modelo.get("eval"):  # una sola fuente de verdad: las métricas salen siempre de student.json
        radar["student"] = modelo["eval"]
    return radar


FUENTES = {"hn": "Hacker News", "gnews": "Google News", "wiki": "Wikipedia", "youtube": "YouTube",
           "instagram": "Instagram", "tiktok": "TikTok", "x": "X", "linkedin": "LinkedIn", "reddit": "Reddit", "arxiv": "arXiv"}


def tres_preguntas(topics) -> list:
    """Las 3 preguntas del brief con ejemplos reales; temas sin evidencia (top_signals) se omiten."""
    ok = [t for t in topics if t.get("top_signals") and t["top_signals"][0].get("url")]
    despega = (max((t for t in ok if t["stage"] == "temprana"), key=lambda t: t["growth"], default=None)
               or max((t for t in ok if t["stage"] == "creciendo"), key=lambda t: t["growth"], default=None))
    vivos = [t for t in ok if t["decision"] != "Descartar"] or ok  # el ejemplo de encaje no puede ser un tema que el radar descarta
    sirve = max(vivos, key=lambda t: t["exec_fit"], default=None)
    if not despega or not sirve:
        return []
    w = despega["why"]
    fuentes = ", ".join(FUENTES.get(f, f) for f in w.get("sources_growing", [])) or "varias fuentes"
    cartas = [
        ("¿Qué tema está empezando a despegar?", despega, despega["reason"].split(";")[0] + ".", f"{despega['growth']:.1f}x de crecimiento"),
        ("¿Por qué funciona?", despega, f"Formato: {w['format_label']}. Gancho: {w['hook_label']}. Mejor día: {w['best_day']}.", f"al alza en {fuentes}"),
        ("¿Le sirve a mi audiencia?", sirve, f"De los temas que el radar no descarta, es el que más encaja con ejecutivos LatAm aprendiendo IA. Decisión: {sirve['decision']}.", f"{round(sirve['exec_fit'] * 100)} de 100 de encaje con 30X"),
    ]
    return [{"pregunta": q, "tema": t["name"], "slug": t["slug"], "respuesta": r, "dato": d, "evidencia_url": t["top_signals"][0]["url"]}
            for q, t, r, d in cartas]


def oportunidades_red() -> list:
    ruta = settings.DATA_DIR / "oportunidades_red.json"
    if not ruta.exists():
        return []
    return [{**o, "red_nombre": FUENTES.get(o["red"], o["red"])} for o in json.loads(ruta.read_text(encoding="utf-8"))[:6]]


def index(request):
    radar = cargar_radar()
    redes = oportunidades_red()
    rows = plan.filas(radar)
    return render(request, "radar/index.html", {"radar": radar, "preguntas": tres_preguntas(radar["topics"]), "redes": redes, "n_redes": len(redes),
                                                "semana": radar.get("week", "").split("-")[-1], "ejemplos": _ejemplos(radar)[:2], "plan_chat": plan.texto_chat(radar, rows),
                                                "m": plan.metricas(radar.get("student"))})


def tema(request, slug):
    radar = cargar_radar()
    topic = next((t for t in radar["topics"] if t["slug"] == slug), None)
    if topic is None:
        raise Http404("Tema no encontrado")
    return render(request, "radar/tema.html", {"radar": radar, "topic": topic})


PLATAFORMAS = ("LinkedIn", "Instagram", "TikTok", "YouTube", "Otro")


def _ejemplos(radar) -> list:
    """Un título real por plataforma (de temas distintos) para el 'Prueba con…'."""
    out, usadas = [], set()
    for plat in ("linkedin", "instagram", "tiktok", "youtube"):
        for t in radar.get("topics", []):
            if t["slug"] in usadas:
                continue
            s = next((s for s in t["top_signals"] if s["source"] == plat and 25 <= len(s["title"]) <= 140), None)
            if s:
                out.append({"texto": s["title"], "plataforma": PLATAFORMAS[("linkedin", "instagram", "tiktok", "youtube").index(plat)]})
                usadas.add(t["slug"])
                break
    return out


def analizar(request):
    radar = cargar_radar()
    ctx = {"radar": radar, "texto": "", "resultado": None, "plataformas": PLATAFORMAS, "plataforma": "Otro",
           "ejemplos": _ejemplos(radar)}
    if request.method == "GET":  # enlaces de la home: ?texto=...&red=... solo prellenan el formulario (la plantilla autoescapa)
        ctx["texto"] = request.GET.get("texto", "")[:MAX_PRELLENADO].strip()
        red = request.GET.get("red", "Otro")
        ctx["plataforma"] = red if red in PLATAFORMAS else "Otro"
    if request.method == "POST":
        if _excede_limite(request):
            ctx["error"] = "Llegaste al límite de 20 análisis por hora. Vuelve en un rato."
            return render(request, "radar/analizar.html", ctx, status=429)
        ctx["texto"] = request.POST.get("texto", "")[:MAX_TEXTO].strip()
        plat = request.POST.get("plataforma", "Otro")
        ctx["plataforma"] = plat if plat in PLATAFORMAS else "Otro"
        if ctx["texto"]:
            from .analyze import analizar as _analizar
            ctx["resultado"] = _analizar(ctx["texto"], ctx["plataforma"])
    return render(request, "radar/analizar.html", ctx)


def como_funciona(request):
    radar = cargar_radar()
    f = settings.DATA_DIR / "llm_vs_student.json"
    llm_vs = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None  # opcional: lo genera `llm_vs_student`
    if llm_vs and llm_vs.get("items"):
        from radar.management.commands.llm_vs_student import cascada
        llm_vs["cascada"] = cascada(llm_vs["items"], radar["student"]["topic"]["offline"]["tau"])
        llm_vs["cascada"]["pct"] = f"{llm_vs['cascada']['top1'] * 100:.1f}".replace(".", ",")
    from . import en_vivo as ev
    return render(request, "radar/como_funciona.html", {"radar": radar, "m": plan.metricas(radar.get("student")), "llm_vs": llm_vs, "datos": ev.contexto(radar, llm_vs)})


def api_radar(request):
    return JsonResponse(cargar_radar(), json_dumps_params={"ensure_ascii": False})


def api_semana_json(request):
    radar = cargar_radar()
    return JsonResponse({"week": radar.get("week"), "temas": plan.filas(radar)}, json_dumps_params={"ensure_ascii": False})


def api_semana_csv(request):
    radar = cargar_radar()
    r = HttpResponse(plan.csv_texto(plan.filas(radar)), content_type="text/csv; charset=utf-8")
    r["Content-Disposition"] = f'attachment; filename="plan-semana-{radar.get("week", "")}.csv"'
    return r


def en_vivo(request):
    from . import en_vivo as ev

    radar = cargar_radar()
    f = settings.DATA_DIR / "llm_vs_student.json"
    llm_vs = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    if llm_vs and llm_vs.get("items"):
        from radar.management.commands.llm_vs_student import cascada
        llm_vs["cascada"] = cascada(llm_vs["items"], radar["student"]["topic"]["offline"]["tau"])
    return render(request, "radar/en_vivo.html", {"datos": ev.contexto(radar, llm_vs)})


def api_traza(request):
    from . import en_vivo as ev

    if request.method != "POST":
        return JsonResponse({"error": "Usa POST."}, status=405)
    if _excede_limite(request):
        return JsonResponse({"error": "Llegaste al límite de 20 análisis por hora."}, status=429)
    texto = request.POST.get("texto", "").strip()
    if not texto or len(texto) > ev.MAX_TRAZA:
        return JsonResponse({"error": f"El texto debe tener entre 1 y {ev.MAX_TRAZA} caracteres."}, status=400)
    return JsonResponse(ev.traza(texto), json_dumps_params={"ensure_ascii": False})
