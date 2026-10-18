"""Afina un encoder de Hugging Face para clasificar TEMA (o formato) de señales sobre IA. Reproducible, sin Django.

  python ml/train_hf.py --task topic --models intfloat/multilingual-e5-small,xlm-roberta-base
  python ml/train_hf.py --task topic --models <ganador> --epochs 5 --final   # reescribe predicciones + pesos

Datos: data/labels.json (consenso de dos LLM) + último data/snapshots/*.json. Hold-out FIJO = mismo 20 % que radar/student.py
(md5(id) % 5 == 0 y etiqueta no 'ext'): NUNCA se usa para entrenar ni elegir. Dentro del 80 % se aparta una validación
(md5('v'+id) % 7 == 0) para elegir modelo, época y umbral "seguro" (precisión >= 90 %).
Salidas: data/hf_preds_<task>.json (clase + prob por señal), data/hf_eval_<task>.json (métricas) y pesos en models/ (gitignored).
"""
import argparse
import glob
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
ACUERDO = {"topic": "agree", "format": "agree_format"}
H = lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16)  # noqa: E731


def datos(task):
    labels = json.loads((ROOT / "data/labels.json").read_text(encoding="utf-8"))["labels"]
    snap = json.loads(Path(sorted(glob.glob(str(ROOT / "data/snapshots/*.json")))[-1]).read_text(encoding="utf-8"))["signals"]
    texto = lambda s: f"{s['source']}: {s['title']}. {s.get('text', '')}"[:700]  # noqa: E731
    por = {s["id"]: s for s in snap}
    filas = [(sid, texto(por[sid]), v[task]) for sid, v in labels.items() if sid in por and v.get(ACUERDO[task])]
    ids_hold = {f[0] for f in filas if H(f[0]) % 5 == 0 and not labels[f[0]].get("ext")}
    hold = [f for f in filas if f[0] in ids_hold]
    dat = [f for f in filas if f[0] not in ids_hold]
    val = [f for f in dat if H("v" + f[0]) % 7 == 0]
    tr = [f for f in dat if H("v" + f[0]) % 7 != 0]
    return tr, val, hold, snap, texto


def umbral_seguro(pares, obj=0.90, minimo=30):
    pares = sorted(pares, reverse=True)
    ok, mejor = 0, None
    for i, (p, c) in enumerate(pares, 1):
        ok += c
        if i >= minimo and ok / i >= obj and (i == len(pares) or pares[i][0] < p):
            mejor = float(p)
    return mejor


def metricas(P, y, tau):
    o = np.argsort(-P, axis=1)
    r = {"accuracy": float((o[:, 0] == y).mean()), "top3": float((o[:, :3] == y[:, None]).any(1).mean()), "n": len(y)}
    if tau is not None:
        m = P.max(1) >= tau
        r["safe_accuracy"] = float((o[m, 0] == y[m]).mean()) if m.any() else None
        r["safe_coverage"] = float(m.mean())
    return r


def predecir(model, tok, textos, prefijo, dev, bs=64):
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
        for i in range(0, len(textos), bs):
            b = tok([prefijo + t for t in textos[i:i + bs]], truncation=True, max_length=96, padding=True, return_tensors="pt").to(dev)
            out.append(torch.softmax(model(**b).logits.float(), -1).cpu().numpy())
    return np.concatenate(out)


def entrenar(nombre, tr, val, clases, epochs, lr, bs, congelar, dev):
    ci = {c: i for i, c in enumerate(clases)}
    tok = AutoTokenizer.from_pretrained(nombre)
    model = AutoModelForSequenceClassification.from_pretrained(nombre, num_labels=len(clases)).to(dev)
    if congelar:  # la matriz de embeddings es ~70 % de xlm-r base: congelarla cabe en 4 GB
        for p in model.base_model.embeddings.word_embeddings.parameters():
            p.requires_grad = False
    pref = "query: " if "e5" in nombre else ""
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)
    pasos = epochs * math.ceil(len(tr) / bs)
    sch = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / (0.1 * pasos), max(0.0, (pasos - s) / (0.9 * pasos))))
    scaler = torch.amp.GradScaler()
    yv = np.array([ci[f[2]] for f in val])
    rng = np.random.default_rng(0)
    mejor, mejor_estado, hist = -1, None, []
    for ep in range(epochs):
        model.train()
        orden = rng.permutation(len(tr))
        for i in range(0, len(tr), bs):
            lote = [tr[j] for j in orden[i:i + bs]]
            b = tok([pref + f[1] for f in lote], truncation=True, max_length=96, padding=True, return_tensors="pt").to(dev)
            y = torch.tensor([ci[f[2]] for f in lote], device=dev)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = torch.nn.functional.cross_entropy(model(**b).logits.float(), y, label_smoothing=0.05)
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sch.step()
        acc = float((predecir(model, tok, [f[1] for f in val], pref, dev).argmax(1) == yv).mean())
        hist.append(round(acc, 4))
        print(f"  {nombre} ep{ep + 1}: val acc {acc:.3f}", flush=True)
        if acc > mejor:
            mejor, mejor_estado = acc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(mejor_estado)
    return model, tok, pref, mejor, hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="topic", choices=list(ACUERDO))
    ap.add_argument("--models", default="intfloat/multilingual-e5-small")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--final", action="store_true", help="guarda pesos + predicciones del corpus con el mejor por validación")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tr, val, hold, snap, texto = datos(a.task)
    clases = sorted({f[2] for f in tr + val + hold})
    ci = {c: i for i, c in enumerate(clases)}
    print(f"train {len(tr)} val {len(val)} hold-out {len(hold)} clases {len(clases)} dev {dev}")
    res, mejor = {}, None
    for nombre in a.models.split(","):
        t0 = time.time()
        congelar = "xlm-roberta" in nombre or "-base" in nombre
        lr = a.lr / 2 if congelar else a.lr
        model, tok, pref, vacc, hist = entrenar(nombre, tr, val, clases, a.epochs, lr, a.bs, congelar, dev)
        Pv = predecir(model, tok, [f[1] for f in val], pref, dev)
        yv = np.array([ci[f[2]] for f in val])
        tau = umbral_seguro([(p.max(), p.argmax() == y) for p, y in zip(Pv, yv)])
        Ph = predecir(model, tok, [f[1] for f in hold], pref, dev)
        yh = np.array([ci[f[2]] for f in hold])
        res[nombre] = {"val_accuracy": round(vacc, 4), "val_hist": hist, "tau": tau, "seconds": round(time.time() - t0),
                       "holdout": metricas(Ph, yh, tau)}  # el hold-out solo se REPORTA; la elección es por val_accuracy
        print(nombre, json.dumps(res[nombre]), flush=True)
        if mejor is None or vacc > res[mejor[0]]["val_accuracy"]:
            mejor = (nombre, model, tok, pref)
        else:
            del model
        torch.cuda.empty_cache()
    elegido = max(res, key=lambda k: res[k]["val_accuracy"])
    print("elegido por validación:", elegido)
    base = max(np.bincount([ci[f[2]] for f in tr]) / len(tr))
    out = {"task": a.task, "chosen": elegido, "baseline_majority": round(float(base), 3), "n_train": len(tr), "n_val": len(val),
           "n_holdout": len(hold), "classes": clases, "candidates": res, "device": torch.cuda.get_device_name(0) if dev == "cuda" else "cpu"}
    if a.final:
        _, model, tok, pref = mejor
        P = predecir(model, tok, [texto(s) for s in snap], pref, dev)
        preds = {s["id"]: [clases[int(p.argmax())], round(float(p.max()), 3)] for s, p in zip(snap, P)}
        (ROOT / f"data/hf_preds_{a.task}.json").write_text(json.dumps({"model": elegido, "tau": res[elegido]["tau"], "preds": preds},
                                                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        d = ROOT / "models" / f"estelaria-{a.task}"
        model.save_pretrained(d)
        tok.save_pretrained(d)
        (d / "classes.json").write_text(json.dumps(clases), encoding="utf-8")
        np.save(ROOT / "models" / f"holdout_probs_{a.task}.npy", predecir(model, tok, [f[1] for f in hold], pref, dev))
        (ROOT / "models" / f"holdout_ids_{a.task}.json").write_text(json.dumps([f[0] for f in hold]))
    (ROOT / f"data/hf_eval_{a.task}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
