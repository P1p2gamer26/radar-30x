#!/usr/bin/env bash
# Verificador: tests + radar.json cumple el contrato + sin datos personales. Sin red (todo desde data/).
set -e
cd "$(dirname "$0")"
export DECISION_MODE=replay DJANGO_DEBUG=1
python -m pytest -q
python manage.py build_radar > /dev/null
python - <<'PY'
import json, re
r = json.load(open("data/radar.json", encoding="utf-8"))
assert len(r["topics"]) >= 10, "menos de 10 temas"
for t in r["topics"][:10]:
    for k in ("slug", "name", "stage", "decision", "reason", "why", "top_signals", "adapt", "series", "p"):
        assert k in t, f"{t.get('slug')}: falta {k}"
    assert t["decision"] in ("Recomendar", "Aprender", "Descartar")
    assert len(t["series"]) == 14 and t["top_signals"], f"{t['slug']}: sin serie o evidencia"
assert r["totals"]["signals"] > 0 and "cost_per_signal_usd" in r["totals"]
txt = open("data/radar.json", encoding="utf-8").read()
assert not re.search(r"[\w.+-]+@[\w-]+\.(com|co|net|org)\b", txt), "hay emails en radar.json"
bad = [u for u in re.findall(r'"url": "([^"]+)"', txt) if "/@" in u and "tiktok.com/@_" not in u]
assert not bad, f"urls con handle de terceros: {bad[:3]}"
print(f"verify OK: {r['totals']['signals']} señales, {len(r['topics'])} temas, top: {r['topics'][0]['name']}")
PY
