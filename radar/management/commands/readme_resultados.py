"""Reescribe el bloque <!-- RESULTADOS --> del README desde data/radar.json y data/student.json (una sola fuente de cifras)."""
import json
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import plan


def _n(x) -> str:
    return f"{x:,}".replace(",", ".")


def bloque(radar: dict, ev: dict) -> str:
    c = {d: [t for t in radar["topics"] if t["decision"] == d] for d in ("Recomendar", "Aprender", "Descartar")}
    tot = radar["totals"]
    fuentes = ", ".join(f"{s['label']} {_n(s['signals'])}" for s in sorted(radar["sources"], key=lambda s: -s["signals"]))
    m = plan.metricas(ev)
    L = [f"Corrida {radar['week']} (generada {radar['generated_at'][:10]}; datos en `data/`, reproducible sin red). Generado por `python manage.py readme_resultados`.", "",
         f"- **Señales:** {_n(tot['signals'])} ({fuentes}).",
         f"- **Temas:** {len(radar['topics'])} analizados; {len(c['Recomendar'])} Recomendar ({', '.join(t['name'] for t in c['Recomendar']) or 'ninguno'}), "
         f"{len(c['Aprender'])} Aprender, {len(c['Descartar'])} Descartar.",
         f"- **Costo:** USD {tot.get('weekly_cost_usd', 0):.2f} por semana (scraping de Instagram/TikTok vía Apify) y USD {tot['teacher_cost_usd']:.2f} una sola vez por etiquetar "
         f"{_n(tot['labeled'])} señales con el LLM (USD {tot['cost_per_signal_usd']} por señal); el estudiante clasifica a USD {tot['student_cost_usd']:.2f}.",
         f"- **Modelo propio, tema** (hold-out fijo del 20 %, {m['n']} piezas con consenso de tema): top-1 **{m['top1']} %**, top-3 {m['top3']} %, "
         f"cuando está seguro acierta {m['seguro']} % y cubre el {m['cobertura']} % de las piezas; contra todas las etiquetas (incluidas las dudosas) {m['todas']} %; adivinar da {m['base']} %.",
         "", "| Tarea | Top-1 | Top-3 | Cuando está seguro (cobertura) | Contra todas | Base |", "|---|---|---|---|---|---|"]
    for k, nombre in (("topic", "Tema"), ("format", "Formato"), ("hook", "Gancho")):
        o = ev[k].get("offline") or ev[k]
        seg = f"{round(o['safe_accuracy'] * 100)} % ({round(o['safe_coverage'] * 100)} %)" if o.get("safe_accuracy") else "no llega a 90 %"
        L.append(f"| {nombre} (radar, offline) | {round(o['holdout_accuracy'] * 100)} % | {round(o['holdout_top3'] * 100)} % | {seg} | "
                 f"{round(o['holdout_accuracy_all'] * 100)} % | {round(o['holdout_baseline'] * 100)} % |")
    t = ev["topic"]
    L.append(f"| Tema (escáner, servidor) | {m['escaner_top1']} % | {m['escaner_top3']} % | {round(t['safe_accuracy'] * 100)} % ({round(t['safe_coverage'] * 100)} %) | "
             f"{round(t['holdout_accuracy_all'] * 100)} % | {round(t['holdout_baseline'] * 100)} % |")
    return "\n".join(L)


class Command(BaseCommand):
    help = "Regenera la sección Resultados del README"

    def handle(self, *a, **k):
        radar = json.loads((settings.DATA_DIR / "radar.json").read_text(encoding="utf-8"))
        ev = json.loads((settings.DATA_DIR / "student.json").read_text(encoding="utf-8"))["eval"]
        ruta = settings.BASE_DIR / "README.md"
        txt = ruta.read_text(encoding="utf-8")
        nuevo = re.sub(r"(<!-- RESULTADOS -->).*?(<!-- /RESULTADOS -->)", lambda mo: f"{mo.group(1)}\n{bloque(radar, ev)}\n{mo.group(2)}", txt, flags=re.S)
        ruta.write_text(nuevo, encoding="utf-8")
        self.stdout.write("README actualizado" if nuevo != txt else "README sin cambios")
