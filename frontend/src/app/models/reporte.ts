export interface CorteItem {
  id_enlace: number;
  nombre_enlace: string;
  inicio: string;
  fin: string;
  duracion_minutos: number;
  es_mantenimiento: boolean;
  tipo?: string;
}

export interface ReporteOut {
  idCentral: number;
  nemo: string;
  tipo_central: number;
  fechaInicio: string;
  fechaFin: string;
  cortes: CorteItem[];
  disponibilidad_pct: number;
  total_minutos_corte: number;
  total_minutos_periodo: number;
}

export interface ReporteRequest {
  idCentral: number;
  fechaInicio: string;
  fechaFin: string;
}
