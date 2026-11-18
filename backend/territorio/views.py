from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .services import (
    filter_parcelas,
    get_parcela_ficha_completa,
    lookup_parcela_by_point,
    search_parcelas,
    validate_market_valuation,
)


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


@require_GET
def parcela_ficha_completa_view(request: HttpRequest, parcela_id: int) -> JsonResponse:
    """Devuelve la ficha completa de parcela con estatus fiscal, normativa, riesgo y relieve."""
    perfil = request.GET.get("perfil", "inversionista")
    try:
        ficha = get_parcela_ficha_completa(parcela_id, perfil=perfil)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if ficha is None:
        return JsonResponse({"error": "Parcela no encontrada."}, status=404)
    return JsonResponse(ficha)


@require_GET
def parcela_puntaje_view(request: HttpRequest, parcela_id: int) -> JsonResponse:
    """Devuelve exclusivamente el puntaje explicable de oportunidad para un perfil."""
    perfil = request.GET.get("perfil", "inversionista")
    try:
        ficha = get_parcela_ficha_completa(parcela_id, perfil=perfil)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if ficha is None:
        return JsonResponse({"error": "Parcela no encontrada."}, status=404)
    return JsonResponse(ficha["puntaje_oportunidad"])


@require_GET
def mercado_validacion_view(_request: HttpRequest) -> JsonResponse:
    """Devuelve métricas MAE/MAPE de validación contra transacciones F2890."""
    return JsonResponse(validate_market_valuation())


@require_GET
def filtrar_parcelas_view(request: HttpRequest) -> JsonResponse:
    """Filtra parcelas vigentes por criterios espaciales y de aptitud."""
    try:
        min_sup = float(request.GET["min_sup"]) if request.GET.get("min_sup") else None
        max_sup = float(request.GET["max_sup"]) if request.GET.get("max_sup") else None
        max_pend = (
            float(request.GET["max_pendiente"]) if request.GET.get("max_pendiente") else None
        )
        excluir_riesgos = request.GET.get("excluir_riesgos", "").lower() in {"1", "true", "si"}
        solo_fiscales = request.GET.get("solo_fiscales", "").lower() in {"1", "true", "si"}
        destino = request.GET.get("destino") or None
        limit = int(request.GET.get("limit", "25"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    resultados = filter_parcelas(
        min_sup=min_sup,
        max_sup=max_sup,
        max_pendiente=max_pend,
        excluir_riesgos=excluir_riesgos,
        solo_fiscales=solo_fiscales,
        destino=destino,
        limit=limit,
    )
    return JsonResponse({"resultados": resultados})
