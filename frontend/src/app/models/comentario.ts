export interface Comentario {
  id: number;
  id_central: number;
  fecha_dia: string;
  tipo: 'corte' | 'dat';
  fecha_inicio: string;
  fecha_fin: string;
  texto: string;
  usuario: string;
  created_at: string;
  updated_at: string;
}
