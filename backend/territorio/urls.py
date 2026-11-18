from django.urls import path

from .views import buscar_parcelas_view, parcela_ficha_completa_view, parcela_por_punto_view

urlpatterns = [
    path("parcelas/por-punto/", parcela_por_punto_view, name="parcela-por-punto"),
    path("parcelas/buscar/", buscar_parcelas_view, name="parcela-buscar"),
    path(
        "parcelas/<int:parcela_id>/ficha-completa/",
        parcela_ficha_completa_view,
        name="parcela-ficha-completa",
    ),
]
