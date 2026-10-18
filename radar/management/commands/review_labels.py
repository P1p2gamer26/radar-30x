from django.core.management.base import BaseCommand

from radar import label
from radar.collect import latest


class Command(BaseCommand):
    help = "Segundo LLM re-etiqueta y marca acuerdo -> data/labels.json"

    def handle(self, *a, **o):
        lab = label.revisar(latest()["signals"])
        v = [x for x in lab["labels"].values() if "agree" in x]
        self.stdout.write(f"{len(v)} revisadas, acuerdo tema {sum(x['agree'] for x in v) / max(len(v), 1):.1%}")
