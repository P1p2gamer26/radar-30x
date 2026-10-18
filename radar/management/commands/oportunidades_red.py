import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import redes
from radar.build import etiquetar_todo
from radar.collect import latest
from radar.taxonomy import TOPICS
from radar.views import cargar_radar


class Command(BaseCommand):
    help = "Temas que despegan en una sola red (aunque en general se descarten) -> data/oportunidades_red.json"

    def handle(self, *args, **opts):
        snap = latest()
        fin = datetime.fromisoformat(snap["collected_at"].replace("Z", "+00:00"))
        labs = etiquetar_todo(snap["signals"])
        topic_of = {sid: l["topic"] for sid, l in labs.items() if l["topic"] in TOPICS}
        radar = cargar_radar()
        dec = {t["slug"]: t["decision"] for t in radar["topics"]}
        nombres = {t["slug"]: t["name"] for t in radar["topics"]}
        out = redes.oportunidades(snap["signals"], topic_of, fin, decisiones=dec, nombres=nombres)
        (settings.DATA_DIR / "oportunidades_red.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        for o in out:
            self.stdout.write(f"{o['tema']} / {o['red']}: {o['growth']}x, {o['piezas']} piezas, global {o['decision_global']}")
        self.stdout.write(f"{len(out)} oportunidades")
