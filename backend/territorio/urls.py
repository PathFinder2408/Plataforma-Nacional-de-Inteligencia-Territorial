from django.urls import path

from .views import (
    buscar_parcelas_view,
    filtrar_parcelas_view,
    mercado_validacion_view,
    parcela_ficha_completa_view,
    parcela_por_punto_view,
    parcela_puntaje_view,
)

urlpatterns = [
    path("parcelas/por-punto/", parcela_por_punto_view, name="parcela-por-punto"),
    path("parcelas/buscar/", buscar_parcelas_view, name="parcela-buscar"),
    path("parcelas/filtrar/", filtrar_parcelas_view, name="parcela-filtrar"),
    path(
        "parcelas/<int:parcela_id>/ficha-completa/",
        parcela_ficha_completa_view,
        name="parcela-ficha-completa",
    ),
    path(
        "parcelas/<int:parcela_id>/puntaje/",
        parcela_puntaje_view,
        name="parcela-puntaje",
    ),
    path("mercado/validacion/", mercado_validacion_view, name="mercado-validacion"),
]
