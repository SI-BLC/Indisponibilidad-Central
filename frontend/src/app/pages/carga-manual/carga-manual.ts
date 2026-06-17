import { Component, inject, signal, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatChipsModule } from '@angular/material/chips';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { CargaManualResult } from '../../models/carga-manual';
import { ConfirmDialogComponent } from './confirm-dialog';

@Component({
  selector: 'app-carga-manual',
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDialogModule,
    MatChipsModule,
  ],
  templateUrl: './carga-manual.html',
  styleUrl: './carga-manual.scss',
})
export class CargaManual {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);

  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  readonly centralControl = new FormControl<number | null>(null);
  readonly centrales = signal<Central[]>([]);
  readonly archivosSeleccionados = signal<File[]>([]);
  readonly resultado = signal<CargaManualResult | null>(null);
  readonly cargando = signal(false);
  readonly confirmado = signal(false);

  ngOnInit() {
    this.api.getCentrales().subscribe(c => this.centrales.set(c));
  }

  onFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files) return;
    const files = Array.from(input.files).filter(
      f => f.name.endsWith('.con') || f.name.endsWith('.dat')
    );
    this.archivosSeleccionados.set(files);
    this.resultado.set(null);
    this.confirmado.set(false);
  }

  removeFile(index: number) {
    const current = [...this.archivosSeleccionados()];
    current.splice(index, 1);
    this.archivosSeleccionados.set(current);
    this.resultado.set(null);
    this.confirmado.set(false);
  }

  analizar() {
    const centralId = this.centralControl.value;
    if (!centralId || this.archivosSeleccionados().length === 0) return;

    this.cargando.set(true);
    this.resultado.set(null);
    this.confirmado.set(false);

    this.api.analizarCargaManual(centralId, this.archivosSeleccionados()).subscribe({
      next: (res) => {
        this.resultado.set(res);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }

  confirmar() {
    const res = this.resultado();
    const central = this.centrales().find(c => c.id === this.centralControl.value);
    if (!res || !central) return;

    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: { central: central.nemo, archivos: res.archivos, resumen: res.resumen },
      width: '480px',
    });

    ref.afterClosed().subscribe(ok => {
      if (!ok) return;
      this.cargando.set(true);
      this.api.confirmarCargaManual(central.id, this.archivosSeleccionados()).subscribe({
        next: (r) => {
          this.resultado.set(r);
          this.confirmado.set(true);
          this.cargando.set(false);
        },
        error: () => this.cargando.set(false),
      });
    });
  }

  get puedeAnalizar(): boolean {
    return !!this.centralControl.value && this.archivosSeleccionados().length > 0;
  }

  get puedeConfirmar(): boolean {
    const res = this.resultado();
    return (
      !!res &&
      !this.confirmado() &&
      (res.resumen.con_a_insertar + res.resumen.dat_a_insertar) > 0
    );
  }
}
