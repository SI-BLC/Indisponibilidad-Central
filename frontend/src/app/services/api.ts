import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Central, CentralCreate, DashboardCentral } from '../models/central';
import { Enlace, EnlaceCreate, Grupo, GrupoCreate, GrupoUpdate, Mantenimiento, MantenimientoCreate } from '../models/enlace';
import { ReporteOut, ReporteRequest } from '../models/reporte';
import { ResultadoReporte, ResultadoCentral, DetalleCentral, CorteReporte, GuardarResultadosResponse, GuardarResultadosMesResponse } from '../models/resultado';
import { ConItem, DatItem } from '../models/datos';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = 'http://10.230.90.220:8000';

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
  guardarResultados(fecha?: string): Observable<GuardarResultadosResponse> {
    let params = new HttpParams();
    if (fecha) params = params.set('fecha', fecha);
    return this.http.post<GuardarResultadosResponse>(`${this.base}/resultados/guardar`, null, { params });
  }

  guardarResultadosMes(year?: number, month?: number): Observable<GuardarResultadosMesResponse> {
    let params = new HttpParams();
    if (year) params = params.set('year', year);
    if (month) params = params.set('month', month);
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
}
