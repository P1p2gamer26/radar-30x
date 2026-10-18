from radar.atipicos import analizar


def _s(i, pts, src="hn", day="2026-10-12"):
    return {"id": f"{src}:{i}", "source": src, "url": "u", "title": f"t{i}", "published_at": day + "T10:00:00Z",
            "author_type": "creador" if pts > 50 else "comunidad", "metrics": {"points": pts}}


def test_lift_y_minimos():
    sig = [_s(i, 100) for i in range(4)] + [_s(10 + i, 10) for i in range(8)]  # mediana 10 -> 4 atípicas (x10)
    topic = {s["id"]: "a" for s in sig}
    hook = {s["id"]: ("pregunta" if s["metrics"]["points"] == 100 else "numero-dato") for s in sig}
    hook["hn:10"] = hook["hn:11"] = "pregunta"  # 2 de 8 en el resto
    fmt = {s["id"]: "tutorial" for s in sig}
    r = analizar(sig, topic, fmt, hook)["a"]
    assert r["n_outliers"] == 4
    assert r["lift_hook"] == {"hook": "pregunta", "x": 4.0}  # (4/4)/(2/8)
    assert r["lift_format"] is None  # x = 1 < 1.5
    assert r["dia"] == "lunes" and r["ejemplos"][0]["ratio"] == 10.0


def test_pocos_outliers_sin_lift():
    sig = [_s(0, 100)] + [_s(i, 10) for i in range(1, 9)]
    topic = {s["id"]: "a" for s in sig}
    r = analizar(sig, topic, {}, {})["a"]
    assert r["n_outliers"] == 1 and r["lift_hook"] is None and r["frase"] == "sin datos suficientes"


def test_fuente_sin_metricas_se_omite():
    sig = [{"id": "g:1", "source": "gnews", "url": "u", "title": "t", "published_at": "2026-10-12T10:00:00Z", "metrics": {}}]
    assert analizar(sig, {"g:1": "a"}, {}, {}) == {}
