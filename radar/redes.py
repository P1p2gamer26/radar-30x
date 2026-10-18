"""Oportunidades por red: un tema que en general se descarta puede despegar en UNA red.
Misma matemática que el radar (peso y share de trend.py), pero dentro de cada fuente: últimos 7 días vs 7 anteriores."""
from datetime import timedelta

from . import trend

REDES = ("instagram", "tiktok", "linkedin", "youtube", "hn", "gnews", "wiki")
MIN_BASE = 20  # piezas mínimas de la red en la semana previa
A = 0.5  # suavizado igual que trend.growth


def _share(signals, topic_of, desde, hasta):
    """({slug: peso}, peso total) de las señales con desde <= fecha < hasta."""
    por, tot = {}, 0.0
    for s in signals:
        if desde <= s["published_at"][:10] < hasta:
            w = trend.peso(s)
            tot += w
            if s["id"] in topic_of:
                por[topic_of[s["id"]]] = por.get(topic_of[s["id"]], 0.0) + w
    return por, tot


def oportunidades(signals, topic_of, fin, min_piezas=5, decisiones=None, nombres=None, top=8) -> list:
    d = lambda n: (fin - timedelta(days=n)).strftime("%Y-%m-%d")  # noqa: E731
    manana = (fin + timedelta(days=1)).strftime("%Y-%m-%d")
    glob_r, glob_t = _share(signals, topic_of, d(6), manana)
    out = []
    for red in REDES:
        sr = [s for s in signals if s["source"] == red]
        rec, tr = _share(sr, topic_of, d(6), manana)
        ant, ta = _share(sr, topic_of, d(13), d(6))
        if sum(1 for s in sr if d(13) <= s["published_at"][:10] < d(6)) < MIN_BASE:
            continue  # sin semana previa en esa red no hay base: el "crecimiento" sería un artefacto de la recolección
        for slug, w in rec.items():
            piezas = [s for s in sr if topic_of.get(s["id"]) == slug and s["published_at"][:10] >= d(6)]
            if len(piezas) < min_piezas:
                continue
            sh_r = 100 * w / tr
            sh_a = 100 * ant.get(slug, 0.0) / ta if ta else 0.0
            g = round((sh_r + A) / (sh_a + A), 2)
            sh_glob = 100 * glob_r.get(slug, 0.0) / glob_t if glob_t else 0.0
            if g >= 1.5 and sh_r >= sh_glob:
                top_s = max((p for p in piezas if p.get("url")), key=trend.peso, default=None)
                out.append({"slug": slug, "tema": (nombres or {}).get(slug, slug), "red": red, "growth": g,
                            "piezas": len(piezas), "decision_global": (decisiones or {}).get(slug, ""),
                            "evidencia_url": top_s["url"] if top_s else ""})
    return sorted(out, key=lambda o: -o["growth"])[:top]


if __name__ == "__main__":
    from datetime import datetime
    fin = datetime(2026, 10, 18)
    sig, topic = [], {}
    def add(i, dia, src, slug):
        sid = f"{src}{i}"
        sig.append({"id": sid, "source": src, "published_at": (fin - timedelta(days=dia)).strftime("%Y-%m-%d") + "T10:00:00Z",
                    "url": "http://x/" + sid, "metrics": {"points": 5}})
        topic[sid] = slug
    n = 0
    for dia in range(14):  # "a" plano y pequeño en hn; "o" constante en tiktok
        n += 1; add(n, dia, "hn", "a")
        for _ in range(3):
            n += 1; add(n, dia, "hn", "f"); n += 1; add(n, dia, "tiktok", "o")
    for dia in range(7):  # "a" despega en tiktok
        for _ in range(4):
            n += 1; add(n, dia, "tiktok", "a")
    for dia in (0, 1):  # "ruido": pocas piezas
        n += 1; add(n, dia, "tiktok", "r")
    r = oportunidades(sig, topic, fin)
    assert [(o["slug"], o["red"]) for o in r] == [("a", "tiktok")], r
    print("redes ok", r)
