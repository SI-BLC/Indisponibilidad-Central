import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService, Cogb55CentralGrupos } from '../../services/api';

@Component({
  selector: 'app-cogb55',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule,
    MatSnackBarModule, MatProgressSpinnerModule, MatChipsModule, MatTooltipModule,
  ],
  templateUrl: './cogb55.html',
  styleUrl: './cogb55.scss',
})
export class Cogb55 implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snack = inject(MatSnackBar);

  asignaciones = signal<Cogb55CentralGrupos[]>([]);
  centralesDisponibles = signal<{id: number; nemo: string}[]>([]);
  gruposDisponibles = signal<number[]>([]);
  loading = signal(true);

  editandoId = signal<number | null>(null);
  editGrupos = signal<number[]>([]);

  form = this.fb.group({
    idCentral: [null as number | null, Validators.required],
    grupos: [[] as number[], Validators.required],
  });

  readonly displayedColumns = ['nemo', 'grupos', 'acciones'];

  ngOnInit() {
    this.cargar();
  }

  cargar() {
    this.loading.set(true);
    this.api.getCogb55().subscribe({
      next: (data) => {
        this.asignaciones.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
    this.api.getCogb55CentralesDisponibles().subscribe(c => this.centralesDisponibles.set(c));
    this.api.getCogb55GruposDisponibles().subscribe(g => this.gruposDisponibles.set(g));
  }

  agregar() {
    const v = this.form.value;
    if (!v.idCentral || !v.grupos?.length) return;
    this.api.setCogb55Grupos(v.idCentral, v.grupos).subscribe({
      next: () => {
        this.snack.open('Central asignada', 'OK', { duration: 3000 });
        this.form.reset();
        this.cargar();
      },
      error: () => this.snack.open('Error al asignar', 'OK', { duration: 4000 }),
    });
  }

  editarInicio(row: Cogb55CentralGrupos) {
    this.editandoId.set(row.id_central);
    this.editGrupos.set([...row.grupos]);
  }

  editarCancelar() {
    this.editandoId.set(null);
    this.editGrupos.set([]);
  }

  editarGuardar(row: Cogb55CentralGrupos) {
    const grupos = this.editGrupos();
    if (!grupos.length) return;
    this.api.setCogb55Grupos(row.id_central, grupos).subscribe({
      next: () => {
        this.snack.open('Grupos actualizados', 'OK', { duration: 3000 });
        this.editandoId.set(null);
        this.cargar();
      },
      error: () => this.snack.open('Error al actualizar', 'OK', { duration: 4000 }),
    });
  }

  eliminar(row: Cogb55CentralGrupos) {
    if (!confirm(`¿Eliminar la asignación de ${row.nemo}?`)) return;
    this.api.deleteCogb55(row.id_central).subscribe({
      next: () => {
        this.snack.open('Asignación eliminada', 'OK', { duration: 3000 });
        this.cargar();
      },
      error: () => this.snack.open('Error al eliminar', 'OK', { duration: 4000 }),
    });
  }

  todosLosGrupos(row: Cogb55CentralGrupos): number[] {
    return [...this.gruposDisponibles(), ...row.grupos].sort((a, b) => a - b);
  }
}
