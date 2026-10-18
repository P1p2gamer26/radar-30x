"""Servidor MCP por stdio (sin red): initialize, tools/list, top_temas, tema, método desconocido y analizar."""
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _llamar(*msgs):
    entrada = "".join(json.dumps({"jsonrpc": "2.0", **m}) + "\n" for m in msgs)
    env = {**os.environ, "DECISION_MODE": "replay"}
    p = subprocess.run([sys.executable, "mcp_radar.py"], input=entrada, capture_output=True, text=True, encoding="utf-8", cwd=RAIZ, env=env, timeout=60)
    return {r["id"]: r for r in map(json.loads, p.stdout.splitlines())}


def _datos(r):
    assert not r["result"]["isError"]
    return json.loads(r["result"]["content"][0]["text"])


def test_mcp_flujo():
    top = _llamar({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                  {"method": "notifications/initialized"},
                  {"id": 2, "method": "tools/list"},
                  {"id": 3, "method": "tools/call", "params": {"name": "top_temas", "arguments": {"n": 3}}},
                  {"id": 5, "method": "nada/raro"})
    assert top[1]["result"]["serverInfo"]["name"] == "estelaria-radar" and len(top) == 4  # la notificación no responde
    assert len(top[2]["result"]["tools"]) == 3
    temas = _datos(top[3])
    assert len(temas) == 3 and all(t["slug"] and t["decision"] for t in temas)
    assert top[5]["error"]["code"] == -32601
    t = _datos(_llamar({"id": 1, "method": "tools/call", "params": {"name": "tema", "arguments": {"slug": temas[0]["slug"]}}})[1])
    assert t["slug"] == temas[0]["slug"] and t["adapt"] and len(t["top_signals"]) <= 5
    malo = _llamar({"id": 1, "method": "tools/call", "params": {"name": "tema", "arguments": {"slug": "no-existe"}}})[1]
    assert malo["result"]["isError"] is True


def test_mcp_analizar():
    r = _llamar({"id": 1, "method": "tools/call", "params": {"name": "analizar", "arguments": {"texto": "Cómo usar ChatGPT para hacer informes de ventas en 5 minutos"}}})[1]
    d = _datos(r)
    assert d["decision"] and d["topic"]
