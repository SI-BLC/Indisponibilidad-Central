export interface Enlace {
  id: number;
  nombre: string;
  idcentral: number;
  idtipo?: number;
  rol?: string | null;
}

export interface EnlaceCreate {
  nombre: string;
  idcentral: number;
  idtipo?: number;
  rol?: string | null;
}

export interface Grupo {
  id: number;
  idenlace: number;
  grupo: number;
  tipo: number;
  periodico: number;
  periodo: number;
  direccion: number;
  calcular?: number;
}

export interface GrupoCreate {
  idenlace: number;
  grupo: number;
  tipo?: number;
  periodico?: number;
  periodo?: number;
  direccion?: number;
  calcular?: number;
}

export interface GrupoUpdate {
  grupo?: number;
  tipo?: number;
  periodico?: number;
  periodo?: number;
  direccion?: number;
  calcular?: number;
}

export interface Mantenimiento {
  id: number;
  idenlace: number;
  tipo: number;
  inicio: string;
  fin: string;
  intervalos?: string;
  grupo: number;
  cantobjetos: number;
}

export interface MantenimientoCreate {
  idenlace: number;
  tipo: number;
  inicio: string;
  fin: string;
  grupo?: number;
  cantobjetos?: number;
}
