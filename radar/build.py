"""Arma data/radar.json (contrato con el frontend, ver SPEC.md) desde el último snapshot + etiquetas."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median

from django.conf import settings

from . import label, student, trend
from .collect import latest
from .taxonomy import FORMATS, HOOKS, TOPICS, match_topics

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FUENTES = {"hn": "Hacker News", "gnews": "Google News", "linkedin": "LinkedIn (vía Google News)", "youtube": "YouTube", "wiki": "Wikipedia"}
PAID_ALTERNATIVE_USD_YEAR = 3000  # Apify Scale ~USD 2.388/año, Exolyt ~2.700/año (hackaton x30/radar/investigacion.md)


def etiquetar_todo(signals: list) -> dict:
    """Profesor donde existe; estudiante (costo 0) para el resto; keywords si el estudiante duda del tema."""
    labels = label.cargar()["labels"]
    modelo = student.cargar()
    out = {}
    for s in signals:
        if s["id"] in labels:
            out[s["id"]] = labels[s["id"]]
            continue
        kw = match_topics(s["title"] + " " + s.get("text", ""))
        if not modelo:
            if kw:
                out[s["id"]] = {"topic": kw[0], "format": "noticia-explicada", "hook": "urgencia-novedad",
                                "exec_fit": 0.5, "by": "regla"}
            continue
        pred = student.predecir(modelo, student.tokens(s["title"] + " " + s.get("text", ""), s["source"]))
        topic, conf = pred["topic"]
        if conf < 0.4 and kw:
            topic = kw[0]
        fit_c, fit_p = pred["fit"]
        out[s["id"]] = {"topic": topic, "format": pred["format"][0], "hook": pred["hook"][0],
                        "exec_fit": round(fit_p if fit_c == "alto" else 1 - fit_p, 2), "by": "student"}
    return out


def _reparto(contador: Counter) -> dict:
    total = sum(contador.values()) or 1
    return {k: round(v / total, 3) for k, v in contador.most_common()}


def _medianas_canal(signals: list, ahora: datetime) -> dict:
    por_canal = defaultdict(list)
    for s in signals:
        if s["source"] == "youtube":
            por_canal[s.get("channel", "")].append(trend.velocidad(s, ahora))
    return {c: median(v) or 1 for c, v in por_canal.items()}


def cobertura_30x() -> dict:
    """{slug: nº de piezas públicas de 30X que tocan el tema} (data/audiencia/30x.json)."""
    ruta = settings.DATA_DIR / "audiencia" / "30x.json"
    if not ruta.exists():
        return {}
    items = json.loads(ruta.read_text(encoding="utf-8")).get("items", [])
    return Counter(slug for it in items for slug in match_topics(it.get("text", ""))[:1])


def adapt_por_defecto(slug: str, why: dict) -> dict:
    nombre = TOPICS[slug]["name"]
    fmt = why.get("format_winner") or "caso-paso-a-paso"
    return {"title": f"{nombre}: qué significa para tu empresa esta semana",
            "hook": f"{HOOKS.get(why.get('hook_winner') or '', 'Dato concreto')} en los primeros 3 segundos",
            "format": fmt,
            "beats": ["Qué pasó (1 dato, 1 fuente)", "Un caso real en una empresa de LatAm", "Qué hacer el lunes"],
            "cta": "Comenta qué área de tu empresa probaría esto primero", "by": "plantilla"}


def build(snap: dict | None = None) -> dict:
    snap = snap or latest()
    signals = snap["signals"]
    ahora = datetime.fromisoformat(snap["collected_at"].replace("Z", "+00:00"))
    labs = etiquetar_todo(signals)
    topic_of = {sid: lab["topic"] for sid, lab in labs.items() if lab["topic"] in TOPICS}

    shares = trend.share_series(signals, topic_of, ahora)
    por_fuente = {src: trend.share_series([s for s in signals if s["source"] == src], topic_of, ahora)
                  for src in ("hn", "gnews")}
    wiki = snap.get("wiki", {})
    hace7 = (ahora - timedelta(days=7)).strftime("%Y-%m-%d")
    medianas = _medianas_canal(signals, ahora)
    cobertura = cobertura_30x()
    max_cob = max(cobertura.values(), default=0) or 1
    adapts = {}
    ruta_adapt = settings.DATA_DIR / "adapt.json"
    if ruta_adapt.exists():
        adapts = json.loads(ruta_adapt.read_text(encoding="utf-8"))

    por_tema = defaultdict(list)
    for s in signals:
        if s["id"] in topic_of:
            por_tema[topic_of[s["id"]]].append(s)
    volumen = {slug: sum(1 for s in por_tema.get(slug, []) if s["published_at"][:10] >= hace7) for slug in TOPICS}
    p50, p75 = trend.percentil(list(volumen.values()), 0.5), trend.percentil(list(volumen.values()), 0.75)

    topics = []
    for slug, t in TOPICS.items():
        serie = shares.get(slug, [0.0] * 14)
        g, z, acc = trend.growth(serie), trend.robust_z(serie), trend.aceleracion(serie)
        crecen = [src for src, sh in por_fuente.items() if sum(sh.get(slug, [0])) > 0 and trend.growth(sh[slug]) >= 1.2]
        if wiki.get(slug) and sum(wiki[slug]) > 14 and trend.growth(wiki[slug], a=1) >= 1.1:
            crecen.append("wiki")
        mom = trend.momentum(z, g, len(crecen))
        piezas = por_tema.get(slug, [])
        pesos = [trend.peso(s) for s in piezas]
        # encaje = 60 % etiquetas (español/YouTube/LinkedIn pesan el doble que HN en inglés) + 40 % afinidad con 30X
        # ponytail: promedio por grupo (HN en inglés pesa 0.5, el resto 1.0) para que 700 posts de HN no ahoguen a la prensa en español
        grupos = {"hn": [], "otras": []}
        for s, w in zip(piezas, pesos):
            grupos["hn" if s["source"] == "hn" else "otras"].append((labs[s["id"]]["exec_fit"], w))
        pg = {"hn": 0.5, "otras": 1.0}
        medias = {g_: sum(f * w for f, w in v) / sum(w for _, w in v) for g_, v in grupos.items() if v}
        ajuste = sum(pg[g_] * m for g_, m in medias.items()) / sum(pg[g_] for g_ in medias) if medias else 0.0
        afinidad = cobertura.get(slug, 0) / max_cob
        fit = round(0.6 * ajuste + 0.4 * afinidad, 3)
        p_raw = round(0.5 * mom + 0.5 * fit, 3)
        etapa = trend.etapa(g, z, acc, volumen[slug], p50, p75)

        vel = {s["id"]: trend.velocidad(s, ahora, medianas.get(s.get("channel", "")) if s["source"] == "youtube" else None)
               for s in piezas}
        formatos = Counter(labs[s["id"]]["format"] for s in piezas)
        ganchos = Counter(labs[s["id"]]["hook"] for s in piezas)
        con_eng = [s for s in piezas if s["source"] in ("youtube", "hn")]

        def ganador(campo):
            grupos = defaultdict(list)
            for s in con_eng:
                grupos[labs[s["id"]][campo]].append(vel[s["id"]])
            grupos = {k: median(v) for k, v in grupos.items() if len(v) >= 2}
            if grupos:
                return max(grupos, key=lambda k: grupos[k])
            return (formatos if campo == "format" else ganchos).most_common(1)[0][0] if piezas else None

        dias = Counter()
        for s, w in zip(piezas, pesos):
            dias[DIAS_SEMANA[datetime.fromisoformat(s["published_at"].replace("Z", "+00:00")).weekday()]] += w
        why = {"format_winner": ganador("format"), "hook_winner": ganador("hook"),
               "best_day": dias.most_common(1)[0][0] if dias else None,
               "author_mix": _reparto(Counter(s["author_type"] for s in piezas)),
               "formats": _reparto(formatos), "hooks": _reparto(ganchos),
               "sources_growing": crecen, "covered_by_30x": cobertura.get(slug, 0)}

        # top piezas: percentil de velocidad dentro de su fuente (Google News no trae engagement: recencia)
        rank = {}
        for src in ("youtube", "hn", "gnews", "linkedin"):
            del_src = [s for s in piezas if s["source"] == src]
            clave = (lambda s: s["published_at"]) if src in ("gnews", "linkedin") else (lambda s: vel[s["id"]])
            for i, s in enumerate(sorted(del_src, key=clave)):
                rank[s["id"]] = (i + 1) / len(del_src) * (0.8 if src == "gnews" else 1.0)
        recientes = [s for s in piezas if s["published_at"][:10] >= hace7]
        ordenadas = sorted(recientes, key=lambda s: -rank.get(s["id"], 0))
        # ponytail: la mejor pieza de cada plataforma primero (variedad de evidencia), luego el resto por rank
        primeras = list({s["source"]: s for s in reversed(ordenadas)}.values())
        top = (sorted(primeras, key=lambda s: -rank.get(s["id"], 0)) + [s for s in ordenadas if s not in primeras])[:6]

        if g >= 1.05:
            tendencia = f"Crece {g:.1f}x frente a sus 11 días previos"
        elif g < 0.95:
            tendencia = "Cae a la mitad frente a sus 11 días previos" if g <= 0.55 else f"Cae {round((1 - g) * 100)}% frente a sus 11 días previos"
        else:
            tendencia = "Estable frente a sus 11 días previos"
        nombres_src = [FUENTES.get(c, c) for c in crecen]
        razon = (f"{tendencia}; encaje con la audiencia 30X {fit:.0%}; "
                 f"{'al alza en ' + ', '.join(nombres_src) if nombres_src else 'sin fuentes al alza'}; "
                 f"formato ganador: {FORMATS.get(why['format_winner'], 'sin datos')}.")
        topics.append({
            "slug": slug, "name": t["name"], "stage": etapa,
            "growth": g, "z": z, "acceleration": acc, "volume": volumen[slug], "series": serie,
            "wiki_series": wiki.get(slug, []), "momentum": mom, "exec_fit": fit, "p": p_raw, "p_raw": p_raw, "decision": "",
            "reason": razon, "why": why,
            "top_signals": [{"title": s["title"], "url": s["url"], "source": s["source"], "published_at": s["published_at"],
                             "metrics": s["metrics"], "format": labs[s["id"]]["format"], "hook": labs[s["id"]]["hook"],
                             "velocity": vel[s["id"]], "by": labs[s["id"]].get("by")} for s in top],
            "adapt": adapts.get(slug) or adapt_por_defecto(slug, why),
        })

    # p = puntaje relativo de la semana (min-max entre temas); la decisión usa los umbrales sobre p
    lo, hi = min(x["p_raw"] for x in topics), max(x["p_raw"] for x in topics)
    for x in topics:
        x["p"] = round((x["p_raw"] - lo) / (hi - lo), 3) if hi > lo else 0.5
        d = "Recomendar" if x["p"] >= settings.AUTO_THRESHOLD else "Aprender" if x["p"] >= settings.REVIEW_THRESHOLD else "Descartar"
        if x["stage"] == "bajando":
            d = "Descartar"
        elif x["stage"] == "saturada" and d == "Recomendar":
            d = "Aprender"
        x["decision"] = d
    topics.sort(key=lambda x: -x["p"])
    for i, x in enumerate(topics, 1):
        x["rank"] = i

    meta = label.cargar()["meta"]
    modelo = student.cargar() or {}
    n_teacher = sum(1 for lab in labs.values() if lab.get("by") == "teacher")
    clasificadas = len(labs)
    propios = {c["name"] for c in json.loads((settings.BASE_DIR / "config" / "channels.json").read_text(encoding="utf-8"))
               if c.get("own")}
    bench = sorted([s for s in signals if s.get("channel") in propios],
                   key=lambda s: -trend.velocidad(s, ahora, medianas.get(s["channel"])))[:8]
    radar = {
        "generated_at": snap["collected_at"],
        "week": ahora.strftime("%G-W%V"), "window_days": 14,
        "question": "¿Cuáles son los 10 temas de IA que más están creciendo esta semana, por qué y cómo los adapta 30X?",
        "sources": [{"name": k, "label": v, "signals": (len(wiki) if k == "wiki" else sum(1 for s in signals if s["source"] == k))}
                    for k, v in FUENTES.items()],
        "totals": {"signals": len(signals), "classified": clasificadas, "labeled": n_teacher,
                   "teacher_model": meta.get("model", ""), "teacher_cost_usd": meta.get("cost_usd", 0.0),
                   "student_cost_usd": 0.0,
                   "cost_per_signal_usd": round(meta.get("cost_usd", 0.0) / max(clasificadas, 1), 6),
                   "paid_alternative_usd_year": PAID_ALTERNATIVE_USD_YEAR},
        "student": modelo.get("eval", {}),
        "benchmark_30x": [{"title": s["title"], "url": s["url"], "channel": s["channel"], "views": s["metrics"]["views"],
                           "outlier": trend.velocidad(s, ahora, medianas.get(s["channel"])),
                           "format": labs.get(s["id"], {}).get("format"), "hook": labs.get(s["id"], {}).get("hook")}
                          for s in bench],
        "calibration": {"method": "min-max semanal", "thresholds": [settings.AUTO_THRESHOLD, settings.REVIEW_THRESHOLD]},
        "topics": topics,
    }
    (settings.DATA_DIR / "radar.json").write_text(json.dumps(radar, ensure_ascii=False, indent=1), encoding="utf-8")
    return radar

