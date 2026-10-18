"""Historia real con fechas pasadas (gratis): Hacker News (Algolia), arXiv y Wikipedia pageviews.

Se descarga una vez a data/historia/ (cacheado, .json.gz) y el backtest rodante lee de ahí sin red.
"""
import gzip
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from django.conf import settings

from . import sources
from .taxonomy import TOPICS

CARPETA = "historia"


def _dia(d: str) -> datetime:
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


def _rango(ini: str, fin: str) -> list:
    a, b = _dia(ini), _dia(fin)
    return [(a + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((b - a).days + 1)]


def _hn_dia(dia: str) -> list:
    t0 = int(_dia(dia).timestamp())
    out = []
    for q in sources.HN_QUERIES:
        for p in range(5):
            url = ("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=200"
                   f"&query={urllib.parse.quote(q)}&numericFilters=created_at_i>={t0},created_at_i<{t0 + 86400}&page={p}")
            crudo = sources._seguro("hn", sources.get, url)
            hits = json.loads(crudo).get("hits", []) if crudo else []
            out += hits
            if len(hits) < 200:
                break
    return out


def bajar_hn(ini: str, fin: str) -> list:
    """Señales de HN día por día (ventanas de 1 día: Algolia topa en 1000 hits por consulta)."""
    vistos, out = set(), []
    with ThreadPoolExecutor(4) as ex:
        for hits in ex.map(_hn_dia, _rango(ini, fin)):
            for h in hits:
                if h["objectID"] in vistos or not h.get("title"):
                    continue
                vistos.add(h["objectID"])
                out.append({"id": f"hn:{h['objectID']}", "source": "hn", "title": h["title"], "text": "", "lang": "en",
                            "published_at": sources._iso(datetime.fromtimestamp(h["created_at_i"], timezone.utc)),
                            "author_type": "comunidad",
                            "metrics": {"points": h.get("points") or 0, "comments": h.get("num_comments") or 0, "views": 0}})
    return out


def bajar_arxiv(ini: str, fin: str, paginas: int = 4) -> list:
    """Papers por día de envío (submittedDate); arXiv pide 3 s entre llamadas."""
    out, vistos = [], set()
    for dia in _rango(ini, fin):
        d = dia.replace("-", "")
        q = f"({sources.ARXIV_Q}) AND submittedDate:[{d}0000 TO {d}2359]"
        for p in range(paginas):
            time.sleep(3)
            url = f"https://export.arxiv.org/api/query?search_query={urllib.parse.quote(q)}&max_results=100&start={p * 100}"
            crudo = sources._seguro("arxiv", sources.get, url)
            piezas = (sources._seguro("arxiv", sources.parse_arxiv, crudo) or []) if crudo else []
            for s in piezas:
                if s["id"] not in vistos:
                    vistos.add(s["id"])
                    out.append({k: s[k] for k in ("id", "source", "title", "text", "lang", "published_at", "author_type", "metrics")})
            if len(piezas) < 100:
                break
    return out


def bajar_wiki(ini: str, fin: str) -> dict:
    """{slug: {YYYYMMDD: vistas}} sumando los artículos del tema."""
    a, b = _dia(ini), _dia(fin)
    out = {}
    for slug, t in TOPICS.items():
        tot = {}
        for art in t["wiki"]:
            for d, v in sources.fetch_pageviews(art, a, b).items():
                tot[d] = tot.get(d, 0) + v
        out[slug] = tot
    return out


def guardar(nombre: str, datos) -> None:
    ruta = settings.DATA_DIR / CARPETA
    ruta.mkdir(parents=True, exist_ok=True)
    with gzip.open(ruta / f"{nombre}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))


def cargar(carpeta=None) -> dict:
    """{'signals': [...hn+arxiv...], 'wiki': {slug: {YYYYMMDD: vistas}}, 'meta': {...}} desde el caché."""
    ruta = carpeta or settings.DATA_DIR / CARPETA
    leer = lambda n: json.load(gzip.open(ruta / f"{n}.json.gz", "rt", encoding="utf-8"))  # noqa: E731
    return {"signals": leer("hn") + leer("arxiv"), "wiki": leer("wiki"), "meta": leer("meta")}
