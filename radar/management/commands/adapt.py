import json

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import label
from radar.views import cargar_radar


class Command(BaseCommand):
    help = ("Genera con el LLM el guion (LinkedIn/YouTube) de cada tema y el reel (IG/TikTok) de los Recomendar/Aprender "
            "-> data/adapt.json (luego build_radar). Por defecto solo completa lo que falta.")

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="todos los temas (si no, solo los 10 primeros)")
        parser.add_argument("--guiones", action="store_true", help="solo los 4 tipos de guion (reel/largo/linkedin/recomendacion)")
        parser.add_argument("--force", action="store_true", help="regenerar aunque ya exista")

    def handle(self, *args, **opts):
        radar = cargar_radar()
        ruta = settings.DATA_DIR / "adapt.json"
        adapts = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        bench = radar.get("benchmark_30x", [])
        for t in radar["topics"] if opts["all"] else radar["topics"][:10]:
            a = adapts.get(t["slug"])
            if opts["guiones"]:
                if a and (opts["force"] or len(a.get("guiones", {}).keys() & set(label.TIPOS_GUION)) < 4):
                    a["guiones"] = label.guiones(t, bench) or a.get("guiones")
                    self.stdout.write(f"{t['slug']}: guiones {sorted((a.get('guiones') or {}).keys() & set(label.TIPOS_GUION))}")
                    ruta.write_text(json.dumps(adapts, ensure_ascii=False, indent=1), encoding="utf-8")
                continue
            if opts["force"] or not a:
                a = label.adaptar(t, bench)
            if a and (opts["force"] or not a.get("adapt_reel")):  # reel de los 20 temas: el escáner lo necesita para IG/TikTok
                a["adapt_reel"] = label.adaptar_reel(t, bench) or a.get("adapt_reel")
            if a:
                adapts[t["slug"]] = a
                self.stdout.write(f"{t['slug']}: {a['title']} | reel: {'si' if a.get('adapt_reel') else 'no'}")
            else:
                self.stdout.write(f"{t['slug']}: sin guion (LLM falló)")
            ruta.write_text(json.dumps(adapts, ensure_ascii=False, indent=1), encoding="utf-8")
