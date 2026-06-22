export interface Central {
  id: number;
  nemo: string;
  tipo: number;
  ip1?: string | null;
  ip2?: string | null;
  protocolo: string;
  id_concentrador?: number | null;
}

export interface CentralCreate {
  nemo: string;
  tipo: number;
  ip1?: string | null;
  ip2?: string | null;
  protocolo?: string;
  id_concentrador?: number | null;
}

export interface DashboardCentral {
  id: number;
  nemo: string;
  tipo: number;
  cant_enlaces: number;
  tiene_grupos: boolean;
}
