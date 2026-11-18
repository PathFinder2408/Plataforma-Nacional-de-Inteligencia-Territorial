from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .services import lookup_parcela_by_point, search_parcelas


@require_GET
def parcela_por_punto_view(request: HttpRequest) -> JsonResponse:
    """Devuelve la ficha básica de parcela que intersecta (lat, lng)."""
    raw_lat = request.GET.get("lat")
    raw_lng = request.GET.get("lng")
    if raw_lat is None or raw_lng is None:
        return JsonResponse(
            {"error": "Los parámetros 'lat' y 'lng' son obligatorios."},
            status=400,
        )
    try:
        lat = float(raw_lat)
        lng = float(raw_lng)
        parcela = lookup_parcela_by_point(lat, lng)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if parcela is None:
        return JsonResponse({"error": "No se encontró parcela en ese punto."}, status=404)
    return JsonResponse(parcela)


@require_GET
def buscar_parcelas_view(request: HttpRequest) -> JsonResponse:
    """Busca parcelas por rol, alias de rol o coordenadas."""
    query = request.GET.get("q", "")
    raw_limit = request.GET.get("limit", "10")
    try:
        limit = int(raw_limit)
        payload = search_parcelas(query, limit=limit)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)
