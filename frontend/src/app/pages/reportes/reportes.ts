import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatButtonToggleModule, MatButtonToggleChange } from '@angular/material/button-toggle';
import { forkJoin } from 'rxjs';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { ReporteOut, CorteItem } from '../../models/reporte';
import { ReporteDialogComponent } from './reporte-dialog';

@Component({
  selector: 'app-reportes',
  providers: [provideNativeDateAdapter()],
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatSelectModule,
    MatInputModule, MatButtonModule, MatTableModule, MatIconModule,
    MatProgressSpinnerModule, MatDatepickerModule, MatButtonToggleModule,
  ],
  templateUrl: './reportes.html',
  styleUrl: './reportes.scss',
})
export class Reportes implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly dialog = inject(MatDialog);

  centrales = signal<Central[]>([]);
  reporte = signal<ReporteOut | null>(null);
  filteredCortes = signal<CorteItem[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  modo = signal<'libre' | '24h'>('libre');

  readonly displayedColumns = ['central', 'enlace', 'inicio', 'fin', 'duracion', 'tipo'];

  form = this.fb.group({
    idCentral: [null as number | null, Validators.required],
    fechaInicio: [null as Date | null, Validators.required],
    fechaFin: [null as Date | null, Validators.required],
  });

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: (c) => this.centrales.set(c) });
  }

  get formValido(): boolean {
    if (this.form.controls.idCentral.invalid || this.form.controls.fechaInicio.invalid) return false;
    if (this.modo() === 'libre' && this.form.controls.fechaFin.invalid) return false;
    return true;
  }

  onModoChange(event: MatButtonToggleChange) {
    this.modo.set(event.value);
  }

  generar() {
    if (!this.formValido) return;
    const v = this.form.value;

    const fechaInicioDate = new Date(v.fechaInicio!);
    fechaInicioDate.setHours(0, 0, 0, 0);

    let fechaFinDate: Date;
    if (this.modo() === '24h') {
      fechaFinDate = new Date(fechaInicioDate);
      fechaFinDate.setDate(fechaFinDate.getDate() + 1);
    } else {
      fechaFinDate = new Date(v.fechaFin!);
      fechaFinDate.setHours(0, 0, 0, 0);
    }

    const req = {
      idCentral: v.idCentral!,
      fechaInicio: fechaInicioDate.toISOString(),
      fechaFin: fechaFinDate.toISOString(),
    };

    this.loading.set(true);
    this.error.set(null);
    this.reporte.set(null);
    this.filteredCortes.set([]);

    forkJoin({
      reporte: this.api.generarReporte(req),
      txt: this.api.generarReporteTxt(req),
    }).subscribe({
      next: ({ reporte, txt }) => {
        this.reporte.set(reporte);
        this.filteredCortes.set(this.computeFilteredCortes(reporte));
        this.loading.set(false);

        const fechaIni = fechaInicioDate.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const fechaFin = fechaFinDate.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const nombreArchivo = `${reporte.nemo} [${fechaIni} a ${fechaFin}].txt`;

        this.dialog.open(ReporteDialogComponent, {
          data: { texto: txt, nombreArchivo },
          maxWidth: '90vw',
          maxHeight: '90vh',
        });
      },
      error: (e) => { this.error.set(e.error?.detail ?? 'Error al generar reporte.'); this.loading.set(false); },
    });
  }

  private computeFilteredCortes(r: ReporteOut): CorteItem[] {
    if (r.tipo_central === 1) {
      // Directa: solo enlaces con patrón *_CAM (excluye *_CAMM)
      return r.cortes.filter(c => {
        const n = c.nombre_enlace.toUpperCase();
        return n.includes('_CAM') && !n.includes('_CAMM');
      });
    } else if (r.tipo_central === 2 || r.tipo_central === 3) {
      // Redundante / Solo-backup: enlaces *_CAMM, *_BCOG, BCOG_* y "Redundante"
      return r.cortes.filter(c => {
        const n = c.nombre_enlace.toUpperCase();
        return n.includes('_CAMM') || n.includes('_BCOG') || n.startsWith('BCOG_') || n === 'REDUNDANTE';
      });
    }
    return r.cortes;
  }

  tipoCentralLabel(tipo: number | null): string {
    switch (tipo) {
      case 1: return 'Directa';
      case 2: return 'Redundante';
      case 3: return 'Solo Backup';
      default: return '';
    }
  }

  formatMinutos(min: number): string {
    const h = Math.floor(min / 60);
    const m = Math.round(min % 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  cortesReales(r: ReporteOut): number {
    return r.cortes.filter(c => !c.es_mantenimiento).length;
  }

  cortesMant(r: ReporteOut): number {
    return r.cortes.filter(c => c.es_mantenimiento).length;
  }
}
