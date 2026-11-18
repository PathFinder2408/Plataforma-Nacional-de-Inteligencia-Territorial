from django.urls import path

from .views import buscar_parcelas_view, parcela_por_punto_view

urlpatterns = [
    path("parcelas/por-punto/", parcela_por_punto_view, name="parcela-por-punto"),
    path("parcelas/buscar/", buscar_parcelas_view, name="parcela-buscar"),
]
