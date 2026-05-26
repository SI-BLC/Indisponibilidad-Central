import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { Enlace, Mantenimiento } from '../../models/enlace';

@Component({
  selector: 'app-mantenimientos',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule, MatSnackBarModule,
  ],
  templateUrl: './mantenimientos.html',
  styleUrl: './mantenimientos.scss',
})
export class Mantenimientos implements OnInit {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);
  private readonly fb = inject(FormBuilder);

  centrales = signal<Central[]>([]);
  enlaces = signal<Enlace[]>([]);
  mantenimientos = signal<Mantenimiento[]>([]);

  readonly tiposMant = [
    { value: 1, label: 'Enlace completo' },
    { value: 2, label: 'Ordinario (grupo)' },
    { value: 3, label: 'Eléctrico (grupo)' },
  ];
  readonly columns = ['enlace', 'tipo', 'inicio', 'fin', 'acciones'];

  form = this.fb.group({
    idCentral: [null as number | null, Validators.required],
    idEnlace: [null as number | null, Validators.required],
    tipo: [null as number | null, Validators.required],
    inicio: ['', Validators.required],
    fin: ['', Validators.required],
  });

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: (c) => this.centrales.set(c) });
  }

  onCentralChange(id: number) {
    this.form.patchValue({ idEnlace: null });
    this.api.getEnlaces(id).subscribe({ next: (e) => this.enlaces.set(e) });
  }

  onEnlaceChange(id: number) {
    this.api.getMantenimientos(id).subscribe({ next: (m) => this.mantenimientos.set(m) });
  }

  guardar() {
    if (this.form.invalid) return;
    const v = this.form.value;
    this.api.crearMantenimiento({
      idenlace: v.idEnlace!, tipo: v.tipo!,
      inicio: new Date(v.inicio!).toISOString(),
      fin: new Date(v.fin!).toISOString(),
    }).subscribe({
      next: (m) => {
        this.mantenimientos.update((list) => [...list, m]);
        this.form.patchValue({ inicio: '', fin: '', tipo: null });
        this.snack.open('Mantenimiento programado', 'OK', { duration: 3000 });
      },
      error: (e) => this.snack.open(e.error?.detail ?? 'Error', 'OK', { duration: 4000 }),
    });
  }

  eliminar(id: number) {
    this.api.eliminarMantenimiento(id).subscribe({
      next: () => this.mantenimientos.update((list) => list.filter((m) => m.id !== id)),
      error: () => this.snack.open('Error al eliminar', 'OK', { duration: 3000 }),
    });
  }

  tipoLabel(tipo: number): string {
    return this.tiposMant.find((t) => t.value === tipo)?.label ?? '';
  }

  tipoBadge(tipo: number): string {
    const map: Record<number, string> = { 1: 'badge-primary', 2: 'badge-warning', 3: 'badge-danger' };
    return map[tipo] ?? 'badge-muted';
  }
}
