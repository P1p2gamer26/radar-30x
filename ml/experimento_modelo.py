"""Experimento: ¿mejores embeddings / ensamble para el TEMA? Todo se elige con CV (5 pliegues) en el 80 %; el hold-out
fijo se reporta UNA vez, solo para el ganador. Uso (raíz del repo): DJANGO_SECRET_KEY=x python ml/experimento_modelo.py [--holdout]"""
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from sklearn.linear_model import LogisticRegression  # noqa: E402

from radar import label, student  # noqa: E402
from radar.collect import latest  # noqa: E402

MODELOS = {  # nombre -> (id HF, prefijo)
    "minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", ""),
    "mpnet": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", ""),
    "e5-small": ("intfloat/multilingual-e5-small", "query: "),
    "e5-base": ("intfloat/multilingual-e5-base", "query: "),
    "labse": ("sentence-transformers/LaBSE", ""),
    "bge-m3": ("BAAI/bge-m3", ""),
}
CS = (1, 10, 30, 100)
K = 5
student.TAREAS = ("topic",)  # solo tema: acelera entrenar_lr


def emb(nombre, textos):
    """Embeddings normalizados con caché por texto en .cache/emb_<nombre>.npz."""
    f = Path(".cache") / f"emb_{nombre}.npz"
    cache = dict(zip(*(lambda z: (z["k"].tolist(), z["v"]))(np.load(f)))) if f.exists() else {}
    llaves = [hashlib.md5(t[:600].encode()).hexdigest() for t in textos]
    faltan = sorted({k: t for k, t in zip(llaves, textos) if k not in cache}.items())
    if faltan:
        from sentence_transformers import SentenceTransformer
        hf, pre = MODELOS[nombre]
        t0 = time.time()
        m = SentenceTransformer(hf)
        m.max_seq_length = 128
        v = m.encode([pre + t[:600] for _, t in faltan], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        for (k, _), x in zip(faltan, v):
            cache[k] = x.astype("float32")
        f.parent.mkdir(exist_ok=True)
        np.savez(f, k=np.array(list(cache)), v=np.array(list(cache.values())))
        print(f"  [{nombre}] {len(faltan)} textos en {time.time() - t0:.0f}s", flush=True)
    return np.array([cache[k] for k in llaves])


def prom(*ds):
    return {c: sum(d.get(c, 0) for d in ds) / len(ds) for c in set().union(*ds)}


def top(d):
    c = max(d, key=lambda k: d[k])
    return c, d[c]


def main():
    signals, labels = latest()["signals"], label.cargar()["labels"]
    por_id = {s["id"]: s for s in signals}
    filas = [(sid, por_id[sid]["title"] + " " + por_id[sid].get("text", ""), por_id[sid]["source"], student.consenso(lab, "topic"))
             for sid, lab in labels.items() if sid in por_id]
    filas = [f for f in filas if f[3] is not None]
    hold_ok = lambda f: student.es_test(f[0]) and not labels[f[0]].get("ext")  # noqa: E731
    dat = [i for i, f in enumerate(filas) if not hold_ok(f)]
    hold = [i for i, f in enumerate(filas) if hold_ok(f)]
    print(f"entrenamiento={len(dat)} hold-out={len(hold)} (consenso de tema)")
    toks = [student.tokens(f[1], f[2]) for f in filas]
    y = [f[3] for f in filas]
    Es = {n: emb(n, [f[1] for f in filas]) for n in (sys.argv[1].split(",") if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else MODELOS)}
    pl = lambda i: int(hashlib.md5(filas[i][0].encode()).hexdigest(), 16) % K  # noqa: E731

    def componentes(tr, te):
        """{nombre: {fila: dist}} entrenando con tr y prediciendo te."""
        out = {}
        lr = student.entrenar_lr([(toks[i], {"topic": y[i]}) for i in tr], 30)
        out["tfidf"] = {i: student._dist_lr(lr, toks[i], "topic") for i in te}
        for n, E in Es.items():
            for C in CS:
                clf = LogisticRegression(C=C, max_iter=3000).fit(E[tr], [y[i] for i in tr])
                out[f"{n}@{C}"] = dict(zip(te, [dict(zip(clf.classes_, p)) for p in clf.predict_proba(E[te])]))
        return out

    oof = {}
    for f in range(K):
        tr, te = [i for i in dat if pl(i) != f], [i for i in dat if pl(i) == f]
        for n, d in componentes(tr, te).items():
            oof.setdefault(n, {}).update(d)
    acc = lambda d: round(sum(top(v)[0] == y[i] for i, v in d.items()) / len(d), 3)  # noqa: E731
    r = {n: acc(d) for n, d in oof.items()}
    mejorC = {n: max(CS, key=lambda C: r[f"{n}@{C}"]) for n in Es}
    comb = {"BASE mix = tfidf + minilm@10": ["tfidf", "minilm@10"]}
    for n in Es:
        comb[f"{n}@mejorC"] = [f"{n}@{mejorC[n]}"]
        comb[f"tfidf + {n}@mejorC"] = ["tfidf", f"{n}@{mejorC[n]}"]
    todos = [f"{n}@{mejorC[n]}" for n in Es]
    comb["todos los emb (mejorC)"] = todos
    comb["tfidf + todos los emb"] = ["tfidf"] + todos
    ranking = sorted(((n, sorted(r[f"{n}@{C}"] for C in CS)[-1]) for n in Es), key=lambda x: -x[1])
    top2 = [f"{n}@{mejorC[n]}" for n, _ in ranking[:2]]
    comb["tfidf + 2 mejores emb"] = ["tfidf"] + top2
    comb["tfidf + 3 mejores emb"] = ["tfidf"] + [f"{n}@{mejorC[n]}" for n, _ in ranking[:3]]
    print("\nCV 5 pliegues (acierto top-1 en el 80 %):")
    for n in ["tfidf"] + [f"{n}@{C}" for n in Es for C in CS]:
        print(f"  {n:22s} {r[n]:.3f}")
    res = {}
    print("\nCombinaciones (promedio de probabilidades):")
    for nom, cs in comb.items():
        d = {i: prom(*(oof[c][i] for c in cs)) for i in oof["tfidf"]}
        res[nom] = (acc(d), cs, d)
        ok3 = sum(y[i] in sorted(v, key=lambda k: -v[k])[:3] for i, v in d.items()) / len(d)
        tau = student.umbral_seguro([(top(v)[1], top(v)[0] == y[i]) for i, v in d.items()])
        print(f"  {nom:34s} top1={res[nom][0]:.3f} top3={ok3:.3f} tau90={tau}")
    ganador = max((n for n in res if not n.startswith("BASE")), key=lambda n: res[n][0])
    print(f"\nmejor en CV: {ganador} {res[ganador][0]:.3f}  vs base {res['BASE mix = tfidf + minilm@10'][0]:.3f}")
    if "--holdout" in sys.argv:
        cs = res[ganador][1]
        tau = student.umbral_seguro([(top(v)[1], top(v)[0] == y[i]) for i, v in res[ganador][2].items()])
        c = componentes(dat, hold)
        d = {i: prom(*(c[k][i] for k in cs)) for i in hold}
        seg = [top(v)[0] == y[i] for i, v in d.items() if tau and top(v)[1] >= tau]
        print(f"HOLD-OUT {ganador} {cs}: top1={acc(d)} top3={sum(y[i] in sorted(v, key=lambda k: -v[k])[:3] for i, v in d.items()) / len(d):.3f} "
              f"tau={tau} seguro={sum(seg) / max(len(seg), 1):.3f} cobertura={len(seg) / len(d):.3f} n={len(d)}")


main()
