import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormControl } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
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
    MatProgressSpinnerModule, MatAutocompleteModule, MatTooltipModule,
  ],
  templateUrl: './resultados.html',
  styleUrl: './resultados.scss',
})
export class Resultados implements OnInit {
  private readonly api    = inject(ApiService);
  private readonly fb     = inject(FormBuilder);
  private readonly router = inject(Router);

  centrales = signal<Central[]>([]);
  searchCentral = new FormControl('');
  centralFilter = signal('');
  filteredCentrales = computed(() => {
    const term = this.centralFilter().toUpperCase();
    if (!term) return this.centrales();
    return this.centrales().filter(c => c.nemo.toUpperCase().includes(term));
  });
  displayCentral = (c: Central | string | null): string => {
    if (!c || typeof c === 'string') return '';
    return c.nemo;
  };
  diasView  = signal<DiaGroup[]>([]);
  loading   = signal(false);
  buscado   = signal(false);

  rangoModo = signal<RangoModo>('mes_actual');

  form = this.fb.group({
    idCentral : [null as number | null],
    fechaDesde: [''],
    fechaHasta: [''],
  });

  onCentralSelected(event: any) {
    const central: Central = event.option.value;
    this.form.controls.idCentral.setValue(central.id);
  }

  clearCentral() {
    this.searchCentral.setValue('');
    this.form.controls.idCentral.setValue(null);
  }

  private readonly STORAGE_KEY = 'resultados_filtros';

  ngOnInit() {
    this.searchCentral.valueChanges.subscribe(val => {
      if (typeof val === 'string') this.centralFilter.set(val);
    });

    const saved = this.restoreState();
    this.api.getCentrales().subscribe({
      next: (c) => {
        this.centrales.set(c);
        if (saved?.idCentral) {
          const match = c.find(x => x.id === saved.idCentral);
          if (match) this.searchCentral.setValue(match as any);
        }
      },
    });

    if (saved) {
      this.aplicarRango(saved.rangoModo);
      this.form.patchValue({ idCentral: saved.idCentral, fechaDesde: saved.fechaDesde, fechaHasta: saved.fechaHasta });
      this.buscar();
    } else {
      this.aplicarRango('mes_actual');
      this.buscar();
    }
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
    this.saveState();
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

  private saveState() {
    const v = this.form.value;
    sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify({
      rangoModo: this.rangoModo(),
      idCentral: v.idCentral ?? null,
      fechaDesde: v.fechaDesde || '',
      fechaHasta: v.fechaHasta || '',
    }));
  }

  private restoreState(): { rangoModo: RangoModo; idCentral: number | null; fechaDesde: string; fechaHasta: string } | null {
    const raw = sessionStorage.getItem(this.STORAGE_KEY);
    sessionStorage.removeItem(this.STORAGE_KEY);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  private toIsoDate(d: Date): string {
    return d.toISOString().slice(0, 10);
  }
}
