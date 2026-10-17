"""Admin de la app decision."""
from django.contrib import admin
from .models import DecisionLog


@admin.register(DecisionLog)
class DecisionLogAdmin(admin.ModelAdmin):
    """Admin de solo lectura para DecisionLog."""

    list_display = ("creado", "modo", "motor", "entrada_hash", "accion", "latencia_ms", "costo_usd")
    list_filter = ("modo", "motor", "accion", "creado")
    search_fields = ("referencia", "entrada_hash")
    readonly_fields = (
        "creado",
        "referencia",
        "modo",
        "motor",
        "entrada_hash",
        "probabilidades",
        "accion",
        "latencia_ms",
        "costo_usd",
    )
    ordering = ("-creado",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False