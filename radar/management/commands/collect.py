from collections import Counter

from django.core.management.base import BaseCommand

from radar.collect import run


class Command(BaseCommand):
    help = "Recolecta señales públicas y guarda data/snapshots/<fecha>.json"

    def handle(self, *args, **opts):
        snap = run()
        por_fuente = Counter(s["source"] for s in snap["signals"])
        self.stdout.write(f"{len(snap['signals'])} señales {dict(por_fuente)}; wiki: {len(snap['wiki'])} temas")
