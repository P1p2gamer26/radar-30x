from django.core.management.base import BaseCommand

from radar import label
from radar.collect import latest


class Command(BaseCommand):
    help = "Etiqueta una muestra de señales con el LLM profesor (data/labels.json)"

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=900)

    def handle(self, *args, n, **opts):
        lab = label.run(latest()["signals"], n=n, log=self.stdout.write)
        self.stdout.write(f"{len(lab['labels'])} etiquetas; meta={lab['meta']}")
