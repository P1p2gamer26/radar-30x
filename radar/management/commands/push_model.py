"""Publica el estudiante en Hugging Face Hub. Uso: HF_TOKEN=... python manage.py push_model (requiere huggingface_hub)."""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

REPO = "P1p2gamer26/radar-30x-student"

CARD = """---
license: mit
language: [es, en]
tags: [text-classification, naive-bayes, content-intelligence, hackathon-30x]
---
# EstelarIA: estudiante (Naive Bayes multinomial)

Clasifica titulares y textos de piezas sobre IA en **tema** (20 temas para ejecutivos LatAm), **formato**, **gancho**
y **encaje ejecutivo** (alto/bajo). Destilado de etiquetas de un LLM profesor ({teacher}) sobre {n} señales públicas
(Hacker News, Google News, YouTube RSS). Corre en Python puro (stdlib), costo USD 0 por señal.

Evaluación (20 % reservado, accuracy vs baseline de clase mayoritaria):
{eval}

Uso: descarga `student.json` y usa `radar/student.py` del repo https://github.com/P1p2gamer26/radar-30x
"""


class Command(BaseCommand):
    help = "Sube data/student.json + model card a Hugging Face Hub"

    def handle(self, *args, **opts):
        from huggingface_hub import HfApi

        modelo = json.loads((settings.DATA_DIR / "student.json").read_text(encoding="utf-8"))
        meta = json.loads((settings.DATA_DIR / "labels.json").read_text(encoding="utf-8"))["meta"]
        ev = modelo["eval"]
        tabla = "\n".join(f"- {k}: {v['accuracy']:.0%} (baseline {v['baseline']:.0%})" for k, v in ev.items() if isinstance(v, dict))
        api = HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(REPO, exist_ok=True)
        api.upload_file(path_or_fileobj=str(settings.DATA_DIR / "student.json"), path_in_repo="student.json", repo_id=REPO)
        api.upload_file(path_or_fileobj=CARD.format(teacher=meta["model"], n=ev["n_train"], eval=tabla).encode(),
                        path_in_repo="README.md", repo_id=REPO)
        self.stdout.write(f"https://huggingface.co/{REPO}")
