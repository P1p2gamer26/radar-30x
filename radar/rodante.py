"""Backtest rodante: cortes semanales sobre historia real (data/historia/), sin red.

Definiciones FIJADAS ANTES de ver resultados (18-oct-2026); no se tocan después:
 - cortes semanales t; el radar ve solo señales con fecha <= t (ventana de 14 días, igual que build.py)
 - marcado = etapa temprana/creciendo (la misma regla del producto); k = nº de marcados en ese corte
 - verdad = share de voz medio de los 14 días siguientes / de los 14 previos >= 1.3 (CRECE) y >= 10 piezas en los 14 previos
 - baselines con el mismo k: azar (esperanza exacta), popularidad (volumen 7 d), persistencia (lo que ya creció la semana pasada)
 - variante secundaria, también fijada de antemano: top-5 fijo por momentum
 - pico de un tema = semana con mayor share medio; cuenta solo si es >= 1.3x la mediana de sus semanas y no es la primera ni la última
"""
import random
from datetime import datetime, timedelta

from . import trend
from .backtest import CRECE, MARCADAS

MIN_PREVIAS = 10
K_FIJO = 5
VENTANA_LEAD = 6  # semanas atrás en que se busca la primera marca antes del pico
BOOT = 2000


def _vol(sigs, topic_of, slugs):
    v = dict.fromkeys(slugs, 0)
    for s in sigs:
        t = topic_of.get(s["id"])
        if t in v:
            v[t] += 1
    return v


def _wiki_ventana(wiki: dict, slug: str, t: str) -> list:
    """14 días de vistas que terminan en t-2 (Wikimedia publica con retraso); [] si faltan datos."""
    fin = datetime.fromisoformat(t) - timedelta(days=2)
    serie = [(wiki.get(slug) or {}).get((fin - timedelta(days=13 - i)).strftime("%Y%m%d")) for i in range(14)]
    return [] if None in serie else serie


def cortes(ini: str, fin: str) -> list:
    """Cortes semanales: necesitan 14 días antes (ventana) y 14 después (verdad)."""
    c, primero = datetime.fromisoformat(fin) - timedelta(days=14), datetime.fromisoformat(ini) + timedelta(days=13)
    out = []
    while c >= primero:
        out.append(c.strftime("%Y-%m-%d"))
        c -= timedelta(days=7)
    return out[::-1]


def un_corte(signals, topic_of, slugs, wiki, t: str) -> dict:
    fin_t = datetime.fromisoformat(t + "T12:00:00+00:00")
    ds = trend.dias(fin_t, 14)
    vistas = [s for s in signals if ds[0] <= s["published_at"][:10] <= t]  # sin fuga: nada posterior a t
    shares = trend.share_series(vistas, topic_of, fin_t, 14)
    por_src = {src: trend.share_series([s for s in vistas if s["source"] == src], topic_of, fin_t, 14) for src in ("hn", "arxiv")}
    vol7 = _vol([s for s in vistas if s["published_at"][:10] >= ds[7]], topic_of, slugs)
    p50, p75 = trend.percentil(list(vol7.values()), 0.5), trend.percentil(list(vol7.values()), 0.75)
    etapa, mom, persist = {}, {}, {}
    for sl in slugs:
        serie = shares.get(sl, [0.0] * 14)
        g, z, acc = trend.growth(serie), trend.robust_z(serie), trend.aceleracion(serie)
        crecen = sum(1 for sh in por_src.values() if sum(sh.get(sl, [0])) > 0 and trend.growth(sh[sl]) >= 1.2)
        w = _wiki_ventana(wiki, sl, t)
        crecen += 1 if w and sum(w) > 14 and trend.growth(w, a=1) >= 1.1 else 0
        etapa[sl], mom[sl] = trend.etapa(g, z, acc, vol7[sl], p50, p75), trend.momentum(z, g, crecen)
        persist[sl] = (sum(serie[7:]) / 7 + 0.5) / (sum(serie[:7]) / 7 + 0.5)
    # verdad: 28 días que terminan en t+14
    fin_v = fin_t + timedelta(days=14)
    dv = trend.dias(fin_v, 28)
    todas = [s for s in signals if dv[0] <= s["published_at"][:10] <= dv[-1]]
    sh = trend.share_series(todas, topic_of, fin_v, 28)
    vol_prev = _vol([s for s in todas if s["published_at"][:10] <= t], topic_of, slugs)
    verdad = sorted(sl for sl in slugs if vol_prev[sl] >= MIN_PREVIAS and
                    (sum(sh.get(sl, [0.0] * 28)[14:]) / 14) / max(sum(sh.get(sl, [0.0] * 28)[:14]) / 14, 1e-9) >= CRECE)
    marcados = sorted(sl for sl in slugs if etapa[sl] in MARCADAS)
    orden = lambda clave: sorted(slugs, key=lambda x: (-clave[x], x))  # noqa: E731
    k = len(marcados)
    return {"corte": t, "senales": len(vistas), "verdad": verdad, "k": k, "marcados": marcados,
            "metodos": {"radar": marcados, "popularidad": orden(vol7)[:k], "persistencia": orden(persist)[:k],
                        "radar_top5": orden(mom)[:K_FIJO], "popularidad_top5": orden(vol7)[:K_FIJO], "persistencia_top5": orden(persist)[:K_FIJO]},
            "semana": {sl: round(sum(shares.get(sl, [0.0] * 14)[7:]) / 7, 3) for sl in slugs}}


def _pooled(filas: list, metodo: str):
    k = sum(len(f["metodos"][metodo]) for f in filas)
    ok = sum(len(set(f["metodos"][metodo]) & set(f["verdad"])) for f in filas)
    v = sum(len(f["verdad"]) for f in filas)
    return (ok / k if k else None), (ok / v if v else None), ok, k


def _azar(filas: list, n: int, top5: bool = False):
    """Esperanza exacta del azar con el mismo k por corte: precisión = |V|/n."""
    ks = [K_FIJO if top5 else f["k"] for f in filas]
    ok = sum(k * len(f["verdad"]) / n for k, f in zip(ks, filas))
    k, v = sum(ks), sum(len(f["verdad"]) for f in filas)
    return (ok / k if k else None), (ok / v if v else None), ok, k


def _ic(vals: list):
    vals = sorted(x for x in vals if x is not None)
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)] if vals else None


def _lead(filas: list, slugs: list, marca) -> dict:
    """Por tema con pico claro: semanas entre su primera marca (dentro de VENTANA_LEAD) y el pico; None = nunca marcado."""
    res = {}
    for sl in slugs:
        sem = [f["semana"][sl] for f in filas]
        if len(sem) < 3:
            continue
        p = max(range(len(sem)), key=lambda i: (sem[i], -i))
        med = sorted(sem)[len(sem) // 2]
        if p in (0, len(sem) - 1) or sem[p] < CRECE * max(med, 1e-9):
            continue
        m = [i for i in range(max(0, p - VENTANA_LEAD), p + 1) if marca(i, sl)]
        res[sl] = p - m[0] if m else None
    return res


def _resumen_lead(res: dict) -> dict:
    det = [v for v in res.values() if v is not None]
    return {"picos": len(res), "detectados": len(det), "anticipados_1_o_mas": sum(1 for v in det if v >= 1),
            "mediana_semanas": sorted(det)[len(det) // 2] if det else None}


def rodante(signals, topic_of, slugs, wiki, ini: str, fin: str, semilla: int = 30) -> dict:
    rng = random.Random(semilla)
    filas = [un_corte(signals, topic_of, slugs, wiki, t) for t in cortes(ini, fin)]
    n = len(slugs)
    out = {"protocolo": "rodante", "umbral_crece": CRECE, "min_piezas_previas": MIN_PREVIAS, "k_fijo": K_FIJO,
           "ventana_historia": [ini, fin], "n_cortes": len(filas), "temas": n, "cortes": [f["corte"] for f in filas],
           "senales": len(signals),
           "base_azar": round(sum(len(f["verdad"]) for f in filas) / (n * len(filas)), 3) if filas else None,
           "por_corte": [{"corte": f["corte"], "k": f["k"], "crecieron": len(f["verdad"]),
                          "aciertos_radar": len(set(f["marcados"]) & set(f["verdad"]))} for f in filas],
           "resultados": {}}
    idx = range(len(filas))
    boots = [[filas[rng.choice(idx)] for _ in idx] for _ in range(BOOT)] if filas else []
    r3 = lambda x: round(x, 3) if x is not None else None  # noqa: E731
    for variante, suf in (("regla_del_producto", ""), ("top5_fijo", "_top5")):
        res = {}
        for m in ("radar", "popularidad", "persistencia"):
            p, r, ok, k = _pooled(filas, m + suf)
            res[m] = {"precision": r3(p), "recall": r3(r), "aciertos": ok, "marcados": k,
                      "ic95_precision": _ic([_pooled(b, m + suf)[0] for b in boots])}
            if m != "radar":
                res[m]["radar_menos_este"] = {"media": r3((res["radar"]["precision"] or 0) - (p or 0)),
                                              "ic95": _ic([(_pooled(b, "radar" + suf)[0] or 0) - (_pooled(b, m + suf)[0] or 0) for b in boots])}
        p, r, ok, k = _azar(filas, n, bool(suf))
        res["azar"] = {"precision": r3(p), "recall": r3(r), "aciertos": round(ok, 1), "marcados": k,
                       "radar_menos_este": {"media": r3((res["radar"]["precision"] or 0) - (p or 0)),
                                            "ic95": _ic([(_pooled(b, "radar" + suf)[0] or 0) - (_azar(b, n, bool(suf))[0] or 0) for b in boots])}}
        out["resultados"][variante] = res
    leads = {m: _lead(filas, slugs, lambda i, sl, m=m: sl in filas[i]["metodos"][m]) for m in ("radar", "popularidad", "persistencia")}
    out["lead_time"] = {m: _resumen_lead(v) for m, v in leads.items()}
    out["lead_time"]["radar"]["por_tema"] = leads["radar"]
    sims = []
    for _ in range(500):  # azar: mismo k por corte, temas al azar
        elegidos = [set(rng.sample(slugs, f["k"])) for f in filas]
        sims.append(_resumen_lead(_lead(filas, slugs, lambda i, sl: sl in elegidos[i])))
    out["lead_time"]["azar"] = {"picos": sims[0]["picos"] if sims else 0,
                                "detectados_media": round(sum(s["detectados"] for s in sims) / len(sims), 1) if sims else None}
    vals = [v for v in leads["radar"].values() if v is not None]
    meds = [sorted(b)[len(b) // 2] for b in ([rng.choice(vals) for _ in vals] for _ in range(BOOT))] if vals else []
    out["lead_time"]["radar"]["ic95_mediana_semanas"] = _ic(meds)
    return out
