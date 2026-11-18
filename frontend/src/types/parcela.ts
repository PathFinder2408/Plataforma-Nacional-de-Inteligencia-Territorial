export type NivelConfianza = "alta" | "media" | "referencial";

export interface ProcedenciaDato {
  fuente: string;
  origen: string;
  licencia: string;
  fecha_corte: string | null;
  confianza: NivelConfianza;
}

export interface ParcelaFicha {
  id: number;
  rol: string;
  comuna: {
    codigo_ine: string;
    nombre: string;
    region_id: number;
  };
  superficie_m2: number | null;
  superficie_declarada: number | null;
  diferencia_superficie_pct: number | null;
  destino: string;
  serie: string;
  avaluo_fiscal: number | null;
  vigente_desde: string | null;
  vigente_hasta: string | null;
  centroide: {
    lng: number;
    lat: number;
  };
  procedencia: ProcedenciaDato;
}

export interface BuscarResponse {
  tipo: "coordenadas" | "rol";
  query: string;
  resultados: ParcelaFicha[];
}

export interface LayerVisibility {
  fiscal: boolean;
  normativa: boolean;
  riesgo: boolean;
}

export interface CabidaReferencial {
  ocupacion_max_m2: number | null;
  edificabilidad_max_m2: number | null;
  altura_max_m: number | null;
  superficie_predial_min_m2: number | null;
  cumple_superficie_min: boolean | null;
  descargo: string;
}

export interface ParcelaFichaCompleta {
  identificacion: ParcelaFicha;
  estatus_fiscal: {
    es_fiscal: boolean;
    coincidencias: Array<{
      codigo_bn: string;
      institucion: string;
      tipo: string;
      porcentaje_traslape: number | null;
      procedencia: ProcedenciaDato;
    }>;
  };
  normativa: Array<{
    instrumento: string;
    codigo_zona: string;
    nombre_zona: string;
    usos_permitidos: string[];
    parametros_urbanisticos: Record<string, number>;
    porcentaje_traslape: number | null;
    cabida_referencial: CabidaReferencial | null;
    procedencia: ProcedenciaDato;
  }>;
  riesgos: Array<{
    codigo_evento: string;
    tipo: string;
    nivel: string;
    descripcion: string;
    porcentaje_afectacion: number | null;
    procedencia: ProcedenciaDato;
  }>;
  relieve: {
    elevacion_media_m: number;
    pendiente_media_pct: number | null;
    exposicion_aspecto: string;
    procedencia: ProcedenciaDato | null;
  } | null;
  descargo_general: string;
}
