import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { ResultadoCentral } from '../../models/resultado';

type RangoModo = 'mes_actual' | 'mes_anterior' | 'personalizado';

interface DiaGroup {
  fecha: string;
  centrales: ResultadoCentral[];
}

@Component({
  selector: 'app-resultados',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatTooltipModule,
  ],
  templateUrl: './resultados.html',
  styleUrl: './resultados.scss',
})
export class Resultados implements OnInit {
  private readonly api    = inject(ApiService);
  private readonly fb     = inject(FormBuilder);
  private readonly router = inject(Router);

  centrales = signal<Central[]>([]);
  diasView  = signal<DiaGroup[]>([]);
  loading   = signal(false);
  buscado   = signal(false);

  rangoModo = signal<RangoModo>('mes_actual');

  form = this.fb.group({
    idCentral : [null as number | null],
    fechaDesde: [''],
    fechaHasta: [''],
  });

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: (c) => this.centrales.set(c) });
    this.aplicarRango('mes_actual');
    this.buscar();
  }

  aplicarRango(modo: RangoModo) {
    this.rangoModo.set(modo);
    if (modo === 'personalizado') return;
    const hoy = new Date();
    let desde: Date, hasta: Date;
    if (modo === 'mes_actual') {
      desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
      hasta = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);
    } else {
      desde = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
      hasta = new Date(hoy.getFullYear(), hoy.getMonth(), 0);
    }
    this.form.patchValue({ fechaDesde: this.toIsoDate(desde), fechaHasta: this.toIsoDate(hasta) });
  }

  buscar() {
    this.loading.set(true);
    this.buscado.set(true);
    const v = this.form.value;
    this.api.getResultadosCentrales({
      id_central: v.idCentral ?? null,
      fecha_desde: v.fechaDesde || null,
      fecha_hasta: v.fechaHasta || null,
    }).subscribe({
      next: (rows) => {
        this.diasView.set(this.agruparPorDia(rows));
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  abrirDetalle(card: ResultadoCentral) {
    this.router.navigate(['/resultados', card.id_central, card.fecha]);
  }

  private agruparPorDia(rows: ResultadoCentral[]): DiaGroup[] {
    const map = new Map<string, ResultadoCentral[]>();
    for (const r of rows) {
      if (!map.has(r.fecha)) map.set(r.fecha, []);
      map.get(r.fecha)!.push(r);
    }
    return [...map.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([fecha, centrales]) => ({ fecha, centrales }));
  }

  tipoCentralLabel(tipo: number | null): string {
    switch (tipo) {
      case 1: return 'Directa';
      case 2: return 'Redundante';
      case 3: return 'Solo Backup';
      default: return '';
    }
  }

  tipoBadgeClass(tipo: number | null): string {
    switch (tipo) {
      case 1: return 'badge-primary';
      case 2: return 'badge-success';
      case 3: return 'badge-warning';
      default: return '';
    }
  }

  segToHms(seg: number | null): string {
    if (seg == null) return '—';
    const s = Math.round(seg);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sc = s % 60;
    return `${h}h ${m}m ${sc}s`;
  }

  private toIsoDate(d: Date): string {
    return d.toISOString().slice(0, 10);
  }
}
