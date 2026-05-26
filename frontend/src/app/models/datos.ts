export interface ConItem {
  id: number;
  fecha: string | null;
  id_enlace: number | null;
  asoc_ab: string | null;
  asoc_ac: string | null;
  asoc_bb: string | null;
  asoc_bc: string | null;
  elc: string | null;
  link: string | null;
  integrity_scan: string | null;
  id_sotr: number | null;
  asoc_change: string | null;
}

export interface DatItem {
  id: number;
  fecha: string | null;
  id_enlace: number | null;
  id_gr: string | null;
  gr_grupo: number | null;
  siz: number | null;
  t: number | null;
  g: number | null;
  h: number | null;
  c: number | null;
  e: number | null;
  m: number | null;
  i: number | null;
  exp: number | null;
  freq: number | null;
  st: number | null;
}
