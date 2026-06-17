import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { ArchivoCargaInfo, ResumenCarga } from '../../models/carga-manual';

interface DialogData {
  central: string;
  archivos: ArchivoCargaInfo[];
  resumen: ResumenCarga;
}

@Component({
  selector: 'app-confirm-dialog',
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Confirmar carga</h2>
    <mat-dialog-content>
      <p>¿Confirmar la carga de <strong>{{ data.archivos.length }} archivo(s)</strong> para la central <strong>{{ data.central }}</strong>?</p>
      <div class="resumen">
        <div class="resumen-row"><span>CON a insertar:</span><strong>{{ data.resumen.con_a_insertar }}</strong></div>
        <div class="resumen-row"><span>DAT a insertar:</span><strong>{{ data.resumen.dat_a_insertar }}</strong></div>
        @if (data.resumen.con_duplicados > 0) {
          <div class="resumen-row warn"><span>CON duplicados (omitidos):</span><strong>{{ data.resumen.con_duplicados }}</strong></div>
        }
        @if (data.resumen.dat_duplicados > 0) {
          <div class="resumen-row warn"><span>DAT duplicados (omitidos):</span><strong>{{ data.resumen.dat_duplicados }}</strong></div>
        }
      </div>
      <p class="advertencia">Esta operación no se puede deshacer.</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="ref.close(false)">Cancelar</button>
      <button mat-flat-button color="primary" (click)="ref.close(true)">Confirmar carga</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .resumen { background: #f5f5f5; border-radius: 6px; padding: 12px 16px; margin: 12px 0; }
    .resumen-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: .9rem; }
    .resumen-row.warn strong { color: #e65100; }
    .advertencia { font-size: .8rem; color: #666; margin: 4px 0 0; }
  `],
})
export class ConfirmDialogComponent {
  constructor(
    public ref: MatDialogRef<ConfirmDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DialogData
  ) {}
}
