import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../services/api';
import { DetalleCentral, DetalleSegmento } from '../../models/resultado';

@Component({
  selector: 'app-resultado-detalle',
  imports: [
    CommonModule, DecimalPipe,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule,
  ],
  templateUrl: './resultado-detalle.html',
  styleUrl:    './resultado-detalle.scss',
})
export class ResultadoDetalle implements OnInit {
  private readonly api    = inject(ApiService);
  private readonly route  = inject(ActivatedRoute);
  private readonly router = inject(Router);

  centralId = 0;
  fecha     = '';
  loading   = signal(true);
  detalle   = signal<DetalleCentral | null>(null);
  error     = signal('');

  readonly DIA_SEG = 86400;

  ngOnInit() {
    this.centralId = Number(this.route.snapshot.paramMap.get('centralId'));
    this.fecha     = this.route.snapshot.paramMap.get('fecha') ?? '';
    this.cargar();
  }

  cargar() {
    this.loading.set(true);
    this.error.set('');
    this.api.getDetalleCentral(this.centralId, this.fecha).subscribe({
      next: (d) => { this.detalle.set(d); this.loading.set(false); },
      error: () => { this.error.set('No se pudo cargar el detalle.'); this.loading.set(false); },
    });
  }

  volver() {
    this.router.navigate(['/resultados']);
  }

  // ── Timeline helpers ──────────────────────────────────────────────────────

  /** Porcentaje de posición/ancho dentro del día (0..100) */
  pct(t: string): number {
    const d = new Date(t);
    const hh = d.getHours(), mm = d.getMinutes(), ss = d.getSeconds();
    return ((hh * 3600 + mm * 60 + ss) / this.DIA_SEG) * 100;
  }

  pctDur(seg: number): number {
    return (seg / this.DIA_SEG) * 100;
  }

  segColor(estado: string): string {
    switch (estado) {
      case 'up':      return '#4bd08b';
      case 'down':    return '#ff6b6b';
      case 'prim':    return '#539bff';
      case 'bck':     return '#f8c076';
      case 'ambos':   return '#fa896b';
      case 'ninguno': return '#ff6b6b';
      default:        return '#7c839d';
    }
  }

  estadoLabel(estado: string): string {
    switch (estado) {
      case 'up':      return 'Disponible';
      case 'down':    return 'Caído';
      case 'prim':    return 'Enlace Directo';
      case 'bck':     return 'Enlace Backup';
      case 'ambos':   return 'Ambos activos (inconsistencia)';
      case 'ninguno': return 'Sin cobertura (corte efectivo)';
      default:        return estado;
    }
  }

  // ── Formato ───────────────────────────────────────────────────────────────

  segToHms(seg: number | null | undefined): string {
    if (seg == null) return '—';
    const s = Math.round(seg);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sc = s % 60;
    return `${h}h ${m}m ${sc}s`;
  }

  horaCorta(iso: string): string {
    const d = new Date(iso);
    return d.toTimeString().slice(0, 8);
  }

  tipoPeriodoBadge(tipo: string | undefined): string {
    switch (tipo) {
      case 'proporcional': return 'badge-warning';
      case 'excluido':     return 'badge-danger';
      default:             return 'badge-ok';
    }
  }

  tipoCentralLabel(tipo: number): string {
    switch (tipo) {
      case 1: return 'Directa';
      case 2: return 'Redundante';
      case 3: return 'Solo Backup';
      default: return '';
    }
  }
}
