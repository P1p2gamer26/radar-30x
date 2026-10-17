"""URLs de la app decision."""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.metricas, name="metricas"),
]