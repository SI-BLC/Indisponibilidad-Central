import { Component, inject, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { BaseChartDirective } from 'ng2-charts';
import { Chart, ChartConfiguration, ChartData, registerables } from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import ChartDataLabels from 'chartjs-plugin-datalabels';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';

Chart.register(...registerables, annotationPlugin, ChartDataLabels);
Chart.defaults.set('plugins.datalabels', { display: false });

@Component({
  selector: 'app-ris',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatSelectModule,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule,
    MatAutocompleteModule, MatInputModule, MatTooltipModule,
    BaseChartDirective,
  ],
  templateUrl: './ris.html',
  styleUrl: './ris.scss',
})
export class Ris {
  private readonly api = inject(ApiService);

  centrales = signal<Central[]>([]);
  searchControl = new FormControl('');
  searchFilter = signal('');
  filteredCentrales = computed(() => {
    const term = this.searchFilter().toUpperCase();
    const list = this.centrales().filter(c => [1, 2, 3].includes(c.tipo));
    if (!term) return list;
    return list.filter(c => c.nemo.toUpperCase().includes(term));
  });

  centralSeleccionada = signal<Central | null>(null);
  mesSeleccionado = signal('');
  mesesDisponibles = signal<string[]>([]);
  loading = signal(false);
  ris = signal<any>(null);

  displayCentral = (c: Central | string | null): string => {
    if (!c) return '';
    if (typeof c === 'string') return c;
    return c.nemo;
  };

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: c => this.centrales.set(c) });
    this.searchControl.valueChanges.subscribe(val => {
      if (typeof val === 'string') this.searchFilter.set(val);
    });
    const now = new Date();
    const meses: string[] = [];
    for (let i = 0; i < 18; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      meses.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
    }
    this.mesesDisponibles.set(meses);
    this.mesSeleccionado.set(meses[0]);
  }

  onCentralSelected(event: any) {
    const central: Central = event.option.value;
    this.centralSeleccionada.set(central);
    this.cargar();
  }

  cargar() {
    const c = this.centralSeleccionada();
    const m = this.mesSeleccionado();
    if (!c || !m) return;
    this.loading.set(true);
    this.ris.set(null);
    this.api.getRis(c.id, m).subscribe({
      next: data => { this.ris.set(data); this.loading.set(false); },
      error: () => { this.loading.set(false); },
    });
  }

  onMesChange() { this.cargar(); }

  formatSeg(seg: number | null): string {
    if (seg == null) return '-';
    return Math.round(seg).toLocaleString('es-AR');
  }

  formatPct(pct: number | null): string {
    if (pct == null) return '-';
    return pct.toFixed(4) + '%';
  }

  formatPct2(pct: number | null): string {
    if (pct == null) return '-';
    return pct.toFixed(2) + '%';
  }

  formatMes(mes: string): string {
    const [a, m] = mes.split('-');
    const nombres = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    return `${nombres[+m]} ${a}`;
  }

  formatMesCorto(mes: string): string {
    const [a, m] = mes.split('-');
    const nombres = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    return `${nombres[+m]} ${a.slice(2)}`;
  }

  formatFecha(fecha: string): string {
    const [a, m, d] = fecha.split('-');
    return `${d}/${m}`;
  }

  formatDatetime(dt: string): string {
    return dt.replace('T', ' ').slice(0, 19);
  }

  formatDuracion(seg: number): string {
    const h = Math.floor(seg / 3600);
    const m = Math.floor((seg % 3600) / 60);
    const s = seg % 60;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  pctClass(pct: number): string {
    if (pct > 0.5) return 'val-red';
    if (pct > 0.1) return 'val-orange';
    return 'val-green';
  }

  readonly tipoLabels: Record<number, string> = { 1: 'Directa', 2: 'Redundante', 3: 'Solo Backup' };

  // --- Colors (Vision UI palette) ---
  private readonly COL_CORTES = '#0075FF';
  private readonly COL_DATOS  = '#FF9966';
  private readonly COL_ACUM   = '#01B574';
  private readonly COL_UMBRAL = '#FF5E62';

  // --- Charts ---
  private readonly piePlugins: any = {
    datalabels: {
      display: true,
      color: '#fff',
      font: { weight: 'bold' as const, size: 13 },
      formatter: (value: number, ctx: any) => {
        const total = (ctx.dataset.data as number[]).reduce((a: number, b: number) => a + b, 0);
        if (!total || !value) return '';
        return (value / total * 100).toFixed(1) + '%';
      },
    },
  };

  pieMesData = signal<ChartData<'pie'>>({ labels: [], datasets: [] });
  pieMesOpts: ChartConfiguration<'pie'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#a0aec0', font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const val = ctx.parsed ?? 0;
            const total = (ctx.dataset.data as number[]).reduce((a, b) => a + b, 0);
            const pct = total ? (val / total * 100).toFixed(1) : '0';
            return `${ctx.label}: ${Math.round(val).toLocaleString('es-AR')} seg (${pct}%)`;
          },
        },
      },
      ...this.piePlugins,
    },
  };

  pieAnioMovilData = signal<ChartData<'pie'>>({ labels: [], datasets: [] });
  pieAnioMovilOpts: ChartConfiguration<'pie'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#a0aec0', font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const val = ctx.parsed ?? 0;
            const total = (ctx.dataset.data as number[]).reduce((a, b) => a + b, 0);
            const pct = total ? (val / total * 100).toFixed(1) : '0';
            return `${ctx.label}: ${Math.round(val).toLocaleString('es-AR')} seg (${pct}%)`;
          },
        },
      },
      ...this.piePlugins,
    },
  };

  chartDiarioData = signal<ChartData<'bar'>>({ labels: [], datasets: [] });
  chartDiarioOpts: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#a0aec0', font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => `${ctx.dataset.label}: ${Math.round(ctx.parsed.y ?? 0).toLocaleString('es-AR')} seg`,
        },
      },
      annotation: {
        annotations: {
          umbral: {
            type: 'line',
            yMin: 432,
            yMax: 432,
            borderColor: this.COL_UMBRAL,
            borderWidth: 2,
            borderDash: [6, 3],
            label: {
              display: true,
              content: '0.5% (432s)',
              position: 'end',
              backgroundColor: 'rgba(255,94,98,0.15)',
              color: this.COL_UMBRAL,
              font: { size: 10 },
            },
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: '#a0aec0', font: { size: 10, family: 'monospace' } },
        grid: { color: 'rgba(255,255,255,.04)' },
      },
      y: {
        stacked: true,
        ticks: { color: '#a0aec0', font: { size: 10 } },
        grid: { color: 'rgba(255,255,255,.06)' },
        title: { display: true, text: 'Segundos', color: '#a0aec0', font: { size: 11 } },
      },
    },
  };

  chartAnioMovilData = signal<ChartData<'bar'>>({ labels: [], datasets: [] });
  chartAnioMovilOpts: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#a0aec0', font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => `${ctx.dataset.label}: ${(ctx.parsed.y ?? 0).toFixed(4)}%`,
        },
      },
      annotation: {
        annotations: {
          umbral: {
            type: 'line',
            yMin: 0.5,
            yMax: 0.5,
            borderColor: this.COL_UMBRAL,
            borderWidth: 2,
            borderDash: [6, 3],
            label: {
              display: true,
              content: '0.5%',
              position: 'end',
              backgroundColor: 'rgba(255,94,98,0.15)',
              color: this.COL_UMBRAL,
              font: { size: 10 },
            },
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: '#a0aec0', font: { size: 10, family: 'monospace' } },
        grid: { color: 'rgba(255,255,255,.04)' },
      },
      y: {
        stacked: true,
        ticks: {
          color: '#a0aec0',
          font: { size: 10 },
          callback: (val) => val + '%',
        },
        grid: { color: 'rgba(255,255,255,.06)' },
        title: { display: true, text: '% Indisponibilidad', color: '#a0aec0', font: { size: 11 } },
      },
      yAcum: {
        position: 'right',
        grid: { drawOnChartArea: false },
        ticks: {
          color: this.COL_ACUM,
          font: { size: 10 },
          callback: (val) => val + '%',
        },
        title: { display: true, text: '% Acumulada', color: this.COL_ACUM, font: { size: 11 } },
      },
    },
  };

  private chartEffect = effect(() => {
    const r = this.ris();
    if (!r) return;

    const colCortes = this.COL_CORTES;
    const colDatos  = this.COL_DATOS;
    const colAcum   = this.COL_ACUM;

    // Pie: Distribución del Mes
    const cortesMes = Math.round(r.resumen_mes.ind_cortes_seg ?? 0);
    const datosMes = Math.round(r.resumen_mes.ind_datos_seg ?? 0);
    this.pieMesData.set({
      labels: ['Cortes', 'Datos Inválidos'],
      datasets: [{
        data: [cortesMes, datosMes],
        backgroundColor: [colCortes, colDatos],
        borderColor: ['rgba(0,117,255,0.3)', 'rgba(255,153,102,0.3)'],
        borderWidth: 1,
      }],
    });

    // Pie: Distribución del Año Móvil
    const cortesAM = Math.round(r.anio_movil.ind_cortes_seg ?? 0);
    const datosAM = Math.round(r.anio_movil.ind_datos_seg ?? 0);
    this.pieAnioMovilData.set({
      labels: ['Cortes', 'Datos Inválidos'],
      datasets: [{
        data: [cortesAM, datosAM],
        backgroundColor: [colCortes, colDatos],
        borderColor: ['rgba(0,117,255,0.3)', 'rgba(255,153,102,0.3)'],
        borderWidth: 1,
      }],
    });

    // Diario chart
    const labels = r.diario.map((d: any) => d.fecha.split('-')[2]);
    this.chartDiarioData.set({
      labels,
      datasets: [
        {
          label: 'Cortes',
          data: r.diario.map((d: any) => Math.round(d.ind_cortes_seg ?? 0)),
          backgroundColor: colCortes,
          borderRadius: 2,
        },
        {
          label: 'Datos Inválidos',
          data: r.diario.map((d: any) => Math.round(d.ind_datos_seg ?? 0)),
          backgroundColor: colDatos,
          borderRadius: 2,
        },
      ],
    });

    // Año Móvil chart (porcentajes + línea acumulada)
    const det = r.anio_movil.detalle || [];
    const amLabels = det.map((d: any) => this.formatMesCorto(d.mes));
    this.chartAnioMovilData.set({
      labels: amLabels,
      datasets: [
        {
          label: 'Cortes %',
          data: det.map((d: any) => d.ind_cortes_pct ?? 0),
          backgroundColor: colCortes,
          borderRadius: 3,
          stack: 'stack0',
          yAxisID: 'y',
        },
        {
          label: 'Datos Inv. %',
          data: det.map((d: any) => d.ind_datos_pct ?? 0),
          backgroundColor: colDatos,
          borderRadius: 3,
          stack: 'stack0',
          yAxisID: 'y',
        },
        {
          label: 'Ind. Acumulada',
          data: det.map((d: any) => d.ind_acum_pct ?? 0),
          type: 'line',
          borderColor: colAcum,
          backgroundColor: 'rgba(1,181,116,0.1)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: colAcum,
          fill: false,
          yAxisID: 'yAcum',
          stack: undefined,
        } as any,
      ],
    });
  });
}
