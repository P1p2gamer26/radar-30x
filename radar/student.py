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


ACUERDO = {"topic": "agree", "format": "agree_format", "hook": "agree_hook"}  # marcas de label.revisar; fit no se revisa


def consenso(lab: dict, tarea: str) -> str | None:
    """Etiqueta solo si los dos LLM coinciden en esa tarea (None = dudosa, no se entrena ni se evalúa)."""
    return objetivo(lab, tarea) if tarea == "fit" or lab.get(ACUERDO[tarea]) else None


def es_test(sid: str) -> bool:
    return int(hashlib.md5(sid.encode()).hexdigest(), 16) % 5 == 0  # 20 % fijo para evaluar


def entrenar(ejemplos: list, min_df: int = 2) -> dict:
    """ejemplos = [(tokens, {tarea: clase})]. Devuelve el modelo serializable."""
    df = Counter(t for toks, _ in ejemplos for t in set(toks))
    vocab = {t for t, n in df.items() if n >= min_df}
    modelo = {"vocab_size": len(vocab), "tasks": {}}
    for tarea in TAREAS:
        clases = Counter(y[tarea] for _, y in ejemplos if y.get(tarea) is not None)
        cuenta = defaultdict(Counter)
        for toks, y in ejemplos:
            if y.get(tarea) is not None:
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


# ------------------------------------------------------------------ regresión logística TF-IDF (sklearn offline -> JSON -> Python puro)
TOPN_LR = 40  # términos con mayor coeficiente por clase y tarea que se exportan (controla el tamaño del JSON)


def entrenar_lr(ejemplos: list, C, topn: int = TOPN_LR, min_df: int = 2) -> dict:
    """Entrena con sklearn (TF-IDF sublineal + LR multinomial), poda a los top-N términos por clase, reentrena sobre
    ese vocabulario y exporta a listas JSON: la predicción en Python puro reproduce la de sklearn. C: número o {tarea: C}."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    docs = [t for t, _ in ejemplos]
    ident = lambda d: d  # noqa: E731  (los documentos ya vienen tokenizados con tokens())
    c_de = lambda tarea: C[tarea] if isinstance(C, dict) else C  # noqa: E731

    def ajustar(X, tarea):
        idx = [i for i, (_, y) in enumerate(ejemplos) if y.get(tarea) is not None]
        clf = LogisticRegression(C=c_de(tarea), max_iter=3000).fit(X[idx], [ejemplos[i][1][tarea] for i in idx])
        co = clf.coef_
        return clf, (np.vstack([-co, co]) if co.shape[0] == 1 else co)

    v = TfidfVectorizer(analyzer=ident, sublinear_tf=True, min_df=min_df)
    X = v.fit_transform(docs)
    terms = np.array(v.get_feature_names_out())
    sel = set()
    for tarea in TAREAS:
        _, co = ajustar(X, tarea)
        for fila in co:
            sel.update(terms[np.argsort(-fila)[:topn]])
    voc = sorted(sel)
    v2 = TfidfVectorizer(analyzer=ident, sublinear_tf=True, vocabulary=voc)
    X2 = v2.fit_transform(docs)
    out = {"terms": voc, "idf": [round(float(x), 4) for x in v2.idf_], "tasks": {}}
    for tarea in TAREAS:
        clf, co = ajustar(X2, tarea)
        b = clf.intercept_
        if len(clf.classes_) == 2:  # binaria: puntaje de la clase 0 fijo en 0, el de la 1 = w.x + b
            W = np.column_stack([np.zeros(len(voc)), clf.coef_[0]])
            b = [0.0, float(b[0])]
        else:
            W = clf.coef_.T
        out["tasks"][tarea] = {"classes": [str(c) for c in clf.classes_], "b": [round(float(x), 4) for x in b],
                               "W": [[round(float(x), 4) for x in fila] for fila in W]}
    return out


def _dist_lr(lr: dict, toks: list, tarea: str) -> dict:
    ix = lr.setdefault("_ix", {t: i for i, t in enumerate(lr["terms"])})  # cache en memoria
    tf = Counter(t for t in toks if t in ix)
    v = {ix[t]: (1 + math.log(n)) * lr["idf"][ix[t]] for t, n in tf.items()}
    norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
    m = lr["tasks"][tarea]
    sc = list(m["b"])
    for i, x in v.items():
        for c, w in enumerate(m["W"][i]):
            sc[c] += x / norma * w
    mx = max(sc)
    e = [math.exp(x - mx) for x in sc]
    z = sum(e)
    return {c: x / z for c, x in zip(m["classes"], e)}


def _knn(ejemplos: list, vocab: set) -> dict:
    """Vecinos por coseno TF-IDF: idf + vector normalizado de cada ejemplo + sus clases."""
    n = len(ejemplos)
    df = Counter(t for toks, _ in ejemplos for t in set(toks) if t in vocab)
    idf = {t: round(math.log((1 + n) / (1 + k)) + 1, 3) for t, k in df.items()}
    docs = []
    for toks, y in ejemplos:
        v = _vector(toks, idf)
        if v:
            docs.append([v, [y.get(t) for t in TAREAS]])
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
    votos, usados = Counter(), 0
    for d, s in sim.most_common():
        c = knn["docs"][d][1][col]
        if c is None:  # vecino sin etiqueta de consenso en esta tarea
            continue
        votos[c] += s ** POT_SIM
        usados += 1
        if usados == K_VECINOS:
            break
    total = sum(votos.values())
    return {c: v / total for c, v in votos.items()} if total else {c: 1 / len(modelo["tasks"][tarea]) for c in modelo["tasks"][tarea]}


def distribucion(modelo: dict, toks: list, tarea: str, metodo: str, texto: str = "") -> dict:
    """Probabilidad por clase con el método "nb", "knn" o "ens" (promedio NB + kNN + keywords de taxonomy en tema)."""
    if metodo == "nb" or "knn" not in modelo:
        return _dist_nb(modelo, toks, tarea)
    if metodo == "knn":
        return _dist_knn(modelo, toks, tarea)
    if metodo == "lr" and "lr" in modelo:
        return _dist_lr(modelo["lr"], toks, tarea)
    if metodo == "lrens" and "lr" in modelo:
        a, b = _dist_lr(modelo["lr"], toks, tarea), distribucion(modelo, toks, tarea, "ens", texto)
        return {c: (a.get(c, 0) + b.get(c, 0)) / 2 for c in set(a) | set(b)}
    a, b = _dist_nb(modelo, toks, tarea), _dist_knn(modelo, toks, tarea)
    d = {c: W_NB * a.get(c, 0) + (1 - W_NB) * b.get(c, 0) for c in set(a) | set(b)}
    if tarea == "topic" and texto:
        for r, slug in enumerate(match_topics(texto)[:3]):  # ponytail: desempate por keywords; el primero pesa más
            if slug in d:
                d[slug] += PESO_KW / (r + 1)
    z = sum(d.values())
    return {c: v / z for c, v in d.items()}


def seguro(modelo: dict, tarea: str, prob: float) -> bool | None:
    """¿La probabilidad supera el umbral (elegido en train) con el que el modelo acierta >= 90 %? None si no hay umbral."""
    tau = modelo.get("eval", {}).get(tarea, {}).get("tau")
    return None if tau is None else prob >= tau


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


# ------------------------------------------------------------------ embeddings (solo offline: sentence-transformers + sklearn)
MODELO_EMB = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_ST = {}
# ensamble "multi" (elegido por CV en ml/experimento_modelo.py): LR de cada modelo con su C, promediada con la LR TF-IDF
MULTI = {"e5-base": ("intfloat/multilingual-e5-base", "query: ", 100), "bge-m3": ("BAAI/bge-m3", "", 10),
         "mpnet": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "", 10)}


def embeber(textos: list, nombre: str | None = None):
    """Embeddings normalizados con caché en disco por texto (nombre=None: MiniLM; si no, un modelo de MULTI);
    requiere sentence-transformers (no en producción)."""
    import numpy as np
    hf, pre = (MODELO_EMB, "") if nombre is None else MULTI[nombre][:2]
    cache_f = settings.BASE_DIR / ".cache" / ("emb.npz" if nombre is None else f"emb_{nombre}.npz")
    cache = {}
    if cache_f.exists():
        z = np.load(cache_f)
        cache = dict(zip(z["k"].tolist(), z["v"]))
    llaves = [hashlib.md5(t[:600].encode()).hexdigest() for t in textos]
    faltan = sorted({k: t for k, t in zip(llaves, textos) if k not in cache}.items())
    if faltan:
        if hf not in _ST:
            from sentence_transformers import SentenceTransformer
            _ST[hf] = SentenceTransformer(hf)
            _ST[hf].max_seq_length = 128
        vecs = _ST[hf].encode([pre + t[:600] for _, t in faltan], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        for (k, _), v in zip(faltan, vecs):
            cache[k] = v.astype("float32")
        cache_f.parent.mkdir(exist_ok=True)
        np.savez(cache_f, k=np.array(list(cache)), v=np.array(list(cache.values())))
    return np.array([cache[k] for k in llaves])


def _ajustar_emb(E, filas: list, ys: list, C: float):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C, max_iter=3000).fit(E[filas], ys)


def _dists_emb(clf, E, filas: list) -> list:
    return [dict(zip(clf.classes_, p)) for p in clf.predict_proba(E[filas])] if filas else []


def _prom(*ds) -> dict:
    return {c: sum(d.get(c, 0) for d in ds) / len(ds) for c in set().union(*ds)}


# ------------------------------------------------------------------ evaluación
CS_LR = (3, 30)
CS_EMB = (1, 10)
C_MIX = (30, 10)  # mix = promedio de lr@30 (TF-IDF) y emb@10
SERVIDOR = ("nb", "knn", "ens", "lr@3", "lr@30", "lrens")  # candidatos que corren en Python puro en producción
OFFLINE = SERVIDOR + ("emb@1", "emb@10", "mix", "multi")
OBJ_SEGURO = 0.90  # precisión que debe alcanzar el umbral "seguro"
MIN_SEGURO = 30  # piezas mínimas para fijar el umbral (menos sería ruido)


def _top(d: dict) -> tuple:
    c = max(d, key=lambda k: d[k])
    return c, d[c]


def umbral_seguro(pares: list) -> float | None:
    """Menor probabilidad p tal que las predicciones con prob >= p aciertan >= 90 % (pares = [(prob, acertó)] de CV en train)."""
    pares = sorted(pares, reverse=True)
    ok, mejor = 0, None
    for i, (p, c) in enumerate(pares, 1):
        ok += c
        if i >= MIN_SEGURO and ok / i >= OBJ_SEGURO and (i == len(pares) or pares[i][0] < p):
            mejor = p
    return round(float(mejor), 4) if mejor is not None else None


def metricas(dists: list, ys: list, tau: float | None) -> dict:
    n = max(len(ys), 1)
    ords = [sorted(d, key=lambda c: -d[c]) for d in dists]
    out = {"accuracy": round(sum(o[0] == y for o, y in zip(ords, ys)) / n, 3),
           "top3": round(sum(y in o[:3] for o, y in zip(ords, ys)) / n, 3), "n": len(ys)}
    if tau is not None:
        seg = [o[0] == y for d, o, y in zip(dists, ords, ys) if d[o[0]] >= tau]
        out["safe_accuracy"] = round(sum(seg) / len(seg), 3) if seg else None
        out["safe_coverage"] = round(len(seg) / n, 3)
    return out


def _dist_cand(cand: str, m: dict, lrs: dict, emb: dict, i: int, toks: list, tarea: str, x: str) -> dict:
    """Distribución de un candidato. lrs = {C: export LR}; emb = {C: {fila: dist}} de la tarea."""
    if cand in ("nb", "knn", "ens"):
        return distribucion(m, toks, tarea, cand, x)
    if cand == "lrens":
        return _prom(_dist_lr(lrs[30], toks, tarea), distribucion(m, toks, tarea, "ens", x))
    if cand.startswith("lr@"):
        return _dist_lr(lrs[int(cand[3:])], toks, tarea)
    if cand.startswith("emb@"):
        return emb[int(cand[4:])][i]
    if cand == "multi":
        return _prom(_dist_lr(lrs[C_MIX[0]], toks, tarea), *(emb[n][i] for n in MULTI))
    return _prom(_dist_lr(lrs[C_MIX[0]], toks, tarea), emb[C_MIX[1]][i])  # mix


def run(signals: list, labels: dict, k: int = 5) -> dict:
    """Etiquetas de consenso (dos LLM coinciden). Hold-out fijo del 20 % (es_test) que no se usa para entrenar NI para
    elegir: método (NB, kNN, ensamble, LR-TF-IDF, embeddings), C y umbral "seguro" se eligen con CV SOLO en el 80 %."""
    por_id = {s["id"]: s for s in signals}
    filas = [(sid, tokens(por_id[sid]["title"] + " " + por_id[sid].get("text", ""), por_id[sid]["source"]),
              {t: consenso(lab, t) for t in TAREAS}, {t: objetivo(lab, t) for t in TAREAS},
              por_id[sid]["title"] + " " + por_id[sid].get("text", ""))
             for sid, lab in labels.items() if sid in por_id]
    try:
        E = embeber([f[4] for f in filas])
        Ex = {n: embeber([f[4] for f in filas], n) for n in MULTI}
    except ImportError:
        E = None
    cands = OFFLINE if E is not None else SERVIDOR
    en_hold = lambda sid: es_test(sid) and not labels[sid].get("ext")  # noqa: E731  (etiquetas ampliadas "ext": solo entrenan, el hold-out sigue fijo)
    hold = [i for i, f in enumerate(filas) if en_hold(f[0])]
    dat = [i for i, f in enumerate(filas) if not en_hold(f[0])]
    pliegue = lambda i: int(hashlib.md5(filas[i][0].encode()).hexdigest(), 16) % k  # noqa: E731
    ej = lambda idx: [(filas[i][1], filas[i][2]) for i in idx]  # noqa: E731
    con = lambda idx, t: [i for i in idx if filas[i][2][t] is not None]  # noqa: E731

    def preparar(tr, te, todas=False):
        """Modelos entrenados con `tr`; distribuciones de embeddings para las filas de `te`, por tarea."""
        m = entrenar(ej(tr))
        lrs = {C: entrenar_lr(ej(tr), C) for C in CS_LR}
        emb = {t: {} for t in TAREAS}
        if E is not None:
            for t in TAREAS:
                for C in CS_EMB:
                    clf = _ajustar_emb(E, con(tr, t), [filas[i][2][t] for i in con(tr, t)], C)
                    fs = te if todas else con(te, t)  # todas: también las filas sin consenso (para medir contra todas las etiquetas)
                    emb[t][C] = dict(zip(fs, _dists_emb(clf, E, fs)))
                fs = te if todas else con(te, t)
                for n, (_, _, C) in MULTI.items():
                    clf = _ajustar_emb(Ex[n], con(tr, t), [filas[i][2][t] for i in con(tr, t)], C)
                    emb[t][n] = dict(zip(fs, _dists_emb(clf, Ex[n], fs)))
        return m, lrs, emb

    oof = {t: {c: {} for c in cands} for t in TAREAS}
    base_ok, n_cv = Counter(), Counter()
    for f in range(k):
        tr = [i for i in dat if pliegue(i) != f]
        te = [i for i in dat if pliegue(i) == f]
        m, lrs, emb = preparar(tr, te)
        for t in TAREAS:
            mayor = Counter(filas[i][2][t] for i in con(tr, t)).most_common(1)[0][0]
            base_ok[t] += sum(filas[i][2][t] == mayor for i in con(te, t))
            n_cv[t] += len(con(te, t))
            for i in con(te, t):
                for c in cands:
                    oof[t][c][i] = _dist_cand(c, m, lrs, emb[t], i, filas[i][1], t, filas[i][4])

    elegido, acc = {}, {}
    for t in TAREAS:
        base = round(base_ok[t] / max(n_cv[t], 1), 3)
        por = {c: round(sum(_top(v)[0] == filas[i][2][t] for i, v in oof[t][c].items()) / max(len(oof[t][c]), 1), 3) for c in cands}
        srv, off = max(SERVIDOR, key=lambda c: por[c]), max(cands, key=lambda c: por[c])
        usable = por[srv] - base >= MARGEN_USABLE
        if not usable:  # sin mejora real sobre la base: nos quedamos con el modelo simple de siempre
            srv = off = "nb"
        elegido[t] = (srv, off)
        acc[t] = {"accuracy": por[srv], "baseline": base, "nb": por["nb"], "knn": por["knn"], "ensemble": por["ens"],
                  "lr": max(por["lr@3"], por["lr@30"]), "method": srv, "usable": usable, "cv": por}

    # umbral "seguro" por tarea y modelo elegido: probabilidades de las predicciones de CV en el 80 %
    tau = {t: [umbral_seguro([(_top(v)[1], _top(v)[0] == filas[i][2][t]) for i, v in oof[t][c].items()]) for c in elegido[t]]
           for t in TAREAS}

    # hold-out: modelos entrenados con el 80 %, evaluados UNA vez con lo ya elegido
    c_lr = {t: int(elegido[t][0][3:]) if elegido[t][0].startswith("lr@") else 30 for t in TAREAS}  # C del LR servido
    m80, lrs80, emb80 = preparar(dat, hold, todas=True)
    lrs80[30] = entrenar_lr(ej(dat), c_lr)  # el LR servido (C por tarea, podado a top-N) es el que se mide
    for t in TAREAS:
        mayor = Counter(filas[i][2][t] for i in con(dat, t)).most_common(1)[0][0]
        hc = con(hold, t)
        acc[t]["n_holdout"] = len(hc)
        acc[t]["holdout_baseline"] = round(sum(filas[i][2][t] == mayor for i in hc) / max(len(hc), 1), 3)
        acc[t]["holdout_baseline_all"] = round(sum(filas[i][3][t] == mayor for i in hold) / max(len(hold), 1), 3)
        for nombre, c, t_ in (("", elegido[t][0], tau[t][0]), ("offline", elegido[t][1], tau[t][1])):
            emb_h = emb80[t]
            if c.startswith("lr@"):
                c = "lr@30"  # lrs80[30] ya trae el C elegido para esta tarea
            dist = lambda i: _dist_cand(c, m80, lrs80, emb_h, i, filas[i][1], t, filas[i][4])  # noqa: E731
            r_c = metricas([dist(i) for i in hc], [filas[i][2][t] for i in hc], t_)
            r_a = metricas([dist(i) for i in hold], [filas[i][3][t] for i in hold], t_)  # contra TODAS las etiquetas (incluye dudosas)
            campos = {"holdout_accuracy": r_c["accuracy"], "holdout_top3": r_c["top3"], "tau": t_,
                      "safe_accuracy": r_c.get("safe_accuracy"), "safe_coverage": r_c.get("safe_coverage"),
                      "holdout_accuracy_all": r_a["accuracy"], "holdout_top3_all": r_a["top3"]}
            if nombre:
                acc[t]["offline"] = {**campos, "holdout_baseline": acc[t]["holdout_baseline"], "method": elegido[t][1],
                                     "cv_accuracy": acc[t]["cv"][elegido[t][1]]}
            else:
                acc[t].update(campos)

    # modelo publicado: aprende de todo el consenso; la cifra honesta es la del hold-out
    todo = dat + hold
    modelo = entrenar(ej(todo))
    modelo["lr"] = entrenar_lr(ej(todo), c_lr)
    modelo["best"] = {t: ("lr" if elegido[t][0].startswith("lr@") else elegido[t][0]) for t in TAREAS}
    modelo["offline_best"] = {t: ("lr" if elegido[t][1].startswith("lr@") else elegido[t][1]) for t in TAREAS}
    modelo["eval"] = {"method": f"consenso de dos LLM; método y umbral elegidos con validación cruzada {k} pliegues sobre el 80 %; "
                                "cifra final en hold-out del 20 % fijo",
                      "n_train": len(dat), "n_cv": max(n_cv.values()), "n_holdout": len(hold),
                      "n_labels": len(filas), "target_precision": OBJ_SEGURO, **acc}
    ruta().write_text(json.dumps(modelo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return modelo["eval"]


def clasificar_corpus(modelo: dict, signals: list, labels: dict) -> dict | None:
    """Clasifica TODAS las `signals` (labels = etiquetas para entrenar embeddings). {sid: {tarea: (clase, prob)}} con el mejor modelo OFFLINE de cada tarea (embeddings si ganaron en CV). None si faltan
    las librerías offline: el llamador cae al estudiante de servidor."""
    ob = modelo.get("offline_best") or modelo.get("best", {})
    emb = {t: m for t, m in ob.items() if m.startswith(("emb@", "mix", "multi"))}
    texto = lambda s: s["title"] + " " + s.get("text", "")  # noqa: E731
    por_id = {s["id"]: s for s in signals}
    ent = [sid for sid in labels if sid in por_id]
    clfs = {}
    if emb:
        try:
            E_all = embeber([texto(s) for s in signals])
            Ex_all = {n: embeber([texto(s) for s in signals], n) for n in MULTI} if "multi" in emb.values() else {}
        except ImportError:
            return None
        pos = {s["id"]: j for j, s in enumerate(signals)}
        E_tr = E_all[[pos[sid] for sid in ent]]
        for t, m in emb.items():
            idx = [j for j, sid in enumerate(ent) if consenso(labels[sid], t) is not None]
            ys = [consenso(labels[ent[j]], t) for j in idx]
            if m == "multi":
                clfs[t] = {n: _ajustar_emb(Ex_all[n][[pos[sid] for sid in ent]], idx, ys, C) for n, (_, _, C) in MULTI.items()}
            else:
                clfs[t] = _ajustar_emb(E_tr, idx, ys, int(m[4:]) if m.startswith("emb@") else C_MIX[1])
    out = {s["id"]: {} for s in signals}
    for t in modelo["tasks"]:
        m = ob.get(t, "nb")
        todas = list(range(len(signals)))
        if m == "multi":
            ds = [list(x) for x in zip(*(_dists_emb(c, Ex_all[n], todas) for n, c in clfs[t].items()))]
        else:
            ds = _dists_emb(clfs[t], E_all, todas) if t in clfs else None
        for j, s in enumerate(signals):
            toks = tokens(texto(s), s["source"])
            if ds is None:
                d = distribucion(modelo, toks, t, m, texto(s))
            elif m == "multi":
                d = _prom(distribucion(modelo, toks, t, "lr", texto(s)), *ds[j])
            elif m.startswith("emb@"):
                d = ds[j]
            else:
                d = _prom(distribucion(modelo, toks, t, "lr", texto(s)), ds[j])
            c = max(d, key=lambda q: d[q])
            out[s["id"]][t] = (c, round(float(d[c]), 3))
    return out


if __name__ == "__main__":
    ej = [(tokens("AI agents automate sales outreach"), {"topic": "ia-ventas", "format": "caso-paso-a-paso", "hook": "promesa-proceso", "fit": "alto"}),
          (tokens("Agentes de ventas con IA para prospeccion"), {"topic": "ia-ventas", "format": "caso-paso-a-paso", "hook": "promesa-proceso", "fit": "alto"}),
          (tokens("Nvidia GPU chips data center costs"), {"topic": "infra-costos", "format": "noticia-explicada", "hook": "urgencia-novedad", "fit": "bajo"}),
          (tokens("GPU chips shortage Nvidia"), {"topic": "infra-costos", "format": "noticia-explicada", "hook": "urgencia-novedad", "fit": "bajo"})]
    m = entrenar(ej, min_df=1)
    assert predecir(m, tokens("ventas con agentes"))["topic"][0] == "ia-ventas"
    assert predecir(m, tokens("nvidia chips"))["fit"][0] == "bajo"
    print("student ok")
