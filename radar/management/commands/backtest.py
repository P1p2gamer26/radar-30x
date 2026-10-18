"""Prueba hacia atrás del radar sobre el último snapshot; escribe data/backtest.json (sin red)."""
import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import backtest
from radar.build import etiquetar_todo
from radar.collect import latest
from radar import student
from radar.taxonomy import TOPICS, match_topics


class Command(BaseCommand):
    help = "Backtest: marcados 'empezando' con datos al día 7 vs lo que creció en los días 8-14"

    def add_arguments(self, p):
        p.add_argument("--rodante", action="store_true", help="protocolo rodante sobre data/historia/ -> data/backtest.json")
        p.add_argument("--descargar", action="store_true", help="con --rodante: baja la historia (HN, arXiv, Wikipedia) a data/historia/")
        p.add_argument("--desde", default="2026-06-26")
        p.add_argument("--hasta", default="2026-10-17")

    def handle(self, *a, **k):
        if k["rodante"]:
            return self.rodante(k)
        snap = latest()
        fin = datetime.fromisoformat(snap["collected_at"].replace("Z", "+00:00"))
        labs = etiquetar_todo(snap["signals"])
        topic_of = {sid: lab["topic"] for sid, lab in labs.items() if lab["topic"] in TOPICS}
        r = backtest.correr(snap["signals"], topic_of, list(TOPICS), fin)
        (settings.DATA_DIR / "backtest_corte_unico.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(json.dumps({x: r[x] for x in ("k", "base_azar", "radar", "popularidad")}, ensure_ascii=False))

    def rodante(self, k):
        from radar import historia, rodante
        if k["descargar"]:
            historia.guardar("wiki", historia.bajar_wiki(k["desde"], k["hasta"]))
            historia.guardar("hn", historia.bajar_hn(k["desde"], k["hasta"]))
            historia.guardar("arxiv", historia.bajar_arxiv(k["desde"], k["hasta"]))
            historia.guardar("meta", {"inicio": k["desde"], "fin": k["hasta"], "fuentes": ["hn", "arxiv", "wiki"]})
        h = historia.cargar()
        # estudiante de Python puro (costo 0, sin red ni embeddings); con poca confianza, keywords como en build.py
        modelo = student.cargar()
        topic_of = {}
        for s in h["signals"]:
            x = s["title"] + " " + s.get("text", "")
            t, conf = student.predecir(modelo, student.tokens(x, s["source"]), x)["topic"]
            kw = match_topics(x)
            t = kw[0] if conf < 0.4 and kw else t
            if t in TOPICS:
                topic_of[s["id"]] = t
        r = rodante.rodante(h["signals"], topic_of, list(TOPICS), h["wiki"], h["meta"]["inicio"], h["meta"]["fin"])
        (settings.DATA_DIR / "backtest.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(json.dumps({"n_cortes": r["n_cortes"], "base_azar": r["base_azar"], **r["resultados"]["regla_del_producto"]}, ensure_ascii=False))
