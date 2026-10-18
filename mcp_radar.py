"""Servidor MCP del radar EstelarIA: JSON-RPC 2.0 por stdio, solo stdlib. Uso: python mcp_radar.py"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TEXTO_MAX = 2000
_N = {"type": "integer", "minimum": 1, "maximum": 20, "default": 10, "description": "Cuántos temas devolver (máx. 20)"}
TOOLS = [
    {"name": "top_temas", "description": "Los temas de IA que más crecen esta semana, con etapa, decisión (Recomendar/Aprender/Descartar), razón y primera evidencia.",
     "inputSchema": {"type": "object", "properties": {"n": _N}}},
    {"name": "tema", "description": "Resumen completo de un tema del radar: por qué crece, cómo lo adapta 30X (guion/idea) y sus señales principales.",
     "inputSchema": {"type": "object", "properties": {"slug": {"type": "string", "description": "Slug del tema, p. ej. ia-marketing"}}, "required": ["slug"]}},
    {"name": "analizar", "description": "Clasifica el texto público de una pieza (tema, formato, gancho, encaje) y dice si conviene replicarla. Modo replay, sin red.",
     "inputSchema": {"type": "object", "properties": {"texto": {"type": "string", "description": "Texto de la pieza (máx. 2000 caracteres)"},
                                                      "plataforma": {"type": "string", "default": "Otro", "description": "LinkedIn, Instagram, TikTok u Otro"}}, "required": ["texto"]}},
]


class ParamsMalos(Exception):
    pass


def _topics():
    with open(os.path.join(AQUI, "data", "radar.json"), encoding="utf-8") as f:
        return json.load(f)["topics"]


def _resumen(t):
    ev = (t.get("top_signals") or [{}])[0]
    return {"slug": t["slug"], "name": t["name"], "stage": t["stage"], "decision": t["decision"], "reason": t["reason"],
            "growth": t["growth"], "exec_fit": t["exec_fit"], "evidencia": ev.get("url")}


def top_temas(a):
    n = a.get("n", 10)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ParamsMalos("n debe ser un entero >= 1")
    return [_resumen(t) for t in _topics()[:min(n, 20)]]


def tema(a):
    slug = a.get("slug")
    if not isinstance(slug, str) or not slug:
        raise ParamsMalos("slug es obligatorio")
    t = next((t for t in _topics() if t["slug"] == slug), None)
    if not t:
        raise ValueError(f"tema desconocido: {slug}")
    return {**_resumen(t), "why": t.get("why"), "adapt": t.get("adapt"),
            "top_signals": [{k: s.get(k) for k in ("title", "url", "source")} for s in t.get("top_signals", [])[:5]]}


def analizar(a):
    texto = a.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise ParamsMalos("texto es obligatorio")
    os.environ["DECISION_MODE"] = "replay"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, AQUI)
    import django
    django.setup()  # ponytail: perezoso, solo esta herramienta paga el arranque de Django
    from radar.analyze import analizar as _analizar
    return _analizar(texto[:TEXTO_MAX], str(a.get("plataforma") or "Otro"))


FUNCS = {"top_temas": top_temas, "tema": tema, "analizar": analizar}


def manejar(msg):
    """Devuelve la respuesta (dict) o None si es notificación."""
    m, p, i = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if i is None:
        return None
    ok = lambda r: {"jsonrpc": "2.0", "id": i, "result": r}
    err = lambda c, t: {"jsonrpc": "2.0", "id": i, "error": {"code": c, "message": t}}
    if m == "initialize":
        return ok({"protocolVersion": p.get("protocolVersion") or "2025-06-18", "capabilities": {"tools": {}},
                   "serverInfo": {"name": "estelaria-radar", "version": "1.0"}})
    if m == "ping":
        return ok({})
    if m == "tools/list":
        return ok({"tools": TOOLS})
    if m == "tools/call":
        f, args = FUNCS.get(p.get("name")), p.get("arguments") or {}
        if not f or not isinstance(args, dict):
            return err(-32602, "herramienta o argumentos inválidos")
        try:
            res, malo = f(args), False
        except ParamsMalos as e:
            return err(-32602, str(e))
        except Exception as e:  # error de la herramienta, no del protocolo
            res, malo = {"error": str(e)}, True
        return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": malo})
    return err(-32601, f"método desconocido: {m}")


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # Windows usa cp1252 por defecto
    for linea in sys.stdin:
        if not linea.strip():
            continue
        try:
            msg = json.loads(linea)
            resp = manejar(msg) if isinstance(msg, dict) else {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "solicitud inválida"}}
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        except Exception as e:
            print("error interno:", e, file=sys.stderr)
            resp = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": "error interno"}}
        if resp:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
