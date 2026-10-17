from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("tema/<slug:slug>/", views.tema, name="tema"),
    path("analizar/", views.analizar, name="analizar"),
    path("como-funciona/", views.como_funciona, name="como_funciona"),
    path("api/radar.json", views.api_radar, name="api_radar"),
]
