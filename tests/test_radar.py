import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar import analyze, build, sources, student, trend
from radar.taxonomy import match_topics

FIX = Path(__file__).parent / "fixtures"
AHORA = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def test_match_topics_sin_tildes_y_palabra_completa():
    assert "agentes-ia" in match_topics("Los AGENTES DE IA llegan a la empresa")
    assert match_topics("regulación europea: AI Act")[0] == "regulacion-etica"
    assert "infra-costos" not in match_topics("tokenization")  # 'tokens' no matchea dentro de otra palabra


def test_hn_dedup_y_metricas(monkeypatch):
    monkeypatch.setattr(sources, "HN_QUERIES", ["AI"])
    monkeypatch.setattr(sources, "get", lambda url: (FIX / "hn.json").read_bytes() if "page=0" in url else b'{"hits": []}')
    out = sources.fetch_hn(AHORA)
    assert len(out) == 2
    assert out[0]["metrics"] == {"points": 120, "comments": 40, "views": 0}
    assert out[1]["url"].startswith("https://news.ycombinator.com/item?id=2")


def test_gnews_quita_medio_y_salta_fechas_malas(monkeypatch):
    monkeypatch.setattr(sources, "TOPICS", {"agentes-ia": {"keywords": ["agentes de ia", "ai agents"]}})
    monkeypatch.setattr(sources, "GNEWS_LOCALES", [("es", "hl=es-419")])
    monkeypatch.setattr(sources, "get", lambda url: (FIX / "gnews.xml").read_bytes())
    out = sources.fetch_gnews(AHORA)
    assert [s["title"] for s in out] == ["Empresas de Colombia adoptan agentes de IA"]
    assert out[0]["author_type"] == "medio"


def test_linkedin_limpia_titulo_y_autor(monkeypatch):
    monkeypatch.setattr(sources, "TOPICS", {"agentes-ia": {"keywords": ["agentes de ia", "ai agents"]}})
    monkeypatch.setattr(sources, "GNEWS_LOCALES", [("es", "hl=es-419")])
    monkeypatch.setattr(sources, "PAUSA_LINKEDIN", 0)
    monkeypatch.setattr(sources, "get", lambda url: (FIX / "linkedin.xml").read_bytes())
    out = sources.fetch_linkedin(AHORA)
    assert [s["title"] for s in out] == ["Cómo usar agentes de IA en ventas", "IA y productividad"]
    assert out[0]["source"] == "linkedin" and out[0]["author_type"] == "creador"


def test_youtube_trae_vistas():
    out = sources.parse_youtube((FIX / "youtube.xml").read_bytes(), {"name": "30X", "lang": "es", "author_type": "empresa"})
    assert out[0]["metrics"]["views"] == 25473 and out[0]["metrics"]["points"] == 900
    assert out[0]["url"] == "https://www.youtube.com/watch?v=abc"


def test_red_caida_no_rompe(monkeypatch):
    def falla(url):
        raise OSError("sin red")
    monkeypatch.setattr(sources, "get", falla)
    assert sources.fetch_hn(AHORA) == []


def test_trend_detecta_temprana():
    sube = [1.0] * 11 + [3.0, 4.0, 5.0]
    assert trend.growth(sube) > 2.5 and trend.robust_z(sube) > 2
    assert trend.etapa(trend.growth(sube), trend.robust_z(sube), trend.aceleracion(sube), 5, 10, 20) == "temprana"
    assert trend.etapa(0.5, 0, 0, 5, 10, 20) == "bajando"


def test_student_aprende():
    ej = [(student.tokens("AI agents automate sales outreach"), {"topic": "ia-ventas", "format": "a", "hook": "b", "fit": "alto"}),
          (student.tokens("Nvidia GPU chips data center"), {"topic": "infra-costos", "format": "c", "hook": "d", "fit": "bajo"})]
    m = student.entrenar(ej, min_df=1)
    assert student.predecir(m, student.tokens("sales agents"))["topic"][0] == "ia-ventas"


def _snap():
    signals = []
    for d in range(14):
        n = 6 if d >= 11 else 1  # agentes-ia se dispara los últimos 3 días
        for i in range(n):
            signals.append({"id": f"hn:{d}-{i}", "source": "hn", "url": f"https://x/{d}/{i}", "title": "AI agents for sales teams",
                            "text": "", "lang": "en", "published_at": f"2026-10-{4 + d:02d}T10:00:00Z", "author_type": "comunidad",
                            "metrics": {"points": 10, "comments": 2, "views": 0}, "query": "AI"})
        signals.append({"id": f"gn:{d}", "source": "gnews", "url": f"https://g/{d}", "title": "Nvidia GPU chips", "text": "",
                        "lang": "en", "published_at": f"2026-10-{4 + d:02d}T10:00:00Z", "author_type": "medio",
                        "metrics": {"points": 0, "comments": 0, "views": 0}, "query": "infra-costos"})
    return {"collected_at": "2026-10-17T20:00:00Z", "signals": signals, "wiki": {}}


@pytest.fixture
def datos(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    return tmp_path


def test_build_contrato(datos):
    r = build.build(_snap())
    assert len(r["topics"]) == 20 and r["topics"][0]["rank"] == 1
    t = next(x for x in r["topics"] if x["slug"] == "agentes-ia")
    assert t["growth"] > 1.2 and len(t["series"]) == 14
    for clave in ("stage", "decision", "reason", "why", "top_signals", "adapt", "momentum", "exec_fit", "p"):
        assert clave in t
    assert t["decision"] in ("Recomendar", "Aprender", "Descartar")
    assert json.loads((datos / "radar.json").read_text(encoding="utf-8"))["week"] == "2026-W42"


def test_analizar_quita_pii_y_no_falla_sin_modelo(datos, settings, db):
    settings.DECISION_MODE = "replay"
    assert "[email]" in analyze.limpiar("escríbeme a ana@x.com") and "@ana" not in analyze.limpiar("hola @ana")
    r = analyze.analizar("Así automatizamos ventas con agentes de IA y ahorramos 30 horas")
    assert r["topic"] in ("agentes-ia", "ia-ventas", "automatizacion") and r["decision"] in ("Recomendar", "Aprender", "Descartar")


def test_api_radar(client, datos):
    (datos / "radar.json").write_text('{"topics": [], "week": "x"}', encoding="utf-8")
    assert client.get("/api/radar.json").json()["week"] == "x"


def test_analizar_limite_por_ip_y_replay_sin_llm(client, datos, settings, monkeypatch, db):
    from django.core.cache import cache
    cache.clear()
    settings.DECISION_MODE = "replay"
    monkeypatch.setattr(analyze, "decide", lambda *a, **k: pytest.fail("replay no debe llamar al LLM"))
    for _ in range(20):
        assert client.post("/analizar/", {"texto": "agentes de ia en ventas"}).status_code == 200
    r = client.post("/analizar/", {"texto": "agentes de ia en ventas"})
    assert r.status_code == 429
    cache.clear()


def test_apify_mapea_y_no_guarda_handles_de_terceros():
    ig = sources.parse_instagram(json.loads((FIX / "apify_instagram.json").read_text(encoding="utf-8")), "perfil-30x")
    tt = sources.parse_tiktok(json.loads((FIX / "apify_tiktok.json").read_text(encoding="utf-8")), "ia")
    assert ig[0]["id"] == "instagram:AAA111" and ig[0]["channel"] == "crece30x" and ig[0]["author_type"] == "empresa"
    assert ig[0]["format"] == "carrusel" and ig[0]["title"] == "5 agentes de IA para tu empresa"
    assert ig[1]["format"] == "reel" and ig[1]["metrics"] == {"points": 10, "comments": 1, "views": 900} and "channel" not in ig[1]
    assert tt[0]["metrics"]["views"] == 2072 and "channel" not in tt[0] and tt[1]["channel"] == "andresbilbao"
    assert tt[1]["author_type"] == "creador"
    txt = json.dumps(ig + tt)
    assert "tercero" not in txt and "otro_usuario" not in txt and "juan@x.com" not in txt


def test_apify_sin_token_devuelve_vacio(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert sources.fetch_instagram(AHORA) == [] and sources.fetch_tiktok(AHORA) == []


def test_escaner_devuelve_tema_decision_adapt_y_similares(client, settings, db):
    from django.core.cache import cache
    cache.clear()
    settings.DECISION_MODE = "replay"  # usa data/ real: radar.json + student.json
    r = client.post("/analizar/", {"texto": "Así usamos agentes de IA para vender más y calificar prospectos en ventas", "plataforma": "LinkedIn"})
    assert r.status_code == 200
    res = r.context["resultado"]
    assert res["topic"] and res["decision"] in ("Recomendar", "Aprender", "Descartar") and res["claves"]
    assert res["adapt"] and len(res["similares"]) == 3 and res["benchmark"]
    html = r.content.decode()
    assert "Copiar guion" in html and "Ver el tema en el radar" in html and "Escanear" in html
    cache.clear()


# ------------------------------------------------------------------ ronda 3

CASOS_ESCANER = [
    ("Mi equipo de ventas cerró 30% más con un agente de IA, paso a paso", {"ia-ventas", "agentes-ia"}),
    ("Cómo usé ChatGPT para redactar mis contratos y ahorré 10 horas", {"copilotos", "automatizacion"}),
    ("OpenAI lanza un nuevo modelo, esto cambia todo", {"modelos-nuevos"}),
    ("Cómo formar a tu equipo en IA sin ser programador", {"educacion-ia"}),
]


@pytest.mark.parametrize("texto,temas", CASOS_ESCANER)
def test_escaner_acierta_el_tema(texto, temas, settings, db):
    settings.DECISION_MODE = "replay"  # data/ real, sin LLM
    assert analyze.analizar(texto)["topic"] in temas


def test_escaner_paso_a_paso_y_confianza_baja(client, settings, db):
    from django.core.cache import cache
    cache.clear()
    settings.DECISION_MODE = "replay"
    r = client.post("/analizar/", {"texto": CASOS_ESCANER[0][0], "plataforma": "Instagram"})
    res = r.context["resultado"]
    assert res["format"] == "caso-paso-a-paso"
    assert res["baja_confianza"] == (res["engine"] == "regla" or res["confidence"] < 0.5)
    if res["baja_confianza"]:
        assert "Confianza baja: revisa antes de producir" in r.content.decode()
    cache.clear()


def test_decision_honesta():
    assert build.decision(0.95, "estable") == "Aprender"  # estable no es temprano
    assert build.decision(0.95, "saturada") == "Aprender"
    assert build.decision(0.95, "bajando") == "Descartar"
    assert build.decision(0.95, "temprana") == build.decision(0.95, "creciendo") == "Recomendar"
    assert build.decision(0.1, "temprana") == "Descartar"


def test_student_ensamble_y_usable():
    ev = student.cargar()["eval"]
    for tarea in student.TAREAS:
        e = ev[tarea]
        assert {"accuracy", "baseline", "nb", "knn", "ensemble", "usable"} <= set(e)
        assert e["usable"] == (e["accuracy"] - e["baseline"] >= student.MARGEN_USABLE - 1e-9)
    assert ev["topic"]["accuracy"] > ev["topic"]["baseline"] + 0.2


def test_terceros_sin_texto():
    ig = sources.parse_instagram(json.loads((FIX / "apify_instagram.json").read_text(encoding="utf-8")), "perfil-30x")
    assert ig[0]["text"] and ig[1]["text"] == ""  # oficial conserva texto saneado, tercero no
    yt = sources.parse_youtube((FIX / "youtube.xml").read_bytes(), {"name": "X", "lang": "es"})
    assert all(s["text"] == "" for s in yt)


def test_radar_json_sin_handles_de_terceros():
    import re
    txt = (Path(__file__).parent.parent / "data" / "radar.json").read_text(encoding="utf-8")
    urls = re.findall(r'"url": "([^"]+)"', txt)
    assert urls and not [u for u in urls if "/@" in u and "tiktok.com/@_" not in u]


def test_build_guiones_sin_plantilla(datos):
    (datos / "adapt.json").write_text(json.dumps({"agentes-ia": {"title": "t", "hook": "h", "format": "opinion", "beats": ["a", "b", "c"],
                                                                  "cta": "c", "platform": "LinkedIn", "adapt_reel": {"hook": "x"}}}), encoding="utf-8")
    r = build.build(_snap())
    t = {x["slug"]: x for x in r["topics"]}
    assert t["agentes-ia"]["adapt"]["title"] == "t" and t["agentes-ia"]["adapt_reel"] == {"hook": "x"}
    assert t["ia-ventas"]["adapt"] is None and t["ia-ventas"]["adapt_reel"] is None  # sin plantilla genérica
    assert t["agentes-ia"]["early_label"] in ("Temprano", "Despegando", "Estable", "Pico/saturado", "Cayendo")


# ------------------------------------------------------------------ ronda 5: escáner coherente

def test_escaner_coherente_con_la_audiencia(settings, db):
    settings.DECISION_MODE = "replay"
    empanadas = analyze.analizar("Receta de empanadas colombianas para el domingo")
    assert empanadas["decision"] == "Descartar"
    pov = analyze.analizar("POV: hiciste el informe semanal en 5 minutos con ChatGPT")
    assert pov["topic"] == "copilotos" and pov["decision"] in ("Aprender", "Recomendar")
    li = analyze.analizar("Agentes de IA en ventas: cómo un equipo comercial calificó prospectos en LinkedIn")
    assert li["topic"] in ("ia-ventas", "agentes-ia")
    tema = next(t for t in json.load(open(settings.DATA_DIR / "radar.json", encoding="utf-8"))["topics"] if t["slug"] == li["topic"])
    assert li["decision"] != "Descartar" or tema["decision"] == "Descartar"  # la pieza sigue al radar de la semana


def test_decision_pieza_reglas():
    t = {"decision": "Recomendar", "stage": "creciendo"}
    assert analyze.decision_pieza(None, 0.9) == "Descartar"
    assert analyze.decision_pieza(t, 0.1) == "Descartar"
    assert analyze.decision_pieza(t, 0.4) == "Aprender" and analyze.decision_pieza(t, 0.5) == "Recomendar"
    assert analyze.decision_pieza({"decision": "Aprender", "stage": "estable"}, 0.7) == "Aprender"
    assert analyze.decision_pieza({"decision": "Descartar", "stage": "bajando"}, 0.9) == "Descartar"


def test_collect_descarta_urls_con_email_y_guarda_costo_apify(monkeypatch, tmp_path, settings):
    from radar import collect
    settings.DATA_DIR = tmp_path
    mala = {"id": "hn:1", "source": "hn", "url": "https://lore.kernel.org/x/CAHk@mail.gmail.com/", "title": "t", "text": ""}
    buena = {"id": "hn:2", "source": "hn", "url": "https://example.com/a", "title": "t", "text": ""}
    for nombre in ("fetch_gnews", "fetch_linkedin", "fetch_youtube", "fetch_instagram", "fetch_tiktok", "fetch_x", "fetch_reddit", "fetch_arxiv"):
        monkeypatch.setattr(sources, nombre, lambda now: [])
    monkeypatch.setattr(sources, "fetch_hn", lambda now: [mala, buena])
    monkeypatch.setattr(sources, "fetch_wiki", lambda now: {})
    usos = iter([1.0, 1.6])
    monkeypatch.setattr(sources, "apify_uso_mensual", lambda: next(usos))
    snap = collect.run(AHORA)
    assert [s["id"] for s in snap["signals"]] == ["hn:2"]
    assert snap["meta"]["apify_cost_usd"] == 0.6


def test_build_usa_costo_apify_medido(datos):
    snap = _snap()
    assert build.build(snap)["totals"]["apify_cost_source"] == "estimado"
    snap["meta"] = {"apify_cost_usd": 0.42, "apify_cost_source": "medido"}
    t = build.build(snap)["totals"]
    assert t["apify_cost_usd"] == t["weekly_cost_usd"] == 0.42 and t["apify_cost_source"] == "medido"


def test_apify_uso_mensual_sin_token(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert sources.apify_uso_mensual() is None


def test_home_sensor_y_prellenado_get(client, db):
    html = client.get("/").content.decode()
    assert "Escanéalo" in html and "/analizar/?texto=" in html
    r = client.get("/analizar/", {"texto": "<script>x</script>" + "a" * 600, "red": "TikTok"})
    assert len(r.context["texto"]) == 500 and r.context["plataforma"] == "TikTok"
    assert "<script>x</script>" not in r.content.decode()  # autoescapado
    assert client.get("/analizar/", {"red": "Otra"}).context["plataforma"] == "Otro"


def test_como_funciona_muestra_holdout_y_cumplimiento(client):
    html = client.get("/como-funciona/").content.decode()
    assert "prueba aparte" in html.lower() or "prueba" in html and "Apify" in html
    assert "titulares públicos indexados en Google News" in html


def test_lr_exportado_reproduce_sklearn():
    """El JSON exportado + inferencia en Python puro da las mismas probabilidades que sklearn en 20 ejemplos."""
    np = pytest.importorskip("numpy")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    import random
    rnd = random.Random(1)
    vocab = {"a": "agentes ventas crm leads prospeccion".split(), "b": "nvidia gpu chips datacenter costos".split(),
             "c": "ley regulacion etica sesgo privacidad".split()}
    ej = []
    for _ in range(90):
        c = rnd.choice("abc")
        toks = [rnd.choice(vocab[c]) for _ in range(5)] + [rnd.choice(vocab[rnd.choice("abc")])]
        ej.append((toks, {"topic": c, "format": "x" if c == "a" else "y", "hook": c, "fit": "alto" if c != "b" else "bajo"}))
    lr = student.entrenar_lr(ej, 10, topn=30, min_df=1)
    json.loads(json.dumps(lr))  # serializable
    v = TfidfVectorizer(analyzer=lambda d: d, sublinear_tf=True, vocabulary=lr["terms"])
    X = v.fit_transform([t for t, _ in ej])
    for tarea in student.TAREAS:
        clf = LogisticRegression(C=10, max_iter=3000).fit(X, [y[tarea] for _, y in ej])
        for toks, _ in ej[:20]:
            ref = dict(zip(clf.classes_, clf.predict_proba(v.transform([toks]))[0]))
            got = student._dist_lr(lr, toks, tarea)
            assert max(ref, key=ref.get) == max(got, key=got.get)
            assert max(abs(ref[c] - got[c]) for c in ref) < 0.02


# ------------------------------------------------------------------ ronda 7

def test_semana_json_y_csv(client):
    j = client.get("/api/semana.json").json()
    assert j["week"] and j["temas"] and all(t["decision"] in ("Recomendar", "Aprender") for t in j["temas"])
    assert {"orden", "tema", "etapa", "por_que", "guion", "reel", "plataforma"} <= set(j["temas"][0])
    r = client.get("/api/semana.csv")
    assert r["Content-Type"].startswith("text/csv") and "attachment" in r["Content-Disposition"]
    lineas = r.content.decode("utf-8-sig").splitlines()
    assert lineas[0] == "orden,tema,decision,etapa,por_que,dia_sugerido,responsable,plataforma,guion,reel" and len(lineas) >= len(j["temas"]) + 1


def test_csv_neutraliza_formulas():
    from radar import plan
    assert "'=SUMA(1)" in plan.csv_texto([{"orden": 1, "tema": "=SUMA(1)", "decision": "x", "etapa": "x", "por_que": "x", "plataforma": "x", "guion": "", "reel": ""}])


def test_home_boton_plan_y_frase(client, db):
    html = client.get("/").content.decode()
    assert "Descargar plan (CSV)" in html and "Copiar para WhatsApp/Slack" in html and "Qué publicar el lunes, en 10 segundos." in html


def test_cifras_salen_de_student_json(client):
    m = student.cargar()["eval"]["topic"]["offline"]
    html = client.get("/como-funciona/").content.decode()
    assert f"acierta {round(m['holdout_accuracy'] * 100)}%" in html and "Privacidad" in html and "2:11 pm" in html
    assert "No guardamos lo que pegas" in client.get("/analizar/").content.decode()


def test_escaner_por_plataforma(settings, db):
    settings.DECISION_MODE = "replay"
    lista = "3 prompts de ChatGPT para tu informe:\n1. Resume tu correo\n2. Prepara tu reunión\n3. Redacta el informe semanal\nComenta PROMPT"
    ig = analyze.analizar(lista, "Instagram")
    assert ig["format"] == "carrusel" and ig["modo_guion"] == "reel" and ig["adapt_reel"] is None or ig["adapt_reel"]["platform"] == "Instagram"
    assert [t["texto"] for t in ig["tu_version"]["tomas"]] == ["Resume tu correo", "Prepara tu reunión", "Redacta el informe semanal"]
    tk = analyze.analizar("POV: tu jefe descubre que usaste ChatGPT para todo el informe \U0001F602", "TikTok")
    assert tk["format"] == "humor-pov" and tk["modo_guion"] == "reel"
    li = analyze.analizar(lista, "LinkedIn")
    assert li["format"] == "carrusel" and li["modo_guion"] == "normal"
    assert li["tu_version"]["gancho"].startswith("3 prompts") and "Comenta" in li["tu_version"]["cta"]


def test_veredicto_accion_y_guion_por_formato(settings, db):
    settings.DECISION_MODE = "replay"
    ig = analyze.analizar("3 prompts de ChatGPT para tu informe:\n1. Resume tu correo\n2. Prepara tu reunión\n3. Redacta el informe semanal\nComenta PROMPT", "Instagram")
    assert ig["adapt"] is None and ig["tu_version"]["gancho_label"] == "Portada" and ig["tu_version"]["cta"]
    assert ig["veredicto"]["accion"] in ("Publícalo esta semana", "Guárdalo para después", "Descártalo")
    li = analyze.analizar("Agentes de IA como compañeros de trabajo suben 40% la cotización de una empresa.", "LinkedIn")
    assert li["adapt_reel"] is None
    tt = analyze.analizar("POV: tu jefe pide el informe y le dices que lo hizo ChatGPT\nÉl: ¿y lo revisaste?\nTú: ...", "TikTok")
    assert [t["seg"] for t in tt["tu_version"]["tomas"]][:1] == ["3-10 s"]


def test_backtest_sin_fuga_y_detecta_tema_que_arranca():
    from radar import backtest
    fin = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
    ds = trend.dias(fin, 14)
    sig, topic_of = [], {}
    for i, d in enumerate(ds):
        for j in range(12):  # tema 'plano': 12 piezas por día; 'sube': 1 por día y luego 3 desde el día 5 (visible antes del corte)
            sig.append({"id": f"p{i}{j}", "published_at": d + "T10:00:00Z", "metrics": {}}); topic_of[f"p{i}{j}"] = "plano"
        for j in range(1 if i < 4 else 3 if i < 7 else 8):
            sig.append({"id": f"s{i}{j}", "published_at": d + "T10:00:00Z", "metrics": {}}); topic_of[f"s{i}{j}"] = "sube"
    r = backtest.correr(sig, topic_of, ["plano", "sube"], fin)
    assert r["crecieron"] == ["sube"] and r["senales_hasta_corte"] == sum(1 for s in sig if s["published_at"][:10] in ds[:7])
    assert r["marcados"] == ["sube"] and r["radar"]["precision"] == 1.0 and r["popularidad"]["precision"] == 0.0


def test_tres_preguntas():
    from django.conf import settings
    from radar.views import tres_preguntas
    topics = json.loads((settings.DATA_DIR / "radar.json").read_text(encoding="utf-8"))["topics"]
    c = tres_preguntas(topics)
    assert len(c) == 3 and all(x["evidencia_url"] for x in c)
    assert c[0]["slug"] == max((t for t in topics if t["stage"] == "temprana"), key=lambda t: t["growth"])["slug"]
    assert c[1]["slug"] == c[0]["slug"]
    assert c[2]["slug"] == max((t for t in topics if t["decision"] != "Descartar"), key=lambda t: t["exec_fit"])["slug"]
    # el de mayor exec_fit sin top_signals se salta
    mejor = next(t for t in topics if t["slug"] == c[2]["slug"])
    resto = [dict(t, top_signals=[]) if t is mejor else t for t in topics]
    assert tres_preguntas(resto)[2]["slug"] != mejor["slug"]


def test_llm_vs_student_parseo_y_acierto():
    from radar.management.commands import llm_vs_student as lv
    assert lv.parsear('ok ```json\n[{"i":0,"topic":"a"},{"i":1,"topic":"b"}]\n```') == {0: "a", 1: "b"}
    assert lv.parsear("sin json") == {}
    items = [{"title": f"t{i}", "text": ""} for i in range(3)]
    salidas = iter(['[{"i":0,"topic":"a"},{"i":1,"topic":"x"}]'])  # item 2 sin parsear; el reintento ya no devuelve nada
    r = lv.evaluar(items, ["a", "b", "c"], llamar=lambda p: next(salidas, ""))
    assert (r["n"], r["llm_top1"], r["llm_unparsed"], r["llm"]) == (3, 0.333, 1, ["a", "x", None])


def test_radar_json_trae_los_4_guiones():
    r = json.loads((Path(__file__).resolve().parent.parent / "data" / "radar.json").read_text(encoding="utf-8"))
    g = r["topics"][0]["guiones"]
    assert g["reel"]["hook"] and g["largo"]["title"] and g["largo"]["hook"] and g["linkedin"]["hook"] and g["recomendacion"]["postura"]
    assert len(g["reel"]["beats"]) >= 3 and len(g["largo"]["secciones"]) >= 4 and len(g["recomendacion"]["argumentos"]) == 3


def test_validador_de_guiones_rechaza_malformados():
    from radar.label import validar_guiones
    assert validar_guiones("basura") == {} and validar_guiones({"reel": {"hook": "", "beats": []}}) == {}
    assert validar_guiones({"reel": {"hook": "h", "beats": [{"texto": "t"}] * 3, "cta": "c"}}) == {}  # beats sin voz
    ok = validar_guiones({"linkedin": {"hook": "h", "slides": list("abcde"), "pregunta": "¿q?"}, "recomendacion": {"postura": "x"}})
    assert list(ok) == ["linkedin"]  # el tipo malformado se omite, el bueno queda


def test_cascada_estudiante_luego_llm():
    from radar.management.commands.llm_vs_student import cascada
    items = [{"gold": "a", "student": "a", "llm": "b", "student_conf": 0.9},   # seguro y acierta
             {"gold": "a", "student": "b", "llm": "a", "student_conf": 0.3},   # duda: el LLM acierta
             {"gold": "a", "student": "b", "llm": "b", "student_conf": 0.2}]   # duda: el LLM falla
    c = cascada(items, 0.5)
    assert c["top1"] == round(2 / 3, 3) and c["llamadas_llm"] == 2 and c["resuelve_estudiante"] == round(1 / 3, 3)


def test_reddit_filtra_y_no_guarda_autor():
    crudo = (FIX / "reddit.xml").read_bytes()
    out = sources.parse_reddit(crudo, "es", "es", filtrar=True)
    assert [s["title"] for s in out] == ["Cómo usar IA en mi negocio"]
    assert out[0]["id"] == "reddit:t3_aaa111" and out[0]["author_type"] == "comunidad" and "alguien" not in str(out)
    assert len(sources.parse_reddit(crudo, "es", "es")) == 2


def test_arxiv_sin_autores_ni_emails():
    out = sources.parse_arxiv((FIX / "arxiv.xml").read_bytes())
    assert out[0]["id"] == "arxiv:2610.22372" and out[0]["title"] == "Agentes LLM para ventas"
    assert "Persona" not in str(out) and "@" not in out[0]["text"] and out[0]["author_type"] == "academia"


def test_parse_x():
    xs = sources.parse_x(json.loads((FIX / "x.json").read_text(encoding="utf-8")), "ia")
    assert len(xs) == 3 and all(s["source"] == "x" and s["url"].startswith("https://x.com/i/status/") for s in xs)
    assert "@" not in xs[0]["title"] and "ana@" not in xs[0]["title"] and xs[0]["lang"] == "es"
    assert xs[0]["author_type"] == "creador" and xs[0]["metrics"]["views"] > 0 and trend.peso(xs[0]) > 1
