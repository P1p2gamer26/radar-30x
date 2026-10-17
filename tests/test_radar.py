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
