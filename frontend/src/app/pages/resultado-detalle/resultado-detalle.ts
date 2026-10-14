import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../services/api';
import { AuthService } from '../../services/auth.service';
import { DetalleCentral } from '../../models/resultado';
import { Comentario } from '../../models/comentario';

interface CorteEfectivo {
  enlace: string;
  inicio: string;
  fin: string;
  dur_seg: number;
  bajo_tolerancia: boolean;
}

@Component({
  selector: 'app-resultado-detalle',
  imports: [
    CommonModule, DecimalPipe, FormsModule, RouterLink,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule,
    MatSnackBarModule,
  ],
  templateUrl: './resultado-detalle.html',
  styleUrl:    './resultado-detalle.scss',
})
export class ResultadoDetalle implements OnInit {
  private readonly api    = inject(ApiService);
  private readonly auth   = inject(AuthService);
  private readonly route  = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly snack  = inject(MatSnackBar);

  centralId = 0;
  fecha     = '';
  loading   = signal(true);
  detalle   = signal<DetalleCentral | null>(null);
  error     = signal('');

  comentarios = signal<Comentario[]>([]);

  cortesSinCobertura = computed(() => {
    const d = this.detalle();
    if (!d) return [];
    return d.cortes_efectivos.filter(c => c.enlace === 'Sin cobertura');
  });

  // Dialog state
  dialogVisible = signal(false);
  dialogTipo    = '';
  dialogInicio  = '';
  dialogFin     = '';
  dialogFinEditable = false;
  dialogTexto   = '';
  dialogCortesSeleccionados: CorteEfectivo[] = [];
  dialogSaving  = signal(false);

  // Edit inline
  editandoId    = signal<number | null>(null);
  editTexto     = '';

  get currentUser() { return this.auth.currentUser()?.username ?? ''; }

  get comentariosCorte() { return this.comentarios().filter(c => c.tipo === 'corte'); }
  get comentariosDat()   { return this.comentarios().filter(c => c.tipo === 'dat'); }

  readonly DIA_SEG = 86400;

  ngOnInit() {
    this.centralId = Number(this.route.snapshot.paramMap.get('centralId'));
    this.fecha     = this.route.snapshot.paramMap.get('fecha') ?? '';
    this.cargar();
    this.cargarComentarios();
  }

  cargar() {
    this.loading.set(true);
    this.error.set('');
    this.api.getDetalleCentral(this.centralId, this.fecha).subscribe({
      next: (d) => { this.detalle.set(d); this.loading.set(false); },
      error: () => { this.error.set('No se pudo cargar el detalle.'); this.loading.set(false); },
    });
  }

  // ── Comentarios ───────────────────────────────────────────────────────────

  cargarComentarios() {
    this.api.listarComentarios(this.centralId, this.fecha).subscribe({
      next: (list) => this.comentarios.set(list),
      error: () => {},
    });
  }

  abrirDialogCorte(inicio: string, fin: string) {
    this.dialogTipo = 'corte';
    this.dialogInicio = inicio;
    this.dialogFin = fin;
    this.dialogFinEditable = false;
    this.dialogTexto = '';
    const sinCob = this.cortesSinCobertura();
    const match = sinCob.find(c => c.inicio === inicio && c.fin === fin);
    this.dialogCortesSeleccionados = match ? [match] : [];
    this.dialogVisible.set(true);
  }

  abrirDialogDat(inicio: string) {
    this.dialogTipo = 'dat';
    this.dialogInicio = inicio;
    this.dialogFin = '';
    this.dialogFinEditable = true;
    this.dialogTexto = '';
    this.dialogCortesSeleccionados = [];
    this.dialogVisible.set(true);
  }

  cerrarDialog() {
    this.dialogVisible.set(false);
  }

  isCorteSelected(c: CorteEfectivo): boolean {
    return this.dialogCortesSeleccionados.some(s => s.inicio === c.inicio && s.fin === c.fin);
  }

  toggleCorte(c: CorteEfectivo) {
    if (this.isCorteSelected(c)) {
      this.dialogCortesSeleccionados = this.dialogCortesSeleccionados.filter(
        s => !(s.inicio === c.inicio && s.fin === c.fin)
      );
    } else {
      this.dialogCortesSeleccionados = [...this.dialogCortesSeleccionados, c];
    }
  }

  guardarDialog() {
    const texto = this.dialogTexto.trim();
    if (!texto) return;
    if (this.dialogFinEditable && !this.dialogFin) return;
    this.dialogSaving.set(true);
    let fechaInicio = this.dialogInicio;
    let fechaFin = this.dialogFinEditable
      ? `${this.fecha}T${this.dialogFin}:00`
      : this.dialogFin;

    let duracionSeg: number | null = null;
    if (this.dialogTipo === 'corte' && this.dialogCortesSeleccionados.length > 0) {
      duracionSeg = this.dialogCortesSeleccionados.reduce((sum, c) => sum + c.dur_seg, 0);
      const inicios = this.dialogCortesSeleccionados.map(c => c.inicio).sort();
      const fines = this.dialogCortesSeleccionados.map(c => c.fin).sort();
      fechaInicio = inicios[0];
      fechaFin = fines[fines.length - 1];
    }

    this.api.crearComentario({
      id_central: this.centralId,
      fecha_dia: this.fecha,
      tipo: this.dialogTipo,
      duracion_seg: duracionSeg,
      fecha_inicio: fechaInicio,
      fecha_fin: fechaFin,
      texto,
    }).subscribe({
      next: (c) => {
        this.comentarios.update(list => [...list, c]);
        this.dialogVisible.set(false);
        this.dialogSaving.set(false);
        this.snack.open('Comentario guardado', 'OK', { duration: 3000 });
      },
      error: () => {
        this.dialogSaving.set(false);
        this.snack.open('Error al guardar', 'OK', { duration: 3000 });
      },
    });
  }

  iniciarEdicion(c: Comentario) {
    this.editandoId.set(c.id);
    this.editTexto = c.texto;
  }

  cancelarEdicion() {
    this.editandoId.set(null);
  }

  guardarEdicion(id: number) {
    const texto = this.editTexto.trim();
    if (!texto) return;
    this.api.actualizarComentario(id, texto).subscribe({
      next: (updated) => {
        this.comentarios.update(list => list.map(c => c.id === id ? updated : c));
        this.editandoId.set(null);
        this.snack.open('Comentario actualizado', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al actualizar', 'OK', { duration: 3000 }),
    });
  }

  eliminarComentario(id: number) {
    if (!confirm('¿Eliminar este comentario?')) return;
    this.api.eliminarComentario(id).subscribe({
      next: () => {
        this.comentarios.update(list => list.filter(c => c.id !== id));
        this.snack.open('Comentario eliminado', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al eliminar', 'OK', { duration: 3000 }),
    });
  }

  volver() {
    this.router.navigate(['/resultados']);
  }

  // ── Timeline helpers ──────────────────────────────────────────────────────

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
