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
