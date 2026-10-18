import json
import re

import pytest
from django.core.cache import cache

from radar import en_vivo


@pytest.fixture(autouse=True)
def _limpio():
    cache.clear()


def test_pagina_200_con_etapas(client):
    r = client.get("/en-vivo/")
    h = r.content.decode()
    assert r.status_code == 200 and "Cómo piensa EstelarIA" in h and 'id="datos-vivo"' in h
    datos = json.loads(h.split('id="datos-vivo" type="application/json">')[1].split("</script>")[0])
    assert [e["nombre"] for e in datos["etapas"]] == [e["nombre"] for e in en_vivo.etapas({"totals": {}, "sources": []}, None, None)]
    assert len(datos["senales"]) > 0


def test_sin_emails_ni_handles_en_payload(client):
    h = client.get("/en-vivo/").content.decode()
    payload = h.split('id="datos-vivo"')[1].split("</script>")[0]
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", payload) and not re.search(r"(?<![\w\\])@\w{2,}", payload)


def test_traza_coherente_con_tau(client):
    r = client.post("/api/traza/", {"texto": "5 agentes de IA para automatizar ventas, escríbeme a juan@mail.com o @juan"})
    j = r.json()
    assert r.status_code == 200
    for k in ("limpio", "top3", "conf", "tau", "escala", "formato", "gancho", "etapa", "p", "decision", "regla"):
        assert k in j
    assert j["escala"] == (j["conf"] < j["tau"]) and len(j["top3"]) == 3
    assert "juan" not in j["limpio"]


def test_traza_rechaza_vacio_y_largo(client):
    assert client.post("/api/traza/", {"texto": "   "}).status_code == 400
    assert client.post("/api/traza/", {"texto": "a" * 2001}).status_code == 400
    assert client.get("/api/traza/").status_code == 405


def test_como_funciona_incluye_simulacion(client):
    h = client.get("/como-funciona/").content.decode()
    assert 'id="datos-vivo"' in h and "Míralo pensar en vivo" in h and 'id="sim-vivo"' in h and "/en-vivo/" in h
