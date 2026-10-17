"""Recolectores de fuentes públicas y gratuitas (sin login, sin datos personales).

Cada fetch_* devuelve una lista de Signals (ver SPEC.md) y nunca lanza: si la red falla
imprime un aviso y devuelve []. Solo stdlib.
"""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # ponytail: expat de py3.13 no resuelve entidades externas; fuentes fijas (Google/YouTube)
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from django.conf import settings

from .taxonomy import TOPICS

UA = "Radar30X/0.1 (https://github.com/P1p2gamer26/radar-30x; radar30x@users.noreply.github.com)"  # Wikimedia exige URL + contacto
PAUSA_LINKEDIN = 1.0  # s entre consultas, para no abusar de Google News
HN_QUERIES = ["AI", "LLM", "GPT", "Claude", "Gemini", "agent", "OpenAI", "Anthropic"]


def get(url: str) -> bytes:
    """GET con User-Agent identificable y timeout. Punto único para mockear en tests."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def _seguro(nombre, fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # ponytail: una fuente caída no tumba la recolección
        print(f"[aviso] {nombre}: {e}")
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ Hacker News


def fetch_hn(now: datetime, days: int = 14) -> list:
    desde = int((now - timedelta(days=days)).timestamp())
    vistos, out = set(), []
    for q, page in ((q, p) for q in HN_QUERIES for p in range(5)):  # ponytail: Algolia da máx 1000 hits por consulta; 5 páginas cubren ~14 días de "AI"
        url = ("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=200"
               f"&query={urllib.parse.quote(q)}&numericFilters=created_at_i>{desde}&page={page}")
        crudo = _seguro("hn", get, url)
        hits = json.loads(crudo).get("hits", []) if crudo else []
        if not hits:
            continue
        for h in hits:
            if h["objectID"] in vistos or not h.get("title"):
                continue
            vistos.add(h["objectID"])
            out.append({
                "id": f"hn:{h['objectID']}", "source": "hn",
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                "title": h["title"], "text": "", "lang": "en",
                "published_at": _iso(datetime.fromtimestamp(h["created_at_i"], timezone.utc)),
                "author_type": "comunidad",
                "metrics": {"points": h.get("points") or 0, "comments": h.get("num_comments") or 0, "views": 0},
                "query": q,
            })
    return out


# ------------------------------------------------------------------ Google News RSS

GNEWS_LOCALES = [("es", "hl=es-419&gl=CO&ceid=CO:es-419"), ("en", "hl=en-US&gl=US&ceid=US:en")]


def fetch_gnews(now: datetime, days: int = 14) -> list:
    out = []
    for slug, t in TOPICS.items():
        q = " OR ".join(f'"{k}"' for k in t["keywords"][:2])
        for lang, loc in GNEWS_LOCALES:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q + f' when:{days}d')}&{loc}"
            crudo = _seguro("gnews", get, url)
            if not crudo:
                continue
            for item in ET.fromstring(crudo).iter("item"):
                titulo = item.findtext("title") or ""
                medio = item.findtext("source") or ""
                if medio and titulo.endswith(f" - {medio}"):
                    titulo = titulo[: -len(medio) - 3]
                try:
                    fecha = parsedate_to_datetime(item.findtext("pubDate"))
                except Exception:
                    continue
                out.append({
                    "id": f"gnews:{item.findtext('guid') or item.findtext('link')}", "source": "gnews",
                    "url": item.findtext("link") or "", "title": titulo, "text": "", "lang": lang,
                    "published_at": _iso(fecha), "author_type": "medio",
                    "metrics": {"points": 0, "comments": 0, "views": 0}, "query": slug,
                })
    return out


# ------------------------------------------------------------------ LinkedIn Pulse (vía Google News)

_SUFIJO_LI = re.compile(r"\s*[-|]\s*LinkedIn\s*$", re.I)


def limpiar_titulo_linkedin(titulo: str) -> str:
    """Quita ' - LinkedIn' y el nombre de autor que sigue a ' - ' o ' | ' (solo contenido, nunca personas)."""
    titulo = _SUFIJO_LI.sub("", titulo)
    return sin_pii(re.split(r"\s+[-|]\s+", titulo)[0])


def fetch_linkedin(now: datetime, days: int = 14) -> list:
    out = []
    for slug, t in TOPICS.items():
        q = "site:linkedin.com/pulse " + " ".join(f'"{k}"' for k in t["keywords"][:2])
        for lang, loc in GNEWS_LOCALES:
            time.sleep(PAUSA_LINKEDIN)
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q + f' when:{days}d')}&{loc}"
            crudo = _seguro("linkedin", get, url)
            if not crudo:
                continue
            for item in ET.fromstring(crudo).iter("item"):
                titulo = limpiar_titulo_linkedin(item.findtext("title") or "")
                try:
                    fecha = parsedate_to_datetime(item.findtext("pubDate"))
                except Exception:
                    continue
                if not titulo:
                    continue
                out.append({
                    "id": f"linkedin:{item.findtext('guid') or item.findtext('link')}", "source": "linkedin",
                    "url": item.findtext("link") or "", "title": titulo, "text": "", "lang": lang,
                    "published_at": _iso(fecha), "author_type": "creador",
                    "metrics": {"points": 0, "comments": 0, "views": 0}, "query": slug,
                })
    return out


# ------------------------------------------------------------------ YouTube RSS

YT = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}


# ponytail: regex simple; quita emails, URLs y @handles de textos libres (descripciones) antes de guardarlos.
_PII = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+|https?://\S+|www\.\S+|(?<!\w)@\w[\w.]*")


def sin_pii(texto: str) -> str:
    return re.sub(r"\s+", " ", _PII.sub("", texto or "")).strip()


def parse_youtube(crudo: bytes, canal: dict) -> list:
    out = []
    for e in ET.fromstring(crudo).findall("a:entry", YT):
        vid = e.findtext("yt:videoId", namespaces=YT)
        grupo = e.find("media:group", YT)
        desc = grupo.findtext("media:description", default="", namespaces=YT) if grupo is not None else ""
        stats = e.find(".//media:statistics", YT)
        rating = e.find(".//media:starRating", YT)
        out.append({
            "id": f"youtube:{vid}", "source": "youtube", "url": f"https://www.youtube.com/watch?v={vid}",
            "title": e.findtext("a:title", default="", namespaces=YT), "text": sin_pii(desc)[:500], "lang": canal.get("lang", "en"),
            "published_at": _iso(datetime.fromisoformat(e.findtext("a:published", namespaces=YT))),
            "author_type": canal.get("author_type", "creador"),
            "metrics": {"points": int(rating.get("count", 0)) if rating is not None else 0, "comments": 0,
                        "views": int(stats.get("views", 0)) if stats is not None else 0},
            "query": canal.get("name", ""), "channel": canal.get("name", ""),
        })
    return out


def fetch_youtube(now: datetime, days: int = 14) -> list:
    canales = json.loads((settings.BASE_DIR / "config" / "channels.json").read_text(encoding="utf-8"))
    desde = now - timedelta(days=days)
    out = []
    for c in canales:
        crudo = _seguro("youtube", get, f"https://www.youtube.com/feeds/videos.xml?channel_id={c['id']}")
        if crudo:
            # ponytail: se guardan todos los videos del feed (15) para la mediana del canal; trend filtra la ventana
            out += [s for s in (_seguro("youtube", parse_youtube, crudo, c) or []) if s["published_at"] >= _iso(desde - timedelta(days=60))]
    return out


# ------------------------------------------------------------------ Wikipedia pageviews


def fetch_pageviews(article: str, start: datetime, end: datetime) -> dict:
    """{YYYYMMDD: vistas} de en.wikipedia para un artículo."""
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
           f"{urllib.parse.quote(article, safe='')}/daily/{start:%Y%m%d}/{end:%Y%m%d}")
    crudo = _seguro("wiki", get, url)
    if not crudo:
        return {}
    return {i["timestamp"][:8]: i["views"] for i in json.loads(crudo).get("items", [])}


def fetch_wiki(now: datetime, days: int = 14) -> dict:
    """{slug: [vistas diarias]} sumando los artículos de cada tema. Termina en D-2 (Wikimedia tarda en publicar)."""
    fin = now - timedelta(days=2)
    dias = [(fin - timedelta(days=days - 1 - i)).strftime("%Y%m%d") for i in range(days)]
    out = {}
    for slug, t in TOPICS.items():
        total = dict.fromkeys(dias, 0)
        for art in t["wiki"]:
            for d, v in fetch_pageviews(art, fin - timedelta(days=days - 1), fin).items():
                if d in total:
                    total[d] += v
        out[slug] = [total[d] for d in dias]
    return out
