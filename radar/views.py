import json

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import render

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
    return json.loads(ruta.read_text(encoding="utf-8"))


def index(request):
    radar = cargar_radar()
    return render(request, "radar/index.html", {"radar": radar, "ejemplos": _ejemplos(radar)[:2]})


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
            ctx["resultado"] = _analizar(ctx["texto"])
    return render(request, "radar/analizar.html", ctx)


def como_funciona(request):
    return render(request, "radar/como_funciona.html", {"radar": cargar_radar()})


def api_radar(request):
    return JsonResponse(cargar_radar(), json_dumps_params={"ensure_ascii": False})
