"""Modelos de la app decision."""
from django.db import models


class DecisionLog(models.Model):
    """Registro de una decisión tomada por el motor."""

    ENGINE_CHOICES = [
        ("systemone", "SystemOne"),
        ("llm", "LLM"),
        ("fallback", "Fallback"),
        ("replay", "Replay"),
    ]

    ACTION_CHOICES = [
        ("auto", "Automática"),
        ("revisar", "Revisar"),
        ("nada", "Nada"),
    ]

    creado = models.DateTimeField(auto_now_add=True, db_index=True)
    referencia = models.CharField(max_length=100, blank=True, default="")
    modo = models.CharField(max_length=20)
    motor = models.CharField(max_length=20, choices=ENGINE_CHOICES)
    entrada_hash = models.CharField(max_length=64)
    probabilidades = models.JSONField()
    accion = models.CharField(max_length=20, choices=ACTION_CHOICES)
    latencia_ms = models.FloatField()
    costo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    class Meta:
        ordering = ("-creado",)
        verbose_name = "Registro de decisión"
        verbose_name_plural = "Registros de decisiones"

    def __str__(self):
        return f"{self.modo}/{self.motor} {self.entrada_hash[:8]} -> {self.accion}"