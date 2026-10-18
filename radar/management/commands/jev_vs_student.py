"""Mide un System One abierto (Von, mismo contrato que Jev) en el MISMO hold-out de tema -> data/jev_abierto_vs_student.json.

Reusa llm_vs_student: mismo hold-out, estudiante y respuestas de DeepSeek ya guardadas en data/llm_vs_student.json.
Requiere el servidor corriendo (`von serve --port 8801`) y SYSTEMONE_URL apuntando a él.
"""
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from radar import label
from radar.collect import latest
from radar.management.commands.llm_vs_student import cascada, holdout_tema
from radar.taxonomy import TOPICS

INSTR = {"en": "Which topic is this post mainly about?",
         "es": "¿De qué tema trata principalmente esta publicación?"}
OTRO = {"en": "Not about AI, or fits none of the other topics", "es": "No es de IA o no encaja en ningún otro tema"}


def pregunta(idioma: str) -> dict:
    """Choice con los 20 temas: nombre + palabras clave como descripción (contrato System One/Jev)."""
    crit = {k: f"{v['name']}: {', '.join(v['keywords'][:6])}" for k, v in TOPICS.items() if k != "otro"}
    crit["otro"] = OTRO[idioma]
    return {"topic": {"type": "choice", "instructions": INSTR[idioma], "criteria": crit}}


def estado(s: dict) -> str:
    return (label._sanitizar(s["title"])[:200] + ". " + label._sanitizar(s.get("text", ""))[:300]).strip()


def preguntar(url: str, texto: str, q: dict, clave: str = "") -> dict:
    import urllib.request
    h = {"Content-Type": "application/json"}
    if clave:
        h["Authorization"] = f"Bearer {clave}"
    req = urllib.request.Request(url, json.dumps({"state": texto, "questions": q}).encode(), h)
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["answers"]["topic"]


def cascada3(items: list, tau: float, tau2: float) -> dict:
    """estudiante (si conf >= tau) -> modelo abierto (si prob >= tau2) -> DeepSeek."""
    n = len(items)
    ok = c_est = c_abierto = c_llm = 0
    for x in items:
        if x["student_conf"] >= tau:
            r, c_est = x["student"], c_est + 1
        elif x["abierto_p"] >= tau2:
            r, c_abierto = x["abierto"], c_abierto + 1
        else:
            r, c_llm = x["llm"], c_llm + 1
        ok += r == x["gold"]
    return {"tau": tau, "tau2": tau2, "top1": round(ok / n, 3), "estudiante": c_est, "abierto": c_abierto, "deepseek": c_llm}


class Command(BaseCommand):
    help = "Mide el System One abierto (Von) en el hold-out de tema -> data/jev_abierto_vs_student.json"

    def add_arguments(self, parser):
        parser.add_argument("--idioma", choices=["en", "es"], default="en")
        parser.add_argument("--modelo", default="von-1.3")
        parser.add_argument("--max", type=int, default=0, help="solo las primeras N piezas (subconjunto)")

    def handle(self, *args, **opts):
        url = settings.SYSTEMONE_URL
        assert url, "define SYSTEMONE_URL (p. ej. http://127.0.0.1:8801/v1/systemone)"
        viejo = json.loads((settings.DATA_DIR / "llm_vs_student.json").read_text(encoding="utf-8"))
        guard = {x["id"]: x for x in viejo["items"]}
        pares = holdout_tema(latest()["signals"], label.cargar()["labels"])
        assert {s["id"] for s, _ in pares} <= set(guard), "el hold-out cambió; corre llm_vs_student"
        tau = json.loads((settings.DATA_DIR / "radar.json").read_text(encoding="utf-8"))["student"]["topic"]["offline"]["tau"]
        pares = pares[:opts["max"]] if opts["max"] else pares
        q = pregunta(opts["idioma"])
        items, t0 = [], time.perf_counter()
        for s, gold in pares:
            r = preguntar(url, estado(s), q)
            items.append({**guard[s["id"]], "abierto": r["choice"], "abierto_p": round(r["probabilities"][r["choice"]], 4),
                          "abierto_probs": {k: round(v, 3) for k, v in sorted(r["probabilities"].items(), key=lambda kv: -kv[1])[:3]}})
        seg = (time.perf_counter() - t0) / len(items)
        n = len(items)
        top1 = lambda k: round(sum(x[k] == x["gold"] for x in items) / n, 3)  # noqa: E731
        top3 = round(sum(x["gold"] in x["abierto_probs"] for x in items) / n, 3)
        out = {"modelo": opts["modelo"], "idioma_pregunta": opts["idioma"], "n": n, "fecha": time.strftime("%Y-%m-%d"),
               "abierto_top1": top1("abierto"), "abierto_top3": top3, "abierto_seconds_per_item": round(seg, 2),
               "student_top1": top1("student"), "deepseek_top1": top1("llm"),
               "cascada_estudiante_abierto": cascada([{**x, "llm": x["abierto"]} for x in items], tau),
               "cascada_estudiante_abierto_deepseek": cascada3(items, tau, tau),
               # ponytail: barrido de tau2 sobre el mismo hold-out = optimista; el titular usa tau2 = tau (a priori)
               "barrido_tau2_optimista": [cascada3(items, tau, t2) for t2 in (0.3, 0.4, 0.5, 0.6, 0.7)],
               "solo_abierto_calibracion": {"conf_media": round(sum(x["abierto_p"] for x in items) / n, 3)},
               "items": items}
        (settings.DATA_DIR / f"jev_abierto_vs_student{'' if opts['idioma'] == 'en' else '_es'}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(json.dumps({k: v for k, v in out.items() if k != "items"}, ensure_ascii=False, indent=1))
