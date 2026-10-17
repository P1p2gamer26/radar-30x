"""Matemática de tendencias: estadística elemental y explicable (el LLM no calcula tendencia).

Usamos *share of voice* diario (peso del tema / peso total del día) en vez de conteos crudos,
porque las fuentes devuelven más piezas recientes y todo parecería "crecer".
"""
import math
from datetime import datetime, timedelta
from statistics import median


def peso(signal: dict) -> float:
    m = signal.get("metrics") or {}
    return 1 + math.log1p(m.get("points", 0) + m.get("comments", 0) + m.get("views", 0) / 100)


def dias(fin: datetime, n: int = 14) -> list:
    return [(fin - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def share_series(signals: list, topic_of: dict, fin: datetime, n: int = 14) -> dict:
    """{slug: [% del peso del día]} para los últimos n días. topic_of = {signal_id: slug}."""
    ds = dias(fin, n)
    idx = {d: i for i, d in enumerate(ds)}
    total = [0.0] * n
    por_tema = {}
    for s in signals:
        i = idx.get(s["published_at"][:10])
        if i is None:
            continue
        w = peso(s)
        total[i] += w
        slug = topic_of.get(s["id"])
        if slug:
            por_tema.setdefault(slug, [0.0] * n)[i] += w
    return {slug: [round(100 * v / t, 3) if t else 0.0 for v, t in zip(serie, total)]
            for slug, serie in por_tema.items()}


def growth(serie: list, a: float = 0.5) -> float:
    """(media últimos 3 + a) / (media de los anteriores + a)."""
    reciente, base = serie[-3:], serie[:-3]
    return round((sum(reciente) / 3 + a) / (sum(base) / max(len(base), 1) + a), 3)


def robust_z(serie: list) -> float:
    """z robusto (mediana y MAD) de la media de los últimos 3 días contra la base."""
    base = serie[:-3]
    med = median(base)
    mad = median(abs(x - med) for x in base)
    return round((sum(serie[-3:]) / 3 - med) / (1.4826 * mad + 0.1 * med + 0.1), 3)


def aceleracion(serie: list) -> float:
    """Crecimiento de hoy menos el crecimiento de hace 3 días (positivo = sigue acelerando)."""
    return round(growth(serie) - growth(serie[:-3]), 3) if len(serie) >= 9 else 0.0


def momentum(z: float, g: float, n_src: int) -> float:
    clip = lambda x, hi: min(max(x, 0.0), hi)  # noqa: E731
    return round(0.5 * clip(z, 4) / 4 + 0.3 * clip(math.log2(max(g, 1e-9)), 1.5) / 1.5 + 0.2 * min(n_src, 3) / 3, 3)


def etapa(g: float, z: float, acc: float, volumen: int, p50: float, p75: float) -> str:
    if g < 0.8:
        return "bajando"
    if (g >= 1.5 or z >= 2) and volumen <= p50 and acc >= 0:
        return "temprana"
    if g >= 1.2:
        return "creciendo"
    if volumen >= p75:
        return "saturada"
    return "estable"


def percentil(valores: list, p: float) -> float:
    v = sorted(valores)
    return v[min(len(v) - 1, int(p * len(v)))] if v else 0


def velocidad(signal: dict, ahora: datetime, mediana_canal: float | None = None) -> float:
    """Engagement por hora; en YouTube, veces sobre la mediana de su canal (outlier >= 3 = funcionó)."""
    horas = max((ahora - datetime.fromisoformat(signal["published_at"].replace("Z", "+00:00"))).total_seconds() / 3600, 1)
    m = signal.get("metrics") or {}
    if signal["source"] == "youtube" or (signal["source"] in ("instagram", "tiktok") and signal.get("channel")):
        # cuentas oficiales: vistas (o likes si el post no tiene vistas) por hora
        vh = (m.get("views") or m.get("points", 0)) / horas
        return round(vh / mediana_canal, 2) if mediana_canal else round(vh, 2)
    return round((m.get("points", 0) + 2 * m.get("comments", 0)) / horas, 2)


if __name__ == "__main__":
    plana = [1.0] * 14
    sube = [1.0] * 11 + [3.0, 4.0, 5.0]
    assert growth(plana) == 1.0 and growth(sube) > 2.5
    assert robust_z(sube) > robust_z(plana)
    assert momentum(robust_z(sube), growth(sube), 2) > momentum(0, 1, 0)
    assert etapa(growth(sube), robust_z(sube), aceleracion(sube), 5, 10, 20) == "temprana"
    assert etapa(0.5, 0, 0, 5, 10, 20) == "bajando"
    print("trend ok")
