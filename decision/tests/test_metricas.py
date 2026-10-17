import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from decision.models import DecisionLog


def _log(accion, lat, costo, motor="llm"):
    return DecisionLog.objects.create(
        modo="live", motor=motor, entrada_hash="x", probabilidades={}, accion=accion,
        latencia_ms=lat, costo_usd=costo,
    )


@pytest.mark.django_db
def test_superadmin_ve_cifras(client):
    for a, l, c in [("auto", 100, "0.001"), ("auto", 200, "0.001"), ("revisar", 300, "0.001"), ("nada", 400, "0.001")]:
        _log(a, l, c)
    client.force_login(User.objects.create_superuser("root", password="x"))
    r = client.get(reverse("metricas"))
    assert r.status_code == 200
    c = r.context
    assert c["total"] == 4 and c["pct_auto"] == 50 and c["pct_revisar"] == 25 and c["pct_nada"] == 25
    assert c["lat_media"] == 250 and c["lat_p95"] == 400
    assert round(c["proyeccion_mensual"], 2) == 10.0


@pytest.mark.django_db
def test_usuario_normal_403(client):
    client.force_login(User.objects.create_user("ana", password="x"))
    assert client.get(reverse("metricas")).status_code == 403


@pytest.mark.django_db
def test_sin_logs_200(client):
    client.force_login(User.objects.create_superuser("root", password="x"))
    assert client.get(reverse("metricas")).status_code == 200
