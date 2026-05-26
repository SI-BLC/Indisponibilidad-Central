import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

export interface ReporteDialogData {
  texto: string;
  nombreArchivo: string;
}

@Component({
  selector: 'app-reporte-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>Reporte Generado</h2>
    <mat-dialog-content>
      <pre class="reporte-txt">{{ data.texto }}</pre>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-flat-button color="primary" (click)="descargar()">
        <mat-icon>download</mat-icon> Descargar .txt
      </button>
      <button mat-button mat-dialog-close>Cerrar</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .reporte-txt {
      font-family: monospace;
      font-size: 0.85rem;
      white-space: pre;
      background: #0d1117;
      color: #e3e5ef;
      padding: 16px;
      border-radius: 8px;
      max-height: 60vh;
      min-width: 620px;
      overflow: auto;
      margin: 0;
    }
    mat-dialog-content { padding: 0 24px 8px !important; }
    mat-dialog-actions { padding: 8px 24px 16px !important; gap: 8px; }
  `],
})
export class ReporteDialogComponent {
  readonly data = inject<ReporteDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<ReporteDialogComponent>);

  descargar(): void {
    const blob = new Blob([this.data.texto], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = this.data.nombreArchivo;
    a.click();
    URL.revokeObjectURL(url);
  }
}
