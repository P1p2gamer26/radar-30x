"""Recolectores de fuentes públicas y gratuitas (sin login, sin datos personales).

Cada fetch_* devuelve una lista de Signals (ver SPEC.md) y nunca lanza: si la red falla
imprime un aviso y devuelve []. Solo stdlib.
"""
import json
import os
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


_HANDLE_URL = re.compile(r"/@(?!_/)[\w.-]+")  # medium.com/@usuario, tiktok.com/@usuario: handles de particulares


def con_handle(url: str) -> bool:
    return bool(_HANDLE_URL.search(url or ""))


_EMAIL_URL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def con_email(url: str) -> bool:
    """URLs con forma de email (message-id de listas de correo): se descartan, pueden identificar a una persona."""
    return bool(_EMAIL_URL.search(url or ""))


def sin_pii(texto: str) -> str:
    return re.sub(r"\s+", " ", _PII.sub("", texto or "")).strip()


def es_propia(s: dict) -> bool:
    """Señal de una cuenta oficial 30X/Bilbao (la única cuyo texto saneado se conserva)."""
    return bool(s.get("channel")) and not s["channel"].startswith("canal-")


def _alias(canal: dict) -> str:
    """Solo los canales propios de 30X guardan su nombre; los demás, un alias estable (privacidad)."""
    return canal.get("name", "") if canal.get("own") else "canal-" + canal.get("id", "")[-6:]


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
            "title": e.findtext("a:title", default="", namespaces=YT), "text": sin_pii(desc)[:500] if canal.get("own") else "", "lang": canal.get("lang", "en"),
            "published_at": _iso(datetime.fromisoformat(e.findtext("a:published", namespaces=YT))),
            "author_type": canal.get("author_type", "creador"),
            "metrics": {"points": int(rating.get("count", 0)) if rating is not None else 0, "comments": 0,
                        "views": int(stats.get("views", 0)) if stats is not None else 0},
            "query": _alias(canal), "channel": _alias(canal),
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


# ------------------------------------------------------------------ Instagram y TikTok (vía Apify, contenido público)

OFICIALES = {"crece30x": "empresa", "andresbilbao": "creador"}  # únicas cuentas cuyo nombre se guarda (en "channel")
APIFY = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}&timeout=240"
IG_HASHTAGS = ["inteligenciaartificial", "ia", "chatgpt", "agentesia", "iaparaempresas"]
TT_HASHTAGS = ["inteligenciaartificial", "ia", "chatgpt"]


def _apify(actor: str, entrada: dict) -> list:
    """POST síncrono a Apify; sin APIFY_TOKEN devuelve [] (demo y CI sin red). El token nunca se imprime."""
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        return []
    req = urllib.request.Request(APIFY.format(actor, token), data=json.dumps(entrada).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=260) as resp:
        return json.loads(resp.read())


def apify_uso_mensual() -> float | None:
    """USD acumulados en el mes según Apify (GET /v2/users/me/usage/monthly); None sin token o si falla. El token va en cabecera."""
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        return None

    def pedir():
        req = urllib.request.Request("https://api.apify.com/v2/users/me/usage/monthly",
                                     headers={"Authorization": f"Bearer {token}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read())["data"]
        return float(d.get("totalUsageCreditsUsdAfterVolumeDiscount", d.get("totalUsageCreditsUsd")))
    return _seguro("apify-costo", pedir)


def _lang(texto: str) -> str:
    return "es" if re.search(r"[áéíóúñ¿¡]|\b(el|la|los|que|para|con|una|de)\b", texto.lower()) else "en"


def _senal(source, ident, url, caption, publicado, metricas, dueno, formato, query):
    """Item crudo -> Signal. Solo las cuentas oficiales conservan nombre ('channel'); el resto queda anónimo."""
    texto = sin_pii(caption)
    linea = sin_pii((caption or "").strip().split("\n")[0])
    s = {"id": f"{source}:{ident}", "source": source, "url": url, "title": linea[:160] or texto[:160], "text": texto[:500] if dueno in OFICIALES else "",  # terceros: solo título y métricas
         "lang": _lang(texto), "published_at": publicado,
         "author_type": OFICIALES.get(dueno, "creador"), "metrics": metricas, "format": formato, "query": query}
    if dueno in OFICIALES:
        s["channel"] = dueno
    return s


def parse_instagram(items: list, query: str) -> list:
    out = []
    for i in items:
        if not i.get("shortCode") or not i.get("timestamp"):
            continue
        tipo = i.get("type")
        formato = "reel" if i.get("productType") == "clips" else "carrusel" if tipo == "Sidecar" else "video corto" if tipo == "Video" else "imagen"
        out.append(_senal("instagram", i["shortCode"], f"https://www.instagram.com/p/{i['shortCode']}/", i.get("caption"),
                          _iso(datetime.fromisoformat(i["timestamp"].replace("Z", "+00:00"))),
                          {"points": max(i.get("likesCount") or 0, 0), "comments": i.get("commentsCount") or 0,
                           "views": i.get("videoViewCount") or i.get("videoPlayCount") or 0},
                          (i.get("ownerUsername") or "").lower(), formato, query))
    return out


def parse_tiktok(items: list, query: str) -> list:
    out = []
    for i in items:
        if not i.get("id") or not i.get("createTimeISO"):
            continue
        dueno = ((i.get("authorMeta") or {}).get("name") or "").lower()
        url = i.get("webVideoUrl") if dueno in OFICIALES else f"https://www.tiktok.com/@_/video/{i['id']}"  # sin handle de terceros
        out.append(_senal("tiktok", i["id"], url, i.get("text"),
                          _iso(datetime.fromisoformat(i["createTimeISO"].replace("Z", "+00:00"))),
                          {"points": i.get("diggCount") or 0, "comments": i.get("commentCount") or 0, "views": i.get("playCount") or 0},
                          dueno, "video corto", query))
    return out


def fetch_instagram(now: datetime, days: int = 14) -> list:
    if not os.environ.get("APIFY_TOKEN"):
        return []
    runs = [("perfil-30x", [f"https://www.instagram.com/{p}/" for p in OFICIALES], 30)]
    runs += [(h, [f"https://www.instagram.com/explore/tags/{h}/"], 15) for h in IG_HASHTAGS]
    out = []
    for query, urls, n in runs:
        crudo = _seguro("instagram", _apify, "apify~instagram-scraper",
                        {"directUrls": urls, "resultsType": "posts", "resultsLimit": n, "addParentData": False})
        out += _seguro("instagram", parse_instagram, crudo or [], query) or []
    return out


def fetch_tiktok(now: datetime, days: int = 14) -> list:
    if not os.environ.get("APIFY_TOKEN"):
        return []
    runs = [("perfil-30x", {"profiles": list(OFICIALES), "resultsPerPage": 20})]
    runs += [(h, {"hashtags": [h], "resultsPerPage": 15}) for h in TT_HASHTAGS]
    out = []
    for query, entrada in runs:
        crudo = _seguro("tiktok", _apify, "clockworks~tiktok-scraper", {**entrada, "shouldDownloadVideos": False, "shouldDownloadCovers": False})
        out += _seguro("tiktok", parse_tiktok, crudo or [], query) or []
    return out
