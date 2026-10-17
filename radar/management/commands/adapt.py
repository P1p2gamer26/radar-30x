import json

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import label
from radar.views import cargar_radar


class Command(BaseCommand):
    help = "Genera con el LLM una idea de pieza para los 10 primeros temas -> data/adapt.json (luego build_radar)"

    def handle(self, *args, **opts):
        radar = cargar_radar()
        ruta = settings.DATA_DIR / "adapt.json"
        adapts = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        for t in radar["topics"][:10]:
            a = label.adaptar(t, radar.get("benchmark_30x", []))
            if a:
                adapts[t["slug"]] = a
                self.stdout.write(f"{t['slug']}: {a['title']}")
        ruta.write_text(json.dumps(adapts, ensure_ascii=False, indent=1), encoding="utf-8")
