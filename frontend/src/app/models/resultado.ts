export interface ResultadoCentral {
  id: number;
  id_central: number;
  fecha: string;
  ind_total_seg: number | null;
  inconsistencia: number;
  generado_en: string | null;
  central_nemo: string | null;
  central_tipo: number | null;
}

export interface DetalleEnlaceEvento {
  t: string;
  tipo: 'i+' | 'e+';
}

export interface DetalleSegmento {
  inicio: string;
  fin: string;
  estado: 'prim' | 'bck' | 'ambos' | 'ninguno' | 'up' | 'down';
  dur_seg: number;
}

export interface DetallePeriodoDat {
  intervalo_fin: string;
  enlace?: string;
  prim_pct?: number;
  bck_pct?: number;
  gap_pct?: number;
  tipo_periodo?: 'normal' | 'proporcional' | 'excluido';
  esperados: number;
  recibidos: number;
  buenos: number;
  norecibidos: number;
  invalidos: number;
  ui_norec: number;
  ui_noval: number;
}

export interface DetalleInconsistencia {
  tipo: string;
  descripcion: string;
  t1: string;
  t2: string;
}

export interface DetalleCentral {
  central: string;
  tipo: number;
  ind_total_seg: number;
  corte_efectivo_seg?: number;
  ind_datos_seg?: number;
  inconsistencias: DetalleInconsistencia[];
  segments: DetalleSegmento[];
  cortes_efectivos: { enlace: string; inicio: string; fin: string; dur_seg: number }[];
  periodos_dat: DetallePeriodoDat[];
  eventos_prim?: DetalleEnlaceEvento[];
  eventos_bck?: DetalleEnlaceEvento[];
  error?: string;
}

export interface ResultadoReporte {
  id: number;
  id_enlace: number;
  fecha: string;
  enlace_nombre: string | null;
  bruta_c: number | null;
  bruta_b: number | null;
  neta_c: number | null;
  neta_b: number | null;
  promedio_neto: number | null;
  mant_cortes_c: number | null;
  mant_cortes_b: number | null;
  promedio_mant_cortes: number | null;
  ind_norec_c: number | null;
  ind_noval_c: number | null;
  ind_norec_b: number | null;
  ind_noval_b: number | null;
  ind_datos_norm: number | null;
  ind_mant_c: number | null;
  ind_mant_b: number | null;
  ind_datos_mant: number | null;
  ind_total_norm: number | null;
  ind_total_mant: number | null;
  generado_en: string | null;
  central_nemo: string | null;
  central_tipo: number | null;
  corte_efectivo: number | null;
  id_central_enlace: number | null;
}

export interface CorteReporte {
  id: number;
  id_enlace: number;
  fecha: string;
  asoc: string | null;
  inicio: string;
  fin: string;
  ind_bruta: number;
  ind_neta: number;
  tipo: number;
}

export interface GuardarResultadosResponse {
  fecha: string;
  procesados: number;
  exitosos: number;
  fallidos: number;
  detalle: { id_enlace: number; ok: boolean; enlace?: string; detalle?: string }[];
}

export interface GuardarResultadosMesResponse {
  periodo: string;
  dias_procesados: number;
  exitosos_total: number;
  fallidos_total: number;
  detalle_dias: { fecha: string; procesados: number; exitosos: number; fallidos: number }[];
}
