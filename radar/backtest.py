"""Prueba hacia atrás: con datos solo hasta el día 7 de la ventana, ¿los temas marcados 'empezando' crecieron en los 7 días siguientes?"""
from datetime import datetime

from . import trend

CRECE = 1.3     # crece = su parte del día (share of voice) en días 8-14 / días 1-7 >= 1.3
MIN_PIEZAS = 5  # y al menos 5 piezas en los días 1-7 (sin esto, ruido de temas casi vacíos)
MARCADAS = ("temprana", "creciendo")


def correr(signals: list, topic_of: dict, slugs: list, fin: datetime) -> dict:
    ds = trend.dias(fin, 14)
    ant = {d for d in ds[:7]}
    # sin fuga: el radar solo ve señales hasta el día 7 (serie de 7 días, aceleración queda en 0)
    vistas = [s for s in signals if s["published_at"][:10] in ant]
    fin7 = datetime.fromisoformat(ds[6] + "T12:00:00+00:00")
    shares = trend.share_series(vistas, topic_of, fin7, 7)
    vol = {t: sum(1 for s in vistas if topic_of.get(s["id"]) == t) for t in slugs}
    p50, p75 = trend.percentil(list(vol.values()), 0.5), trend.percentil(list(vol.values()), 0.75)
    marcados, etapas = [], {}
    for t in slugs:
        serie = shares.get(t, [0.0] * 7)
        etapas[t] = trend.etapa(trend.growth(serie), trend.robust_z(serie), 0.0, vol[t], p50, p75)
        if etapas[t] in MARCADAS:
            marcados.append(t)
    # verdad: share de los 14 días completos, días 8-14 contra 1-7
    todas = trend.share_series(signals, topic_of, fin, 14)
    verdad = set()
    for t in slugs:
        s = todas.get(t, [0.0] * 14)
        a, b = sum(s[:7]) / 7, sum(s[7:]) / 7
        if vol[t] >= MIN_PIEZAS and b / max(a, 1e-9) >= CRECE:
            verdad.add(t)
    k = len(marcados)
    pop = sorted(slugs, key=lambda t: -vol[t])[:k]

    def pr(elegidos):
        ok = len(set(elegidos) & verdad)
        return {"precision": round(ok / k, 3) if k else None, "recall": round(ok / len(verdad), 3) if verdad else None, "aciertos": ok}
    return {"corte_dia": 7, "umbral_crece": CRECE, "min_piezas": MIN_PIEZAS, "senales_hasta_corte": len(vistas),
            "temas": len(slugs), "crecieron": sorted(verdad), "base_azar": round(len(verdad) / len(slugs), 3),
            "marcados": sorted(marcados), "k": k, "radar": pr(marcados), "popularidad": pr(pop),
            "lead_time": "no medible: la ventana es de 14 días y la verdad se juzga por semanas, no por día"}
