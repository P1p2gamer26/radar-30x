"""Estudiante: Naive Bayes multinomial (stdlib) destilado de las etiquetas del LLM profesor.

Clasifica tema, formato, gancho y encaje ejecutivo (alto/bajo) a costo 0 por señal.
Se guarda en data/student.json y se publica en Hugging Face Hub (deploy/push_model.py).
"""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict

from django.conf import settings

from .taxonomy import match_topics, normalizar

TAREAS = ("topic", "format", "hook", "fit")
K_VECINOS = 30
POT_SIM = 3  # >1 da más peso a los vecinos más parecidos
W_NB = 0.3  # peso de NB en el ensamble
PESO_KW = 0.4  # empuje de keywords de taxonomy al ensamble (solo tema): desempata, no manda
MARGEN_USABLE = 0.03  # el modelo solo es "usable" si supera la base por >= 3 puntos
_PAL = re.compile(r"[a-z0-9][a-z0-9\-\.]{1,}")
STOP = set("the and for with that this from your you are how what why los las del por para con una que como mas sus".split())


def tokens(texto: str, source: str = "") -> list:
    pal = [p.strip(".-") for p in _PAL.findall(normalizar(texto))]
    pal = [p for p in pal if len(p) > 2 and p not in STOP]
    kw = [f"kw_{s}" for s in match_topics(texto)[:3]]  # keywords de taxonomy como rasgos extra
    return pal + [f"{a}_{b}" for a, b in zip(pal, pal[1:])] + kw + ([f"src:{source}"] if source else [])


def objetivo(lab: dict, tarea: str) -> str:
    return ("alto" if lab["exec_fit"] >= 0.6 else "bajo") if tarea == "fit" else lab[tarea]


def es_test(sid: str) -> bool:
    return int(hashlib.md5(sid.encode()).hexdigest(), 16) % 5 == 0  # 20 % fijo para evaluar


def entrenar(ejemplos: list, min_df: int = 2) -> dict:
    """ejemplos = [(tokens, {tarea: clase})]. Devuelve el modelo serializable."""
    df = Counter(t for toks, _ in ejemplos for t in set(toks))
    vocab = {t for t, n in df.items() if n >= min_df}
    modelo = {"vocab_size": len(vocab), "tasks": {}}
    for tarea in TAREAS:
        clases = Counter(y[tarea] for _, y in ejemplos)
        cuenta = defaultdict(Counter)
        for toks, y in ejemplos:
            cuenta[y[tarea]].update(t for t in toks if t in vocab)
        total_docs = sum(clases.values())
        tarea_m = {}
        for c, n in clases.items():
            total = sum(cuenta[c].values()) + len(vocab)  # suavizado de Laplace
            tarea_m[c] = {"prior": round(math.log(n / total_docs), 4), "unk": round(math.log(1 / total), 4),
                          "ll": {t: round(math.log((k + 1) / total), 4) for t, k in cuenta[c].items()}}
        modelo["tasks"][tarea] = tarea_m
    modelo["knn"] = _knn(ejemplos, vocab)
    return modelo


def _knn(ejemplos: list, vocab: set) -> dict:
    """Vecinos por coseno TF-IDF: idf + vector normalizado de cada ejemplo + sus clases."""
    n = len(ejemplos)
    df = Counter(t for toks, _ in ejemplos for t in set(toks) if t in vocab)
    idf = {t: round(math.log((1 + n) / (1 + k)) + 1, 3) for t, k in df.items()}
    docs = []
    for toks, y in ejemplos:
        v = _vector(toks, idf)
        if v:
            docs.append([v, [y[t] for t in TAREAS]])
    return {"idf": idf, "docs": docs}


def _vector(toks: list, idf: dict) -> dict:
    tf = Counter(t for t in toks if t in idf)
    v = {t: (1 + math.log(k)) * idf[t] for t, k in tf.items()}
    norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: round(x / norma, 4) for t, x in v.items()}


def _dist_nb(modelo: dict, toks: list, tarea: str) -> dict:
    clases = modelo["tasks"][tarea]
    conocidos = modelo.setdefault("_conocidos", {})  # cache en memoria, no se guarda
    if tarea not in conocidos:
        conocidos[tarea] = set().union(*(m["ll"] for m in clases.values()))
    vistos = [t for t in toks if t in conocidos[tarea]]
    puntajes = {c: m["prior"] + sum(m["ll"].get(t, m["unk"]) for t in vistos) for c, m in clases.items()}
    mx = max(puntajes.values())
    z = sum(math.exp(v - mx) for v in puntajes.values())
    return {c: math.exp(v - mx) / z for c, v in puntajes.items()}


def _dist_knn(modelo: dict, toks: list, tarea: str) -> dict:
    knn = modelo["knn"]
    if "_idx" not in modelo:  # índice invertido token -> [(doc, peso)], cache en memoria
        idx = defaultdict(list)
        for d, (v, _) in enumerate(knn["docs"]):
            for t, w in v.items():
                idx[t].append((d, w))
        modelo["_idx"] = idx
    sim = Counter()
    for t, w in _vector(toks, knn["idf"]).items():
        for d, w2 in modelo["_idx"].get(t, ()):
            sim[d] += w * w2
    col = TAREAS.index(tarea)
    votos = Counter()
    for d, s in sim.most_common(K_VECINOS):
        votos[knn["docs"][d][1][col]] += s ** POT_SIM
    total = sum(votos.values())
    return {c: v / total for c, v in votos.items()} if total else {c: 1 / len(modelo["tasks"][tarea]) for c in modelo["tasks"][tarea]}


def distribucion(modelo: dict, toks: list, tarea: str, metodo: str, texto: str = "") -> dict:
    """Probabilidad por clase con el método "nb", "knn" o "ens" (promedio NB + kNN + keywords de taxonomy en tema)."""
    if metodo == "nb" or "knn" not in modelo:
        return _dist_nb(modelo, toks, tarea)
    if metodo == "knn":
        return _dist_knn(modelo, toks, tarea)
    a, b = _dist_nb(modelo, toks, tarea), _dist_knn(modelo, toks, tarea)
    d = {c: W_NB * a.get(c, 0) + (1 - W_NB) * b.get(c, 0) for c in set(a) | set(b)}
    if tarea == "topic" and texto:
        for r, slug in enumerate(match_topics(texto)[:3]):  # ponytail: desempate por keywords; el primero pesa más
            if slug in d:
                d[slug] += PESO_KW / (r + 1)
    z = sum(d.values())
    return {c: v / z for c, v in d.items()}


def predecir(modelo: dict, toks: list, texto: str = "") -> dict:
    """{tarea: (clase, probabilidad)} con el mejor método de cada tarea (modelo["best"], por defecto NB)."""
    out = {}
    for tarea in modelo["tasks"]:
        d = distribucion(modelo, toks, tarea, modelo.get("best", {}).get(tarea, "nb"), texto)
        mejor = max(d, key=lambda c: d[c])
        out[tarea] = (mejor, round(d[mejor], 3))
    return out


def ruta():
    return settings.DATA_DIR / "student.json"


def cargar() -> dict | None:
    return json.loads(ruta().read_text(encoding="utf-8")) if ruta().exists() else None


def _acierto(modelo: dict, test: list, tarea: str, met: str) -> int:
    return sum(max(d, key=lambda c: d[c]) == y[tarea] for toks, y, x in test for d in [distribucion(modelo, toks, tarea, met, x)])


def run(signals: list, labels: dict, k: int = 5) -> dict:
    """Separa un 20 % fijo (es_test) como hold-out; elige método por tarea con validación cruzada SOLO sobre el 80 %
    (NB, kNN o ensamble); la cifra honesta es el acierto en el hold-out, que ninguna decisión vio."""
    por_id = {s["id"]: s for s in signals}
    todos = [(sid, tokens(por_id[sid]["title"] + " " + por_id[sid].get("text", ""), por_id[sid]["source"]),
              {t: objetivo(lab, t) for t in TAREAS}, por_id[sid]["title"] + " " + por_id[sid].get("text", ""))
             for sid, lab in labels.items() if sid in por_id]
    holdout = [d for d in todos if es_test(d[0])]
    datos = [d for d in todos if not es_test(d[0])]
    pliegue = lambda sid: int(hashlib.md5(sid.encode()).hexdigest(), 16) % k  # noqa: E731
    metodos = ("nb", "knn", "ens")
    ok, base_ok, n = {m: Counter() for m in metodos}, Counter(), 0
    for f in range(k):
        train = [(t, y) for sid, t, y, _ in datos if pliegue(sid) != f]
        test = [(t, y, x) for sid, t, y, x in datos if pliegue(sid) == f]
        m = entrenar(train)
        n += len(test)
        for tarea in TAREAS:
            mayor = Counter(y[tarea] for _, y in train).most_common(1)[0][0]
            base_ok[tarea] += sum(y[tarea] == mayor for _, y, _ in test)
            for met in metodos:
                ok[met][tarea] += _acierto(m, test, tarea, met)
    acc, best = {}, {}
    for tarea in TAREAS:
        por_met = {met: round(ok[met][tarea] / max(n, 1), 3) for met in metodos}
        best[tarea] = max(metodos, key=lambda met: por_met[met])
        base = round(base_ok[tarea] / max(n, 1), 3)
        acc[tarea] = {"accuracy": por_met[best[tarea]], "baseline": base, "nb": por_met["nb"], "knn": por_met["knn"],
                      "ensemble": por_met["ens"], "method": best[tarea],
                      "usable": por_met[best[tarea]] - base >= MARGEN_USABLE}
        if not acc[tarea]["usable"]:
            best[tarea] = "nb"  # sin mejora real sobre la base, nos quedamos con el modelo simple de siempre
            acc[tarea]["method"] = "nb"
    # hold-out: modelo entrenado solo con el 80 %, evaluado una vez con el método ya elegido
    m80 = entrenar([(t, y) for _, t, y, _ in datos])
    prueba = [(t, y, x) for _, t, y, x in holdout]
    for tarea in TAREAS:
        mayor = Counter(y[tarea] for _, _, y, _ in datos).most_common(1)[0][0]
        acc[tarea]["holdout_accuracy"] = round(_acierto(m80, prueba, tarea, best[tarea]) / max(len(prueba), 1), 3)
        acc[tarea]["holdout_baseline"] = round(sum(y[tarea] == mayor for _, y, _ in prueba) / max(len(prueba), 1), 3)
    modelo = entrenar([(t, y) for _, t, y, _ in todos])  # el modelo publicado aprende de todo; la cifra honesta es la del hold-out
    modelo["best"] = best
    modelo["eval"] = {"method": f"método elegido con validación cruzada {k} pliegues sobre el 80 %; cifra final en hold-out del 20 % fijo",
                      "n_train": len(datos), "n_test": n, "n_holdout": len(prueba), **acc}
    ruta().write_text(json.dumps(modelo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return modelo["eval"]


if __name__ == "__main__":
    ej = [(tokens("AI agents automate sales outreach"), {"topic": "ia-ventas", "format": "caso-paso-a-paso", "hook": "promesa-proceso", "fit": "alto"}),
          (tokens("Agentes de ventas con IA para prospeccion"), {"topic": "ia-ventas", "format": "caso-paso-a-paso", "hook": "promesa-proceso", "fit": "alto"}),
          (tokens("Nvidia GPU chips data center costs"), {"topic": "infra-costos", "format": "noticia-explicada", "hook": "urgencia-novedad", "fit": "bajo"}),
          (tokens("GPU chips shortage Nvidia"), {"topic": "infra-costos", "format": "noticia-explicada", "hook": "urgencia-novedad", "fit": "bajo"})]
    m = entrenar(ej, min_df=1)
    assert predecir(m, tokens("ventas con agentes"))["topic"][0] == "ia-ventas"
    assert predecir(m, tokens("nvidia chips"))["fit"][0] == "bajo"
    print("student ok")
