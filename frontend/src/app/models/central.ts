export interface Central {
  id: number;
  nemo: string;
  nemo_cammesa?: string | null;
  cliente?: string | null;
  pem?: string | null;
  tipo: number;
  ip1?: string | null;
  ip2?: string | null;
  protocolo: string;
  id_concentrador?: number | null;
  ssl: number;
}

export interface CentralCreate {
  nemo: string;
  nemo_cammesa?: string | null;
  cliente?: string | null;
  pem?: string | null;
  tipo: number;
  ip1?: string | null;
  ip2?: string | null;
  protocolo?: string;
  id_concentrador?: number | null;
  ssl?: number;
}

export interface DashboardCentral {
  id: number;
  nemo: string;
  tipo: number;
  cant_enlaces: number;
  tiene_grupos: boolean;
}
