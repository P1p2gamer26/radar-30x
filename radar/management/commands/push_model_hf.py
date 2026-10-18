"""Publica el encoder afinado (models/estelaria-topic) + model card con métricas en Hugging Face Hub.
Uso: HF_TOKEN=... python manage.py push_model_hf  (requiere huggingface_hub; sin token no hace nada y dice qué falta)."""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

REPO = "P1p2gamer26/estelaria-topic-classifier"

CARD = """---
license: mit
language: [es, en]
base_model: {base}
tags: [text-classification, fine-tuned, content-intelligence, hackathon-30x]
---
# EstelarIA: clasificador de tema (encoder afinado)

Afinado de `{base}` para asignar a titulares/textos sobre IA uno de {k} temas para ejecutivos de LatAm
(etiquetas: consenso de dos LLM sobre {n} señales públicas de Hacker News, Google News y YouTube).

Evaluación en un hold-out fijo del 20 % que no se usó para entrenar ni elegir (n={nh}); base = clase mayoritaria ({base_acc:.0%}):

- top-1: **{acc:.1%}**, top-3: {top3:.1%}
- cuando está seguro (prob >= {tau}): acierta {sa} y cubre {sc} de las piezas

Entrenado en {seg} s en {dev}. Reproducible con `ml/train_hf.py` / `ml/estelaria_finetune.ipynb` del repo
https://github.com/P1p2gamer26/radar-30x. Entrada: `"<fuente>: <título>. <texto>"` (max 96 tokens).
"""


class Command(BaseCommand):
    help = "Sube models/estelaria-topic + model card a Hugging Face Hub (necesita HF_TOKEN)"

    def handle(self, *a, **o):
        tok = os.environ.get("HF_TOKEN")
        carpeta = settings.BASE_DIR / "models" / "estelaria-topic"
        ev_f = settings.DATA_DIR / "hf_eval_topic.json"
        if not tok:
            raise CommandError("Falta HF_TOKEN (token con permiso write de huggingface.co/settings/tokens).")
        if not carpeta.exists() or not ev_f.exists():
            raise CommandError("Falta entrenar: python ml/train_hf.py --task topic --final")
        from huggingface_hub import HfApi

        ev = json.loads(ev_f.read_text(encoding="utf-8"))
        c = ev["candidates"][ev["chosen"]]
        h = c["holdout"]
        pct = lambda x: "n/d" if x is None else f"{x:.0%}"  # noqa: E731
        card = CARD.format(base=ev["chosen"], k=len(ev["classes"]), n=ev["n_train"] + ev["n_val"] + ev["n_holdout"], nh=h["n"],
                           base_acc=ev["baseline_majority"], acc=h["accuracy"], top3=h["top3"], tau=round(c["tau"] or 0, 3),
                           sa=pct(h.get("safe_accuracy")), sc=pct(h.get("safe_coverage")), seg=c["seconds"], dev=ev["device"])
        api = HfApi(token=tok)
        api.create_repo(REPO, exist_ok=True)
        api.upload_folder(folder_path=str(carpeta), repo_id=REPO)
        api.upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md", repo_id=REPO)
        api.upload_file(path_or_fileobj=ev_f.read_bytes(), path_in_repo="eval.json", repo_id=REPO)
        self.stdout.write(f"https://huggingface.co/{REPO}")
