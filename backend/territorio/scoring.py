import statistics
from dataclasses import asdict, dataclass
from typing import Any

PERFILES_VALIDOS = {"inversionista", "desarrollador", "fiscal"}


@dataclass(frozen=True)
class FactorPuntaje:
    """Factor individual auditable que suma o resta al puntaje de oportunidad."""

    categoria: str
    etiqueta: str
    delta: float
    detalle: str
    confianza: str


def compute_opportunity_score(
    *,
    perfil: str,
    parcela: dict[str, Any],
    es_fiscal: bool,
    normativa: list[dict[str, Any]],
    riesgos: list[dict[str, Any]],
    relieve: dict[str, Any] | None,
    mercado_h3: dict[str, Any] | None,
) -> dict[str, Any]:
    """Calcula puntaje explicable [0..100] a partir de factores explícitos y trazables."""
    if perfil not in PERFILES_VALIDOS:
        raise ValueError(f"Perfil inválido '{perfil}'. Use uno de: {sorted(PERFILES_VALIDOS)}")

    base = 50.0
    factores: list[FactorPuntaje] = []

    # 1. Mercado y tendencia H3
    if mercado_h3 and mercado_h3.get("precio_m2_mediana_clp"):
        tendencia = float(mercado_h3.get("tendencia_pct") or 0.0)
        ratio = mercado_h3.get("ratio_precio_avaluo")
        delta_mkt = 0.0
        if tendencia >= 5.0:
            delta_mkt += 12.0
        elif tendencia <= -5.0:
            delta_mkt -= 8.0
        else:
            delta_mkt += 4.0

        if ratio is not None and 1.0 <= float(ratio) <= 2.2:
            delta_mkt += 5.0

        factores.append(
            FactorPuntaje(
                categoria="mercado",
                etiqueta="Dinámica de mercado H3",
                delta=round(delta_mkt, 2),
                detalle=(
                    f"Celda {mercado_h3['h3_index']}: mediana "
                    f"${mercado_h3['precio_m2_mediana_clp']:,.0f}/m², "
                    f"tendencia {tendencia:+.1f}%."
                ),
                confianza=str(mercado_h3["procedencia"]["confianza"]),
            )
        )
    else:
        factores.append(
            FactorPuntaje(
                categoria="mercado",
                etiqueta="Sin datos de mercado H3",
                delta=0.0,
                detalle="No hay transacciones F2890 suficientes en la celda H3.",
                confianza="referencial",
            )
        )

    # 2. Aptitud normativa y cabida
    if normativa:
        zona = normativa[0]
        params = zona.get("parametros_urbanisticos") or {}
        coef_const = float(params.get("coef_constructibilidad") or 0.0)
        cumple_min = (zona.get("cabida_referencial") or {}).get("cumple_superficie_min")

        if coef_const >= 1.5:
            delta_norm = 15.0 if perfil != "desarrollador" else 20.0
            msg = f"Zona {zona['codigo_zona']} con alta edificabilidad (coef. {coef_const})."
        elif coef_const >= 0.5:
            delta_norm = 8.0
            msg = f"Zona {zona['codigo_zona']} con edificabilidad moderada (coef. {coef_const})."
        else:
            delta_norm = -8.0
            msg = f"Zona {zona['codigo_zona']} restrictiva (coef. {coef_const})."

        if cumple_min is False:
            delta_norm -= 5.0
            msg += " Superficie bajo el mínimo predial zonal."

        factores.append(
            FactorPuntaje(
                categoria="normativa",
                etiqueta="Aptitud normativa",
                delta=round(delta_norm, 2),
                detalle=msg,
                confianza=str(zona["procedencia"]["confianza"]),
            )
        )
    else:
        factores.append(
            FactorPuntaje(
                categoria="normativa",
                etiqueta="Sin zonificación cargada",
                delta=0.0,
                detalle="Requiere validar Instrumento de Planificación Territorial / CIP.",
                confianza="referencial",
            )
        )

    # 3. Riesgos y amenazas
    if not riesgos:
        factores.append(
            FactorPuntaje(
                categoria="riesgo",
                etiqueta="Exposición a amenazas",
                delta=10.0,
                detalle="Sin amenazas registradas en las capas cargadas.",
                confianza="media",
            )
        )
    else:
        penalizaciones = {"alto": -25.0, "restriccion": -22.0, "medio": -10.0, "bajo": -4.0}
        for r in riesgos:
            base_pen = penalizaciones.get(r["nivel"], -5.0)
            factores.append(
                FactorPuntaje(
                    categoria="riesgo",
                    etiqueta=f"Riesgo {r['tipo']} ({r['nivel']})",
                    delta=base_pen,
                    detalle=(
                        f"Afectación {r.get('porcentaje_afectacion') or 0:.1f}%: "
                        f"{r.get('descripcion') or r['codigo_evento']}"
                    ),
                    confianza=str(r["procedencia"]["confianza"]),
                )
            )

    # 4. Relieve (DEM)
    if relieve and relieve.get("pendiente_media_pct") is not None:
        pend = float(relieve["pendiente_media_pct"])
        if pend <= 5.0:
            delta_rel = 10.0
            desc_rel = f"Pendiente suave ({pend:.1f}%) favorable para desarrollo."
        elif pend <= 15.0:
            delta_rel = 4.0
            desc_rel = f"Pendiente moderada ({pend:.1f}%)."
        else:
            delta_rel = -10.0
            desc_rel = f"Pendiente alta ({pend:.1f}%), mayor costo de urbanización."

        rel_conf = (relieve.get("procedencia") or {}).get("confianza") or "referencial"
        factores.append(
            FactorPuntaje(
                categoria="relieve",
                etiqueta="Topografía (DEM)",
                delta=delta_rel,
                detalle=desc_rel,
                confianza=str(rel_conf),
            )
        )

    # 5. Estatus fiscal y calidad de dato
    if es_fiscal:
        delta_fiscal = 15.0 if perfil == "fiscal" else -15.0
        desc_fiscal = (
            "Terreno fiscal apto para solicitud de arriendo/concesión."
            if perfil == "fiscal"
            else "Propiedad fiscal: no disponible para compraventa privada directa."
        )
        factores.append(
            FactorPuntaje(
                categoria="estatus_fiscal",
                etiqueta="Propiedad fiscal",
                delta=delta_fiscal,
                detalle=desc_fiscal,
                confianza="media",
            )
        )

    conf_geom = str((parcela.get("procedencia") or {}).get("confianza") or "referencial")
    conf_deltas = {"alta": 5.0, "media": 2.0, "referencial": 0.0}
    factores.append(
        FactorPuntaje(
            categoria="calidad_dato",
            etiqueta="Calidad geométrica",
            delta=conf_deltas.get(conf_geom, 0.0),
            detalle=f"Geometría predial con nivel de confianza '{conf_geom}'.",
            confianza=conf_geom,
        )
    )

    raw_score = base + sum(f.delta for f in factores)
    score_total = round(max(0.0, min(100.0, raw_score)), 2)

    return {
        "perfil": perfil,
        "puntaje_total": score_total,
        "puntaje_base": base,
        "metodologia": "Modelo aditivo transparente (base 50 + suma acotada [0, 100])",
        "factores": [asdict(f) for f in factores],
    }


def evaluate_valuation_error(observaciones: list[dict[str, float]]) -> dict[str, Any]:
    """Calcula MAE y MAPE comparando valor estimado (superficie * mediana H3) vs F2890 real."""
    if not observaciones:
        return {
            "muestras": 0,
            "mae_clp": None,
            "mape_pct": None,
            "detalle": "Sin transacciones suficientes para validar error.",
        }

    abs_errors: list[float] = []
    pct_errors: list[float] = []
    for obs in observaciones:
        real_val = float(obs["monto_real_clp"])
        est_val = float(obs["monto_estimado_clp"])
        if real_val <= 0:
            continue
        err = abs(est_val - real_val)
        abs_errors.append(err)
        pct_errors.append((err / real_val) * 100.0)

    if not abs_errors:
        return {
            "muestras": 0,
            "mae_clp": None,
            "mape_pct": None,
            "detalle": "Sin muestras válidas con monto positivo.",
        }

    return {
        "muestras": len(abs_errors),
        "mae_clp": round(statistics.mean(abs_errors), 2),
        "mape_pct": round(statistics.mean(pct_errors), 2),
        "metodologia": "Comparación monto F2890 observado vs superficie_m2 * mediana_m2 H3 res.8",
    }
