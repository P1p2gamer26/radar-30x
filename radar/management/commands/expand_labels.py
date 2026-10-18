from django.core.management.base import BaseCommand

from radar import label
from radar.collect import latest


class Command(BaseCommand):
    help = "Etiqueta con dos LLM las señales sin etiquetar (ext=True: solo entrenamiento) -> data/labels.json"

    def add_arguments(self, p):
        p.add_argument("--max-calls", type=int, default=380)

    def handle(self, *a, **o):
        lab = label.ampliar(latest()["signals"], o["max_calls"])
        v = [x for x in lab["labels"].values() if x.get("ext")]
        self.stdout.write(f"{len(v)} nuevas, acuerdo tema {sum(x['agree'] for x in v) / max(len(v), 1):.1%}")
