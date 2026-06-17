export interface ArchivoCargaInfo {
  nombre: string;
  tipo: string;
  log: string[];
  a_insertar: number;
  duplicados: number;
}

export interface ResumenCarga {
  con_a_insertar: number;
  dat_a_insertar: number;
  con_duplicados: number;
  dat_duplicados: number;
}

export interface CargaManualResult {
  central_id: number;
  enlaces_central: string[];
  archivos: ArchivoCargaInfo[];
  resumen: ResumenCarga;
}
