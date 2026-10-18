"""Piezas atípicas por tema: las que rinden >= 3x la mediana de su fuente, comparadas con el resto (gancho, formato, día, autor)."""
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

from .taxonomy import FORMATS, HOOKS

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
UMBRAL, MIN_TEMA, MIN_OUT, MIN_LIFT = 3, 5, 3, 1.5


PISO = {"hn": 10, "youtube": 1000, "instagram": 500, "tiktok": 1000}  # mínimo razonable de la mediana (puntos o vistas)


CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _score(s):
    """Engagement comparable DENTRO de su fuente; None = la fuente no trae métricas (gnews, linkedin, wiki)."""
    m = s.get("metrics") or {}
    if s["source"] == "hn":
        return m.get("points") or 0
    if s["source"] in ("youtube", "instagram", "tiktok"):
        return m.get("views") or m.get("points") or 0
    return None


def _lift(out, rest, campo, nombres):
    """Mejor valor con x = parte en atípicas / parte en el resto >= 1,5 y al menos 2 atípicas; si no, None."""
    co, cr = Counter(campo(s) for s in out), Counter(campo(s) for s in rest)
    mejor = None
    for v, n in co.items():
        if v is None or n < 2 or not cr[v]:
            continue
        x = (n / len(out)) / (cr[v] / len(rest))
        if x >= MIN_LIFT and (mejor is None or x > mejor["x"]):
            mejor = {"x": round(x, 1), "n": n, "name": nombres.get(v, v)}
            mejor["valor"] = v
    return mejor


def _num(x):
    return f"{x:.1f}".replace(".", ",")


def analizar(signals, topic_of, fmt_of, hook_of) -> dict:
    """{slug: {...}} para cada tema con piezas puntuables. Pura: sin red ni disco."""
    glob = defaultdict(list)
    for s in signals:
        sc = _score(s)
        if sc is not None:
            glob[s["source"]].append(sc)
    glob = {k: median(v) for k, v in glob.items()}
    por_tema = defaultdict(list)
    for s in signals:
        if s["id"] in topic_of and _score(s) is not None:
            por_tema[topic_of[s["id"]]].append(s)
    res = {}
    for slug, piezas in por_tema.items():
        ratio = {}
        for src in {s["source"] for s in piezas}:
            ps = [s for s in piezas if s["source"] == src]
            base = median(_score(s) for s in ps) if len(ps) >= MIN_TEMA else glob.get(src)
            base = max(base or 0, PISO.get(src, 0))  # ponytail: piso por fuente; sin él una mediana de 1 punto en HN da ratios ×200 engañosos
            if base and base > 0:  # mediana 0 = no hay con qué comparar
                ratio.update({s["id"]: _score(s) / base for s in ps})
        out = sorted((s for s in piezas if ratio.get(s["id"], 0) >= UMBRAL), key=lambda s: -ratio[s["id"]])
        rest = [s for s in piezas if s["id"] in ratio and ratio[s["id"]] < UMBRAL]
        r = {"n_outliers": len(out), "n_piezas": len(ratio), "lift_hook": None, "lift_format": None, "dia": None,
             "autores": None, "ejemplos": [], "frase": None}
        if len(out) < 2:
            r["frase"] = "sin datos suficientes"
        else:
            r["ejemplos"] = [{"title": s["title"][:140], "url": s["url"], "source": s["source"], "ratio": round(ratio[s["id"]], 1)}
                             for s in [s for s in out if not CJK.search(s["title"])][:2]]  # ponytail: ejemplos legibles para la audiencia hispana
        if len(out) >= MIN_OUT and rest:
            lh = _lift(out, rest, lambda s: hook_of.get(s["id"]), HOOKS)
            lf = _lift(out, rest, lambda s: fmt_of.get(s["id"]), FORMATS)
            r["lift_hook"] = lh and {"hook": lh["valor"], "x": lh["x"]}
            r["lift_format"] = lf and {"format": lf["valor"], "x": lf["x"]}
            dia, n = Counter(DIAS[datetime.fromisoformat(s["published_at"].replace("Z", "+00:00")).weekday()] for s in out).most_common(1)[0]
            r["dia"] = dia if n >= 2 else None
            tipo, n = Counter(s.get("author_type") for s in out).most_common(1)[0]
            r["autores"] = {"tipo": tipo, "share": round(n / len(out), 2)} if tipo else None
            partes = []
            if lh:
                partes.append(f"el gancho «{lh['name']}» {_num(lh['x'])}x más que el resto")
            if lf:
                partes.append(f"el formato {lf['name'].lower()} {_num(lf['x'])}x")
            if partes:
                r["frase"] = "Las piezas que más rinden usan " + " y ".join(partes) + "."
        if r["frase"] is None and len(out) >= 2:
            r["frase"] = "Hay piezas que rinden 3x o más, pero sin un patrón claro de gancho o formato."
        res[slug] = r
    return res
