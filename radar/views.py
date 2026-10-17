import json

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import render

MAX_TEXTO = 3000
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
    return render(request, "radar/index.html", {"radar": cargar_radar()})


def tema(request, slug):
    radar = cargar_radar()
    topic = next((t for t in radar["topics"] if t["slug"] == slug), None)
    if topic is None:
        raise Http404("Tema no encontrado")
    return render(request, "radar/tema.html", {"radar": radar, "topic": topic})


def analizar(request):
    texto, resultado = "", None
    if request.method == "POST":
        if _excede_limite(request):
            return render(request, "radar/analizar.html", {"radar": cargar_radar(), "texto": "", "resultado": None,
                                                           "error": "Llegaste al límite de 20 análisis por hora. Vuelve en un rato."},
                          status=429)
        texto = request.POST.get("texto", "")[:MAX_TEXTO].strip()
        if texto:
            from .analyze import analizar as _analizar
            resultado = _analizar(texto)
    return render(request, "radar/analizar.html", {"radar": cargar_radar(), "texto": texto, "resultado": resultado})


def como_funciona(request):
    return render(request, "radar/como_funciona.html", {"radar": cargar_radar()})


def api_radar(request):
    return JsonResponse(cargar_radar(), json_dumps_params={"ensure_ascii": False})
