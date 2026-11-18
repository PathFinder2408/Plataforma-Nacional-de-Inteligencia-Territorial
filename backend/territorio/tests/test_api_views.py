from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="test-only")

from territorio.services import validate_coordinates
from territorio.views import buscar_parcelas_view, parcela_por_punto_view


def test_validate_coordinates_bounds() -> None:
    assert validate_coordinates(-29.90, -71.25) == (-29.90, -71.25)
    try:
        validate_coordinates(-95.0, -71.25)
        raise AssertionError("Debió lanzar ValueError")
    except ValueError:
        pass


def test_parcela_por_punto_missing_params() -> None:
    rf = RequestFactory()
    resp = parcela_por_punto_view(rf.get("/api/v1/parcelas/por-punto/"))
    assert resp.status_code == 400


def test_parcela_por_punto_not_found() -> None:
    rf = RequestFactory()
    with patch("territorio.views.lookup_parcela_by_point", return_value=None):
        resp = parcela_por_punto_view(
            rf.get("/api/v1/parcelas/por-punto/", {"lat": "-29.90", "lng": "-71.25"})
        )
    assert resp.status_code == 404


def test_parcela_por_punto_ok() -> None:
    rf = RequestFactory()
    sample = {"rol": "00101-00001", "procedencia": {"confianza": "referencial"}}
    with patch("territorio.views.lookup_parcela_by_point", return_value=sample):
        resp = parcela_por_punto_view(
            rf.get("/api/v1/parcelas/por-punto/", {"lat": "-29.90", "lng": "-71.25"})
        )
    assert resp.status_code == 200


def test_buscar_parcelas_empty_query() -> None:
    rf = RequestFactory()
    resp = buscar_parcelas_view(rf.get("/api/v1/parcelas/buscar/", {"q": "   "}))
    assert resp.status_code == 400
