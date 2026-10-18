"""Plan de la semana (exportable) y cifras del modelo. Una sola fuente: radar.json (temas) y student.json (métricas)."""
import csv
import io

CAMPOS = ["orden", "tema", "decision", "etapa", "por_que", "dia_sugerido", "responsable", "plataforma", "guion", "reel"]


def _pct(x) -> int:
    return round((x or 0) * 100)


def metricas(student_eval: dict) -> dict:
    """Cifras del tema (top-1, top-3, seguro + cobertura, contra todas, base) tal como salen de student.json -> eval."""
    t = (student_eval or {}).get("topic", {})
    o = t.get("offline") or t
    return {"top1": _pct(o.get("holdout_accuracy")), "top3": _pct(o.get("holdout_top3")), "seguro": _pct(o.get("safe_accuracy")),
            "cobertura": _pct(o.get("safe_coverage")), "todas": _pct(o.get("holdout_accuracy_all")),
            "base": _pct(o.get("holdout_baseline")), "n": t.get("n_holdout") or (student_eval or {}).get("n_holdout", 0),  # piezas del hold-out con consenso de tema
            "escaner_top1": _pct(t.get("holdout_accuracy")), "escaner_top3": _pct(t.get("holdout_top3"))}


def _guion(a) -> str:
    if not a:
        return ""
    return " | ".join([a["title"], "Gancho: " + a["hook"]] + a.get("beats", []) + ["CTA: " + a["cta"]])


def _reel(r) -> str:
    if not r:
        return ""
    return " | ".join(["Gancho: " + r["hook"]] + [f"{s['seg']} s: {s['visual']} (texto: {s['texto']})" for s in r["shots"]] + ["CTA: " + r["cta"]])


def filas(radar: dict) -> list:
    out = []
    for t in radar.get("topics", []):
        if t["decision"] not in ("Recomendar", "Aprender"):
            continue
        a, r = t.get("adapt"), t.get("adapt_reel")
        out.append({"orden": len(out) + 1, "tema": t["name"], "decision": t["decision"], "etapa": t.get("early_label", t["stage"]),
                    "por_que": t["reason"], "dia_sugerido": t["why"].get("best_day", ""), "responsable": "", "plataforma": (a or {}).get("platform", ""), "guion": _guion(a), "reel": _reel(r)})
    return out


def csv_texto(rows: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, CAMPOS)
    w.writeheader()
    for f in rows:  # los textos vienen de un LLM: neutraliza fórmulas de Excel/Sheets (=, +, -, @)
        w.writerow({k: ("'" + v if isinstance(v, str) and v and v[0] in "=+-@" else v) for k, v in f.items()})
    return "﻿" + buf.getvalue()


def texto_chat(radar: dict, rows: list) -> str:
    """Resumen corto para pegar en WhatsApp/Slack (*negrita* funciona en ambos)."""
    lineas = [f"*Plan de la semana {radar.get('week', '')} · EstelarIA*"]
    for f in rows:
        lineas.append(f"{f['orden']}. *{f['tema']}* ({f['decision']} · {f['etapa']}) en {f['plataforma'] or 'LinkedIn'}")
        lineas.append(f"   Por qué: {f['por_que']}")
    return "\n".join(lineas)
