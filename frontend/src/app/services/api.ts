import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Central, CentralCreate, DashboardCentral } from '../models/central';
import { Enlace, EnlaceCreate, Grupo, GrupoCreate, GrupoUpdate, DataSet, DataSetCreate, DataSetUpdate, Mantenimiento, MantenimientoCreate } from '../models/enlace';
import { ReporteOut, ReporteRequest } from '../models/reporte';
import { ResultadoReporte, ResultadoCentral, DetalleCentral, CorteReporte, GuardarResultadosResponse, GuardarResultadosMesResponse } from '../models/resultado';
import { ConItem, DatItem, ConIccpItem, DatIccpItem } from '../models/datos';
import { CargaManualResult } from '../models/carga-manual';
import { Comentario } from '../models/comentario';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = 'https://10.230.90.220';

  // Centrales
  getCentrales(): Observable<Central[]> {
    return this.http.get<Central[]>(`${this.base}/centrales`);
  }

  getCentral(id: number): Observable<Central> {
    return this.http.get<Central>(`${this.base}/centrales/${id}`);
  }

  crearCentral(data: CentralCreate): Observable<Central> {
    return this.http.post<Central>(`${this.base}/centrales`, data);
  }

  actualizarCentral(id: number, data: Partial<CentralCreate>): Observable<Central> {
    return this.http.put<Central>(`${this.base}/centrales/${id}`, data);
  }

  eliminarCentral(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/centrales/${id}`);
  }

  // Dashboard
  getDashboard(): Observable<DashboardCentral[]> {
    return this.http.get<DashboardCentral[]>(`${this.base}/dashboard`);
  }

  // Enlaces
  getEnlaces(idcentral?: number): Observable<Enlace[]> {
    let params = new HttpParams();
    if (idcentral !== undefined) params = params.set('idcentral', idcentral);
    return this.http.get<Enlace[]>(`${this.base}/enlaces`, { params });
  }

  crearEnlace(data: EnlaceCreate): Observable<Enlace> {
    return this.http.post<Enlace>(`${this.base}/enlaces`, data);
  }

  eliminarEnlace(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/enlaces/${id}`);
  }

  // Grupos
  getGrupos(idenlace?: number): Observable<Grupo[]> {
    let params = new HttpParams();
    if (idenlace !== undefined) params = params.set('idenlace', idenlace);
    return this.http.get<Grupo[]>(`${this.base}/grupos`, { params });
  }

  crearGrupo(data: GrupoCreate): Observable<Grupo> {
    return this.http.post<Grupo>(`${this.base}/grupos`, data);
  }

  actualizarGrupo(id: number, data: GrupoUpdate): Observable<Grupo> {
    return this.http.put<Grupo>(`${this.base}/grupos/${id}`, data);
  }

  eliminarGrupo(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/grupos/${id}`);
  }

  // Mantenimientos
  getMantenimientos(idenlace?: number): Observable<Mantenimiento[]> {
    let params = new HttpParams();
    if (idenlace !== undefined) params = params.set('idenlace', idenlace);
    return this.http.get<Mantenimiento[]>(`${this.base}/mantenimientos`, { params });
  }

  crearMantenimiento(data: MantenimientoCreate): Observable<Mantenimiento> {
    return this.http.post<Mantenimiento>(`${this.base}/mantenimientos`, data);
  }

  eliminarMantenimiento(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/mantenimientos/${id}`);
  }

  // Reporte
  generarReporte(req: ReporteRequest): Observable<ReporteOut> {
    return this.http.post<ReporteOut>(`${this.base}/reportes`, req);
  }

  generarReporteTxt(req: ReporteRequest): Observable<string> {
    return this.http.post(`${this.base}/reportes/txt`, req, { responseType: 'text' });
  }

  // Resultados
  guardarResultados(fecha?: string, idCentrales?: number[]): Observable<GuardarResultadosResponse> {
    let params = new HttpParams();
    if (fecha) params = params.set('fecha', fecha);
    if (idCentrales?.length) {
      for (const id of idCentrales) params = params.append('id_centrales', id);
    }
    return this.http.post<GuardarResultadosResponse>(`${this.base}/resultados/guardar`, null, { params });
  }

  guardarResultadosMes(year?: number, month?: number, idCentrales?: number[]): Observable<GuardarResultadosMesResponse> {
    let params = new HttpParams();
    if (year) params = params.set('year', year);
    if (month) params = params.set('month', month);
    if (idCentrales?.length) {
      for (const id of idCentrales) params = params.append('id_centrales', id);
    }
    return this.http.post<GuardarResultadosMesResponse>(`${this.base}/resultados/guardar-mes`, null, { params });
  }

  getCortes(filtros: {
    ids_enlace?: number[];
    fecha_desde?: string | null;
    fecha_hasta?: string | null;
  }): Observable<CorteReporte[]> {
    let params = new HttpParams();
    filtros.ids_enlace?.forEach(id => (params = params.append('ids_enlace', id)));
    if (filtros.fecha_desde) params = params.set('fecha_desde', filtros.fecha_desde);
    if (filtros.fecha_hasta) params = params.set('fecha_hasta', filtros.fecha_hasta);
    return this.http.get<CorteReporte[]>(`${this.base}/resultados/cortes`, { params });
  }

  getResultados(filtros: {
    id_central?: number | null;
    fecha_desde?: string | null;
    fecha_hasta?: string | null;
  }): Observable<ResultadoReporte[]> {
    let params = new HttpParams();
    if (filtros.id_central != null) params = params.set('id_central', filtros.id_central);
    if (filtros.fecha_desde) params = params.set('fecha_desde', filtros.fecha_desde);
    if (filtros.fecha_hasta) params = params.set('fecha_hasta', filtros.fecha_hasta);
    return this.http.get<ResultadoReporte[]>(`${this.base}/resultados`, { params });
  }

  getResultadosCentrales(filtros: {
    id_central?: number | null;
    fecha_desde?: string | null;
    fecha_hasta?: string | null;
  }): Observable<ResultadoCentral[]> {
    let params = new HttpParams();
    if (filtros.id_central != null) params = params.set('id_central', filtros.id_central);
    if (filtros.fecha_desde) params = params.set('fecha_desde', filtros.fecha_desde);
    if (filtros.fecha_hasta) params = params.set('fecha_hasta', filtros.fecha_hasta);
    return this.http.get<ResultadoCentral[]>(`${this.base}/resultados/centrales`, { params });
  }

  getDetalleCentral(idCentral: number, fecha: string): Observable<DetalleCentral> {
    return this.http.get<DetalleCentral>(`${this.base}/resultados/detalle/${idCentral}/${fecha}`);
  }

  // Check enlaces desde central (proxy via backend para evitar CORS)
  checkEnlaces(ip: string): Observable<string> {
    return this.http.get(`${this.base}/centrales/checkenlaces/${ip}`, { responseType: 'text' });
  }

  checkGrupos(ip: string, nombreEnlace: string): Observable<string> {
    const params = new HttpParams().set('nombre_enlace', nombreEnlace);
    return this.http.get(`${this.base}/centrales/checkgrupos/${ip}`, { responseType: 'text', params });
  }

  actualizarEnlace(id: number, data: Partial<EnlaceCreate>): Observable<Enlace> {
    return this.http.put<Enlace>(`${this.base}/enlaces/${id}`, data);
  }

  // Datos
  getDatosCon(filtros: { ids_enlace?: number[]; fecha_inicio?: string; fecha_fin?: string }): Observable<ConItem[]> {
    let params = new HttpParams();
    filtros.ids_enlace?.forEach(id => (params = params.append('ids_enlace', id)));
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    return this.http.get<ConItem[]>(`${this.base}/datos/con`, { params });
  }

  getDatosDat(filtros: { ids_enlace?: number[]; fecha_inicio?: string; fecha_fin?: string }): Observable<DatItem[]> {
    let params = new HttpParams();
    filtros.ids_enlace?.forEach(id => (params = params.append('ids_enlace', id)));
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    return this.http.get<DatItem[]>(`${this.base}/datos/dat`, { params });
  }

  getDatosConIccp(filtros: { ids_enlace?: number[]; fecha_inicio?: string; fecha_fin?: string }): Observable<ConIccpItem[]> {
    let params = new HttpParams();
    filtros.ids_enlace?.forEach(id => (params = params.append('ids_enlace', id)));
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    return this.http.get<ConIccpItem[]>(`${this.base}/datos/con_iccp`, { params });
  }

  getDatosDatIccp(filtros: { ids_enlace?: number[]; fecha_inicio?: string; fecha_fin?: string }): Observable<DatIccpItem[]> {
    let params = new HttpParams();
    filtros.ids_enlace?.forEach(id => (params = params.append('ids_enlace', id)));
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    return this.http.get<DatIccpItem[]>(`${this.base}/datos/dat_iccp`, { params });
  }

  // Carga Manual
  analizarCargaManual(centralId: number, files: File[]): Observable<CargaManualResult> {
    const fd = new FormData();
    fd.append('central_id', String(centralId));
    files.forEach(f => fd.append('files', f, f.name));
    return this.http.post<CargaManualResult>(`${this.base}/carga-manual/analizar`, fd);
  }

  confirmarCargaManual(centralId: number, files: File[]): Observable<CargaManualResult> {
    const fd = new FormData();
    fd.append('central_id', String(centralId));
    files.forEach(f => fd.append('files', f, f.name));
    return this.http.post<CargaManualResult>(`${this.base}/carga-manual/confirmar`, fd);
  }

  // DataSets (ICCP)
  getDataSets(idEnlace: number): Observable<DataSet[]> {
    return this.http.get<DataSet[]>(`${this.base}/datasets`, { params: { id_enlace: idEnlace } });
  }

  crearDataSetsDefaults(idEnlace: number): Observable<DataSet[]> {
    return this.http.post<DataSet[]>(`${this.base}/datasets/defaults/${idEnlace}`, {});
  }

  crearDataSet(data: DataSetCreate): Observable<DataSet> {
    return this.http.post<DataSet>(`${this.base}/datasets`, data);
  }

  actualizarDataSet(id: number, data: DataSetUpdate): Observable<DataSet> {
    return this.http.put<DataSet>(`${this.base}/datasets/${id}`, data);
  }

  eliminarDataSet(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/datasets/${id}`);
  }

  // Comentarios
  listarComentarios(idCentral: number, fechaDia: string, tipo?: string): Observable<Comentario[]> {
    let params = new HttpParams().set('id_central', idCentral).set('fecha_dia', fechaDia);
    if (tipo) params = params.set('tipo', tipo);
    return this.http.get<Comentario[]>(`${this.base}/comentarios/`, { params });
  }

  crearComentario(body: {
    id_central: number; fecha_dia: string; tipo: string;
    fecha_inicio: string; fecha_fin: string; texto: string;
  }): Observable<Comentario> {
    return this.http.post<Comentario>(`${this.base}/comentarios/`, body);
  }

  actualizarComentario(id: number, texto: string): Observable<Comentario> {
    return this.http.put<Comentario>(`${this.base}/comentarios/${id}`, { texto });
  }

  eliminarComentario(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/comentarios/${id}`);
  }

  // Cortes manuales
  insertarCorteManual(body: { id_enlace: number; fecha: string }): Observable<any> {
    return this.http.post(`${this.base}/cortes-manuales/`, body);
  }

  listarCortesManuales(idEnlace?: number, fecha?: string): Observable<any[]> {
    let params = new HttpParams();
    if (idEnlace) params = params.set('id_enlace', idEnlace);
    if (fecha) params = params.set('fecha', fecha);
    return this.http.get<any[]>(`${this.base}/cortes-manuales/`, { params });
  }

  eliminarCorteManual(idCon: number): Observable<any> {
    return this.http.delete(`${this.base}/cortes-manuales/${idCon}`);
  }

  // ── Instaladores ────────────────────────────────────────────────────────────

  checkPlantaInstalador(planta: string): Observable<any> {
    return this.http.get(`${this.base}/instaladores/check/${planta}`);
  }

  generarInstaladoresSSE(
    data: Record<string, any>,
    callbacks: {
      onProgress: (p: { step: number; total: number; message: string }) => void;
      onDone: (r: any) => void;
      onError: (msg: string) => void;
    },
  ) {
    const token = localStorage.getItem('auth_token') || '';
    fetch(`${this.base}/instaladores/generar`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    }).then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        callbacks.onError(err.detail || 'Error al generar');
        return;
      }
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.lastIndexOf('\n\n');
        if (boundary === -1) continue;
        const chunk = buffer.substring(0, boundary + 2);
        buffer = buffer.substring(boundary + 2);

        for (const block of chunk.split('\n\n').filter(Boolean)) {
          const lines = block.split('\n');
          let event = '';
          let dataStr = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) event = line.substring(7);
            if (line.startsWith('data: ')) dataStr = line.substring(6);
          }
          if (!event || !dataStr) continue;
          const parsed = JSON.parse(dataStr);
          if (event === 'progress') callbacks.onProgress(parsed);
          else if (event === 'done') callbacks.onDone(parsed);
          else if (event === 'error') callbacks.onError(parsed.message);
        }
      }
    }).catch((err) => {
      callbacks.onError('Error de conexión: ' + err.message);
    });
  }

  historialInstaladores(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/instaladores/historial`);
  }

  eliminarPlantaInstalador(planta: string): Observable<any> {
    return this.http.delete(`${this.base}/instaladores/eliminar/${planta}`);
  }
}
