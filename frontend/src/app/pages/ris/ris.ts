import { Component, inject, signal, computed, effect, ElementRef } from '@angular/core';
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
import { ThemeService } from '../../services/theme';
import { Central } from '../../models/central';
import html2canvas from 'html2canvas';
import { generateRisPdf, loadPdfAssets, SectionCapture } from './ris-pdf';

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
  private readonly theme = inject(ThemeService);
  private readonly elRef = inject(ElementRef);

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

  validacion = signal<any>(null);
  editandoValidacion = signal(false);
  validacionComentario = signal('');
  guardandoValidacion = signal(false);

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
    this.validacion.set(null);
    this.editandoValidacion.set(false);
    this.api.getRis(c.id, m).subscribe({
      next: data => { this.ris.set(data); this.loading.set(false); },
      error: () => { this.loading.set(false); },
    });
    this.api.getValidacionRis(c.id, m).subscribe({
      next: v => this.validacion.set(v),
    });
  }

  onMesChange() { this.cargar(); }

  abrirValidacion() {
    this.validacionComentario.set(this.validacion()?.comentario || '');
    this.editandoValidacion.set(true);
  }

  guardarValidacion() {
    const c = this.centralSeleccionada();
    const m = this.mesSeleccionado();
    if (!c || !m) return;
    this.guardandoValidacion.set(true);
    const nuevoEstado = !this.validacion()?.validado;
    this.api.setValidacionRis(c.id, m, nuevoEstado, this.validacionComentario() || null).subscribe({
      next: v => {
        this.validacion.set(v);
        this.editandoValidacion.set(false);
        this.guardandoValidacion.set(false);
      },
      error: () => { this.guardandoValidacion.set(false); },
    });
  }

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

  private readonly COL_CORTES = '#4B8BD4';
  private readonly COL_DATOS  = '#E0874A';
  private readonly COL_ACUM   = '#7CCBA2';
  private readonly COL_UMBRAL = '#E06070';

  private cc = computed(() => {
    const dark = this.theme.isDark();
    return {
      tick: dark ? '#6b728a' : '#8a90a6',
      grid: dark ? 'rgba(255,255,255,.05)' : 'rgba(0,0,0,.06)',
      axBorder: dark ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.08)',
      surface: dark ? '#131720' : '#ffffff',
      text1: dark ? '#e3e5ef' : '#1a1d26',
      tooltipBg: dark ? 'rgba(15,18,28,.92)' : 'rgba(255,255,255,.95)',
      tooltipTitle: dark ? '#c8ccd8' : '#2d3142',
      tooltipBody: dark ? '#a0a6bc' : '#5c6378',
      tooltipBorder: dark ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.1)',
      legend: dark ? '#8a90a6' : '#6b728a',
      annotBg: dark ? 'rgba(224,96,112,.12)' : 'rgba(224,96,112,.15)',
    };
  });

  private pieTooltipCb = {
    label: (ctx: any) => {
      const val = ctx.parsed ?? 0;
      const total = (ctx.dataset.data as number[]).reduce((a: number, b: number) => a + b, 0);
      const pct = total ? (val / total * 100).toFixed(1) : '0';
      return ` ${ctx.label}: ${Math.round(val).toLocaleString('es-AR')} seg (${pct}%)`;
    },
  };

  private buildDoughnutOpts(c: any): ChartConfiguration<'doughnut'>['options'] {
    return {
      responsive: true, maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: {
            color: c.legend, font: { size: 11 },
            usePointStyle: true, pointStyle: 'circle', padding: 16,
            generateLabels: (chart: any) => {
              const ds = chart.data.datasets?.[0];
              if (!ds) return [];
              const total = (ds.data as number[]).reduce((a: number, b: number) => a + b, 0);
              return (chart.data.labels || []).map((label: string, i: number) => {
                const val = ds.data[i] ?? 0;
                const pct = total ? (val / total * 100).toFixed(1) : '0';
                return {
                  text: `${label}: ${pct}%`,
                  fontColor: c.legend,
                  fillStyle: ds.backgroundColor?.[i],
                  strokeStyle: ds.backgroundColor?.[i],
                  hidden: false,
                  index: i,
                  pointStyle: 'circle' as const,
                };
              });
            },
          },
        },
        tooltip: {
          backgroundColor: c.tooltipBg, titleColor: c.tooltipTitle, bodyColor: c.tooltipBody,
          borderColor: c.tooltipBorder, borderWidth: 1, cornerRadius: 6, padding: 10,
          titleFont: { size: 12, weight: 600 }, bodyFont: { size: 11 },
          callbacks: this.pieTooltipCb,
        },
        datalabels: { display: false },
      },
    };
  }

  pieMesData = signal<ChartData<'doughnut'>>({ labels: [], datasets: [] });
  pieMesOpts = computed(() => this.buildDoughnutOpts(this.cc()));

  pieAnioMovilData = signal<ChartData<'doughnut'>>({ labels: [], datasets: [] });
  pieAnioMovilOpts = computed(() => this.buildDoughnutOpts(this.cc()));

  chartDiarioData = signal<ChartData<'bar'>>({ labels: [], datasets: [] });
  chartDiarioOpts = computed((): ChartConfiguration<'bar'>['options'] => {
    const c = this.cc();
    return {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: c.legend, font: { size: 11 }, usePointStyle: true, pointStyle: 'circle', padding: 16 },
        },
        tooltip: {
          backgroundColor: c.tooltipBg, titleColor: c.tooltipTitle, bodyColor: c.tooltipBody,
          borderColor: c.tooltipBorder, borderWidth: 1, cornerRadius: 6, padding: 10,
          titleFont: { size: 12, weight: 600 }, bodyFont: { size: 11 },
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${Math.round(ctx.parsed.y ?? 0).toLocaleString('es-AR')} seg`,
          },
        },
        annotation: {
          annotations: {
            umbral: {
              type: 'line', yMin: 432, yMax: 432,
              borderColor: this.COL_UMBRAL, borderWidth: 1.5, borderDash: [6, 4],
              label: {
                display: true, content: '0.5% (432s)', position: 'end',
                backgroundColor: c.annotBg, color: this.COL_UMBRAL,
                font: { size: 10 }, padding: 4,
              },
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true, border: { color: c.axBorder },
          ticks: { color: c.tick, font: { size: 10, family: 'monospace' } },
          grid: { color: c.grid },
        },
        y: {
          stacked: true, border: { color: c.axBorder },
          ticks: { color: c.tick, font: { size: 10 } },
          grid: { color: c.grid },
          title: { display: true, text: 'Segundos', color: c.tick, font: { size: 11 } },
        },
      },
    };
  });

  chartAnioMovilData = signal<ChartData<'bar'>>({ labels: [], datasets: [] });
  chartAnioMovilOpts = computed((): ChartConfiguration<'bar'>['options'] => {
    const c = this.cc();
    return {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: c.legend, font: { size: 11 }, usePointStyle: true, pointStyle: 'circle', padding: 16 },
        },
        tooltip: {
          backgroundColor: c.tooltipBg, titleColor: c.tooltipTitle, bodyColor: c.tooltipBody,
          borderColor: c.tooltipBorder, borderWidth: 1, cornerRadius: 6, padding: 10,
          titleFont: { size: 12, weight: 600 }, bodyFont: { size: 11 },
          callbacks: {
            label: (ctx: any) => {
              const v = ctx.parsed.y ?? 0;
              if (ctx.dataset.yAxisID === 'yAcum') return ` ${ctx.dataset.label}: ${v.toFixed(4)}%`;
              return ` ${ctx.dataset.label}: ${Math.round(v).toLocaleString('es-AR')} seg`;
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true, border: { color: c.axBorder },
          ticks: { color: c.tick, font: { size: 10, family: 'monospace' } },
          grid: { color: c.grid },
        },
        y: {
          stacked: true, border: { color: c.axBorder },
          ticks: { color: c.tick, font: { size: 10 } },
          grid: { color: c.grid },
          title: { display: true, text: 'Segundos', color: c.tick, font: { size: 11 } },
        },
        yAcum: {
          position: 'right',
          border: { color: c.axBorder },
          grid: { drawOnChartArea: false },
          ticks: { color: this.COL_ACUM, font: { size: 10 }, callback: (val) => val + '%' },
          title: { display: true, text: '% Acumulada', color: this.COL_ACUM, font: { size: 11 } },
        },
      },
    };
  });

  generandoPdf = signal(false);

  async descargarPdf() {
    const r = this.ris();
    if (!r) return;
    this.generandoPdf.set(true);
    try {
      const assets = await loadPdfAssets();
      const container = this.elRef.nativeElement as HTMLElement;
      const bgColor = getComputedStyle(document.body).backgroundColor;

      const selectors = [
        '.kpi-row', '.charts-row',
        '.seccion-header', '.resumen-panel', '.nota-panel',
        '.tabla-panel-cortes', '.tabla-panel-datos',
        '.grid-panel', '.anexo-panel',
      ];
      const breakBeforeSelectors = new Set(['.tabla-panel-cortes']);
      const elements: HTMLElement[] = [];
      const pageBreaks = new Set<number>();
      for (const sel of selectors) {
        container.querySelectorAll(sel).forEach(el => {
          if (breakBeforeSelectors.has(sel)) pageBreaks.add(elements.length);
          elements.push(el as HTMLElement);
        });
      }

      const sections: SectionCapture[] = [];
      for (const el of elements) {
        const canvas = await html2canvas(el, {
          scale: 2,
          backgroundColor: null,
          useCORS: true,
          logging: false,
        });
        sections.push({
          dataUrl: canvas.toDataURL('image/png'),
          width: canvas.width,
          height: canvas.height,
        });
      }

      generateRisPdf(r, sections, assets, bgColor, pageBreaks);
    } finally {
      this.generandoPdf.set(false);
    }
  }

  private chartEffect = effect(() => {
    const r = this.ris();
    if (!r) return;

    const c = this.cc();
    const colCortes = this.COL_CORTES;
    const colDatos  = this.COL_DATOS;
    const colAcum   = this.COL_ACUM;

    const cortesMes = Math.round(r.resumen_mes.ind_cortes_seg ?? 0);
    const datosMes = Math.round(r.resumen_mes.ind_datos_seg ?? 0);
    this.pieMesData.set({
      labels: ['Cortes', 'Datos Inválidos'],
      datasets: [{
        data: [cortesMes, datosMes],
        backgroundColor: [colCortes, colDatos],
        borderColor: c.surface,
        borderWidth: 2,
        hoverBorderColor: c.text1,
        hoverBorderWidth: 2,
        hoverOffset: 6,
      }],
    });

    const cortesAM = Math.round(r.anio_movil.ind_cortes_seg ?? 0);
    const datosAM = Math.round(r.anio_movil.ind_datos_seg ?? 0);
    this.pieAnioMovilData.set({
      labels: ['Cortes', 'Datos Inválidos'],
      datasets: [{
        data: [cortesAM, datosAM],
        backgroundColor: [colCortes, colDatos],
        borderColor: c.surface,
        borderWidth: 2,
        hoverBorderColor: c.text1,
        hoverBorderWidth: 2,
        hoverOffset: 6,
      }],
    });

    const labels = r.diario.map((d: any) => d.fecha.split('-')[2]);
    this.chartDiarioData.set({
      labels,
      datasets: [
        {
          label: 'Cortes',
          data: r.diario.map((d: any) => Math.round(d.ind_cortes_seg ?? 0)),
          backgroundColor: colCortes,
          hoverBackgroundColor: '#6AABE2',
          borderRadius: 4,
          borderSkipped: false,
        },
        {
          label: 'Datos Inválidos',
          data: r.diario.map((d: any) => Math.round(d.ind_datos_seg ?? 0)),
          backgroundColor: colDatos,
          hoverBackgroundColor: '#ECA46E',
          borderRadius: 4,
          borderSkipped: false,
        },
      ],
    });

    const det = r.anio_movil.detalle || [];
    const amLabels = det.map((d: any) => this.formatMesCorto(d.mes));
    this.chartAnioMovilData.set({
      labels: amLabels,
      datasets: [
        {
          label: 'Cortes',
          data: det.map((d: any) => Math.round(d.ind_cortes_seg ?? 0)),
          backgroundColor: colCortes,
          hoverBackgroundColor: '#6AABE2',
          borderRadius: 4,
          borderSkipped: false,
          stack: 'stack0',
          yAxisID: 'y',
        },
        {
          label: 'Datos Inv.',
          data: det.map((d: any) => Math.round(d.ind_datos_seg ?? 0)),
          backgroundColor: colDatos,
          hoverBackgroundColor: '#ECA46E',
          borderRadius: 4,
          borderSkipped: false,
          stack: 'stack0',
          yAxisID: 'y',
        },
        {
          label: 'Ind. Acumulada',
          data: det.map((d: any) => d.ind_acum_pct ?? 0),
          type: 'line',
          borderColor: colAcum,
          backgroundColor: 'rgba(124,203,162,0.08)',
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: c.surface,
          pointBorderColor: colAcum,
          pointBorderWidth: 2,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: colAcum,
          fill: true,
          tension: 0.3,
          yAxisID: 'yAcum',
          stack: undefined,
        } as any,
      ],
    });
  });
}
