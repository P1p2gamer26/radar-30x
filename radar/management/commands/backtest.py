"""Prueba hacia atrás del radar sobre el último snapshot; escribe data/backtest.json (sin red)."""
import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import backtest
from radar.build import etiquetar_todo
from radar.collect import latest
from radar.taxonomy import TOPICS


class Command(BaseCommand):
    help = "Backtest: marcados 'empezando' con datos al día 7 vs lo que creció en los días 8-14"

    def handle(self, *a, **k):
        snap = latest()
        fin = datetime.fromisoformat(snap["collected_at"].replace("Z", "+00:00"))
        labs = etiquetar_todo(snap["signals"])
        topic_of = {sid: lab["topic"] for sid, lab in labs.items() if lab["topic"] in TOPICS}
        r = backtest.correr(snap["signals"], topic_of, list(TOPICS), fin)
        (settings.DATA_DIR / "backtest.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(json.dumps({x: r[x] for x in ("k", "base_azar", "radar", "popularidad")}, ensure_ascii=False))
