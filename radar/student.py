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

from .taxonomy import normalizar

TAREAS = ("topic", "format", "hook", "fit")
_PAL = re.compile(r"[a-z0-9][a-z0-9\-\.]{1,}")
STOP = set("the and for with that this from your you are how what why los las del por para con una que como mas sus".split())


def tokens(texto: str, source: str = "") -> list:
    pal = [p.strip(".-") for p in _PAL.findall(normalizar(texto))]
    pal = [p for p in pal if len(p) > 2 and p not in STOP]
    return pal + [f"{a}_{b}" for a, b in zip(pal, pal[1:])] + ([f"src:{source}"] if source else [])


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
    return modelo


def predecir(modelo: dict, toks: list) -> dict:
    """{tarea: (clase, probabilidad)}."""
    out = {}
    conocidos = modelo.setdefault("_conocidos", {})  # cache en memoria, no se guarda
    for tarea, clases in modelo["tasks"].items():
        if tarea not in conocidos:
            conocidos[tarea] = set().union(*(m["ll"] for m in clases.values()))
        vistos = [t for t in toks if t in conocidos[tarea]]
        puntajes = {c: m["prior"] + sum(m["ll"].get(t, m["unk"]) for t in vistos) for c, m in clases.items()}
        mx = max(puntajes.values())
        z = sum(math.exp(v - mx) for v in puntajes.values())
        mejor = max(puntajes, key=lambda c: puntajes[c])
        out[tarea] = (mejor, round(1 / z, 3))  # exp(mx - mx) / z
    return out


def ruta():
    return settings.DATA_DIR / "student.json"


def cargar() -> dict | None:
    return json.loads(ruta().read_text(encoding="utf-8")) if ruta().exists() else None


def run(signals: list, labels: dict) -> dict:
    """Entrena con 80 % de las etiquetas, mide contra el 20 % y guarda el modelo (reentrenado con todo)."""
    por_id = {s["id"]: s for s in signals}
    datos = [(sid, tokens(por_id[sid]["title"] + " " + por_id[sid].get("text", ""), por_id[sid]["source"]),
              {t: objetivo(lab, t) for t in TAREAS})
             for sid, lab in labels.items() if sid in por_id]
    train = [(t, y) for sid, t, y in datos if not es_test(sid)]
    test = [(t, y) for sid, t, y in datos if es_test(sid)]
    m = entrenar(train)
    acc = {}
    for tarea in TAREAS:
        aciertos = sum(predecir(m, toks)[tarea][0] == y[tarea] for toks, y in test)
        base = Counter(y[tarea] for _, y in train).most_common(1)[0][0]
        acc[tarea] = {"accuracy": round(aciertos / max(len(test), 1), 3),
                      "baseline": round(sum(y[tarea] == base for _, y in test) / max(len(test), 1), 3)}
    modelo = entrenar([(t, y) for _, t, y in datos])
    modelo["eval"] = {"n_train": len(train), "n_test": len(test), **acc}
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
