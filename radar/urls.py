from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("tema/<slug:slug>/", views.tema, name="tema"),
    path("analizar/", views.analizar, name="analizar"),
    path("como-funciona/", views.como_funciona, name="como_funciona"),
    path("en-vivo/", views.en_vivo, name="en_vivo"),
    path("api/traza/", views.api_traza, name="api_traza"),
    path("api/radar.json", views.api_radar, name="api_radar"),
    path("api/semana.json", views.api_semana_json, name="api_semana_json"),
    path("api/semana.csv", views.api_semana_csv, name="api_semana_csv"),
]
