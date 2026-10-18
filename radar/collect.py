"""Orquesta las fuentes y guarda un snapshot versionable en data/snapshots/YYYY-MM-DD.json."""
import json
from datetime import datetime, timezone

from django.conf import settings

from . import sources


def run(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    signals, vistos = [], set()
    antes = sources.apify_uso_mensual()  # costo real de la corrida = uso mensual después - antes
    for fn in (sources.fetch_hn, sources.fetch_gnews, sources.fetch_linkedin, sources.fetch_youtube, sources.fetch_instagram, sources.fetch_tiktok):
        for s in fn(now):
            if s["url"] not in vistos and not (sources.con_handle(s["url"]) and not s.get("channel") in sources.OFICIALES) and not sources.con_email(s["url"]):
                vistos.add(s["url"])
                signals.append(s)
    snap = {"collected_at": sources._iso(now), "signals": signals, "wiki": sources.fetch_wiki(now)}
    despues = sources.apify_uso_mensual()
    if antes is not None and despues is not None:
        snap["meta"] = {"apify_cost_usd": round(max(despues - antes, 0.0), 4), "apify_cost_source": "medido con la API de uso de Apify"}
    carpeta = settings.DATA_DIR / "snapshots"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{now:%Y-%m-%d}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return snap


def latest() -> dict:
    """Último snapshot guardado (o vacío)."""
    archivos = sorted((settings.DATA_DIR / "snapshots").glob("*.json"))
    return json.loads(archivos[-1].read_text(encoding="utf-8")) if archivos else {"signals": [], "wiki": {}}
