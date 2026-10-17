"""Vistas de la app decision."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Count, Avg
from django.shortcuts import render
from .models import DecisionLog


@login_required
def metricas(request):
    """Vista de métricas (solo superusuarios)."""
    if not request.user.is_superuser:
        raise PermissionDenied

    # Total de decisiones
    total = DecisionLog.objects.count()

    # Porcentajes de acción
    # ponytail: evitar división por cero
    if total == 0:
        pct_auto = pct_revisar = pct_nada = 0
    else:
        auto_count = DecisionLog.objects.filter(accion="auto").count()
        revisar_count = DecisionLog.objects.filter(accion="revisar").count()
        nada_count = DecisionLog.objects.filter(accion="nada").count()
        pct_auto = (auto_count / total) * 100
        pct_revisar = (revisar_count / total) * 100
        pct_nada = (nada_count / total) * 100

    # Latencia media
    lat_media_qs = DecisionLog.objects.aggregate(avg=Avg("latencia_ms"))
    lat_media = lat_media_qs["avg"] or 0

    # Latencia p95
    # ponytail: p95 = valor en índice int(n*0.95) de lista ordenada
    latencias = list(DecisionLog.objects.values_list("latencia_ms", flat=True).order_by("latencia_ms"))
    n = len(latencias)
    if n == 0:
        lat_p95 = 0
    else:
        idx = int(n * 0.95)
        if idx >= n:
            idx = n - 1
        lat_p95 = latencias[idx]

    # Costos
    costo_total_qs = DecisionLog.objects.aggregate(total=Sum("costo_usd"))
    costo_total = float(costo_total_qs["total"] or 0)
    # ponytail: evitar división por cero
    if total == 0:
        costo_medio = 0
    else:
        costo_medio = costo_total / total

    proyeccion_mensual = costo_medio * 10000

    # Decisiones por motor
    por_motor = list(
        DecisionLog.objects.values("motor")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    context = {
        "total": total,
        "pct_auto": pct_auto,
        "pct_revisar": pct_revisar,
        "pct_nada": pct_nada,
        "lat_media": lat_media,
        "lat_p95": lat_p95,
        "costo_total": costo_total,
        "costo_medio": costo_medio,
        "proyeccion_mensual": proyeccion_mensual,
        "por_motor": por_motor,
    }
    return render(request, "metricas.html", context)