"""Verificación determinista de cifras en los guiones: cada cifra debe aparecer en las piezas reales del tema.
Sin LLM. Una cifra es: porcentaje, dinero, múltiplo (3x), cantidad con unidad (10 mil, 225 días) o año."""
import re

NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
ESCALA = {"mil millones": 1e9, "millones": 1e6, "millón": 1e6, "mil": 1e3, "mm": 1e6, "m": 1e6, "k": 1e3,
          "million": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "thousand": 1e3}
UNIDADES = "modelos|días|dias|usuarios|empresas|startups|países|paises|personas|clientes|empleados"
FEM = {"empresas", "startups", "personas"}
CLAIM = re.compile(
    rf"(?P<din>(?:US\$|USD|COP|\$)\s?(?:{NUM})(?:\s?(?:mil millones|millones|mil|MM|M|k|K)\b)?)"
    rf"|(?P<din2>(?:{NUM})(?:\s?(?:mil millones|millones|mil))?\s+(?:de\s+)?(?:d[óo]lares|USD|pesos|euros)\b)"
    rf"|(?P<pct>(?:{NUM})\s?%)"
    rf"|(?P<mult>(?<![\w.,])(?:{NUM})\s?(?:x|veces)\b)"
    rf"|(?P<esc>(?:{NUM})\s?(?:mil millones|millones|mil)\b)"
    rf"|(?P<cta>(?<![\w.,])(?:{NUM})\s+(?:{UNIDADES})\b)"
    rf"|(?P<anio>(?<![\w.,])(?:19|20)\d\d\b)", re.I)
EJEMPLO = re.compile(r"por ejemplo|ejemplo|imagina|supón|supon|digamos|supongamos|equipo de \d", re.I)
FRASES = re.compile(r"(?<=[a-záéíóúñ0-9%)'\"”][.!?])\s+(?=[¿¡A-ZÁÉÍÓÚÑ\"'“])")
MINS = {"beats": 3, "secciones": 4, "puntos": 1, "slides": 5, "argumentos": 3}  # mínimos que exige validar_guiones


def _valor(txt: str, extra: str = "") -> list:
    """'25,9' -> [25.9]; '3.000' -> [3000] (o 3.0 si es evidencia en inglés); aplica la escala (mil, M, k...)."""
    t = txt.strip()
    esc = ESCALA.get(extra.strip().lower(), 1)
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t):
        vs = [float(re.sub(r"[.,]", "", t))]
        if len(re.findall(r"[.,]", t)) == 1:
            vs.append(float(t.replace(",", ".")))
    elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+[.,]\d+", t):
        vs = [float(re.sub(r"[.,](?=\d{3}\b)", "", t).replace(",", "."))]
    else:
        vs = [float(t.replace(",", "."))]
    return [round(v * esc, 6) for v in vs]


_EV = re.compile(rf"(?P<n>{NUM})\s?(?P<e>mil millones|millones|millón|million|billion|thousand|mil|bn|MM|M|k|B)?(?![a-zñáéíóú])(?P<p>\s?%|\s?(?:percent|por ciento))?", re.I)


def _evidencia(textos: list) -> tuple:
    """Todos los números del corpus: (valores sueltos/escalados, valores que van con %)."""
    vals, pcts = set(), set()
    for m in _EV.finditer(" ".join(textos)):
        e = m.group("e") or ""
        for v in _valor(m.group("n"), e):
            vals.add(v)
            if m.group("p"):
                pcts.add(v)
        if e:  # '$24k' también cuenta como 24 sin escala
            vals.update(_valor(m.group("n")))
    return vals, pcts


def _parse(m) -> tuple:
    """(tipo, valores) de un match de CLAIM."""
    tipo, txt = m.lastgroup, m.group(0)
    num = re.search(NUM, txt)
    esc = re.search(r"(mil millones|millones|mil|MM|M|k)\b", txt[num.end():], re.I) if num and tipo in ("din", "din2", "esc") else None
    return tipo, _valor(num.group(0), esc.group(1) if esc else "")


def _estado(m, frase: str, ev: tuple, forzado: bool) -> str:
    tipo, vs = _parse(m)
    vals, pcts = ev
    if any(v in (pcts if tipo == "pct" else vals) for v in vs):
        return "verificada"
    # ponytail: "210 mil" respalda a 210.364 (redondeo de hasta 1 %) cuando la cifra viene con escala
    if tipo in ("din", "din2", "esc") and re.search(r"mil|millon|\d\s?(?:M|MM|k)", m.group(0), re.I)             and any(abs(e - v) <= 0.01 * v for v in vs for e in vals):
        return "verificada"
    # ponytail: un % o un 3x inventado nunca es "ejemplo"; solo cuentas/dinero/personas en frases de ejemplo
    if (forzado or EJEMPLO.search(frase)) and tipo in ("din", "din2", "cta", "esc"):
        return "ejemplo"
    return "sin_respaldo"


def _frases(txt: str) -> list:
    return FRASES.split(txt)


def _claims(txt: str, ev: tuple, forzado: bool = False) -> list:
    out = []
    for f in _frases(txt):
        for m in CLAIM.finditer(f):
            out.append({"texto": m.group(0).strip(), "estado": _estado(m, f, ev, forzado), "frase": f})
    return out


def _hojas(x, key="", forzado=False):
    if isinstance(x, str):
        yield key, x, forzado
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("verificacion", "duration"):
                yield from _hojas(v, k, forzado or k == "ejemplo")
    elif isinstance(x, list):
        for v in x:
            yield from _hojas(v, key, forzado)


def verificar_guion(guion: dict, evidencia: list) -> dict:
    ev = _evidencia(evidencia)
    vistas, res = set(), {"cifras": 0, "verificadas": 0, "sin_respaldo": [], "ejemplos": []}
    for _, txt, forz in _hojas(guion):
        for c in _claims(txt, ev, forz):
            k = (c["estado"], re.sub(r"\s", "", c["texto"].lower()))
            if k in vistas:
                continue
            vistas.add(k)
            if c["estado"] == "ejemplo":
                res["ejemplos"].append(c["texto"])
                continue
            res["cifras"] += 1
            if c["estado"] == "verificada":
                res["verificadas"] += 1
            else:
                res["sin_respaldo"].append(c["texto"])
    return res


class _Vacio(Exception):
    pass


def _sin_cifra(frase: str, ev: tuple, forzado: bool) -> str:
    """Reescribe la frase quitando solo las cifras sin respaldo (sustitución genérica)."""
    for m in reversed([m for m in CLAIM.finditer(frase) if _estado(m, frase, ev, forzado) == "sin_respaldo"]):
        t, txt = m.lastgroup, m.group(0)
        if t == "pct":
            nuevo = "una parte importante" if re.match(r"\s+de\b", frase[m.end():]) else ""
            ini = re.search(r"(?:(?:solo|apenas|casi|más de)\s+)?(?:el\s+)?$", frase[:m.start()], re.I).start()
        elif t in ("din", "din2", "esc"):
            nuevo, ini = "una cifra considerable", m.start()
        elif t == "mult":
            nuevo, ini = "varias veces", m.start()
        elif t == "cta":
            u = txt.split()[-1].lower()
            nuevo, ini = ("varias " if u in FEM else "varios ") + u, m.start()
        else:  # año
            nuevo, ini = "", re.search(r"(?:\ben\s+)?$", frase[:m.start()]).start()
        frase = frase[:ini] + nuevo + frase[m.end():]
    return re.sub(r"\s{2,}", " ", frase).strip()


def limpiar_guion(guion: dict, evidencia: list) -> tuple:
    """Quita las cifras sin respaldo: primero la frase, luego el beat/argumento entero, si no queda otra se reescribe.
    Devuelve (guion_limpio, acciones)."""
    ev, reg = _evidencia(evidencia), []

    def malo(x):
        return any(c["estado"] == "sin_respaldo" for _, t, f in _hojas(x) for c in _claims(t, ev, f))

    def rec(x, key="", forz=False, sub=False):
        if isinstance(x, str):
            fs = _frases(x)
            if not malo(x):
                return x
            buenas = [f for f in fs if not any(c["estado"] == "sin_respaldo" for c in _claims(f, ev, forz))]
            if buenas:
                reg.append({"accion": "frase quitada", "antes": x[:90]})
                return " ".join(buenas)
            if not sub:
                raise _Vacio
            reg.append({"accion": "cifra reescrita", "antes": x[:90]})
            return " ".join(_sin_cifra(f, ev, forz) for f in fs)
        if isinstance(x, dict):
            return {k: (v if k in ("verificacion", "duration") else rec(v, k, forz or k == "ejemplo", sub)) for k, v in x.items()}
        if isinstance(x, list):
            salida, quitables = [], len(x) - MINS.get(key, 0)
            for it in x:
                n = len(reg)
                try:
                    salida.append(rec(it, key, forz, False))
                except _Vacio:
                    del reg[n:]
                    if quitables > 0:
                        quitables -= 1
                        reg.append({"accion": "elemento quitado", "antes": str(it)[:90]})
                    else:
                        salida.append(rec(it, key, forz, True))
            return salida
        return x

    return rec(guion, sub=True), reg
