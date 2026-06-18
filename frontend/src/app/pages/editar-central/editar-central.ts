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
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { Enlace, EnlaceCreate } from '../../models/enlace';

interface EnlaceObtenido {
  nombre: string;
  editando: boolean;
  nombreEdit: string;
  esNuevo: boolean;
}

@Component({
  selector: 'app-editar-central',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule, MatSnackBarModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './editar-central.html',
  styleUrl: './editar-central.scss',
})
export class EditarCentral implements OnInit {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);
  private readonly fb = inject(FormBuilder);

  centrales = signal<Central[]>([]);
  centralSeleccionada = signal<Central | null>(null);
  enlaces = signal<Enlace[]>([]);

  // Obtener enlaces
  ipCentral = '';
  loadingEnlaces = signal(false);
  enlacesObtenidos = signal<EnlaceObtenido[]>([]);

  // Eliminar central
  confirmandoEliminar = false;

  readonly tipos = [
    { value: 1, label: 'Tipo 1 — Directa' },
    { value: 2, label: 'Tipo 2 — Redundante' },
    { value: 3, label: 'Tipo 3 — Solo Backup' },
  ];
  readonly tipoLabels: Record<number, string> = { 1: 'Directa', 2: 'Redundante', 3: 'Solo Backup' };
  readonly enlaceColumns = ['id', 'nombre', 'idtipo', 'rol', 'acciones'];
  readonly rolesDisponibles = [
    { value: null,           label: '— sin rol —' },
    { value: 'directo',      label: 'Directo' },
    { value: 'concentrador', label: 'Concentrador' },
  ];

  formCentral = this.fb.group({
    nemo: ['', Validators.required],
    tipo: [null as number | null, Validators.required],
    protocolo: ['elcom', Validators.required],
    ip1: [''],
    ip2: [''],
  });

  formEnlace = this.fb.group({
    nombre: ['', Validators.required],
    idtipo: [null as number | null],
  });

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: (c) => this.centrales.set(c) });
  }

  seleccionar(central: Central) {
    this.centralSeleccionada.set(central);
    this.formCentral.patchValue({ nemo: central.nemo, tipo: central.tipo, protocolo: central.protocolo ?? 'elcom', ip1: central.ip1 ?? '', ip2: central.ip2 ?? '' });
    this.api.getEnlaces(central.id).subscribe({ next: (e) => this.enlaces.set(e) });
    this.confirmandoEliminar = false;
    this.enlacesObtenidos.set([]);
    this.ipCentral = central.ip1 ?? '';
  }

  guardarCentral() {
    const c = this.centralSeleccionada();
    if (!c || this.formCentral.invalid) return;
    const v = this.formCentral.value;
    this.api.actualizarCentral(c.id, { nemo: v.nemo!, tipo: v.tipo!, protocolo: v.protocolo!, ip1: v.ip1 || null, ip2: v.ip2 || null }).subscribe({
      next: (updated) => {
        this.centralSeleccionada.set(updated);
        this.centrales.update((list) => list.map((x) => (x.id === updated.id ? updated : x)));
        this.snack.open('Central actualizada', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al actualizar', 'OK', { duration: 3000 }),
    });
  }

  eliminarCentral() {
    const c = this.centralSeleccionada();
    if (!c) return;
    this.api.eliminarCentral(c.id).subscribe({
      next: () => {
        this.centrales.update((list) => list.filter((x) => x.id !== c.id));
        this.centralSeleccionada.set(null);
        this.enlaces.set([]);
        this.enlacesObtenidos.set([]);
        this.confirmandoEliminar = false;
        this.snack.open('Central eliminada', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al eliminar la central', 'OK', { duration: 3000 }),
    });
  }

  agregarEnlace() {
    const c = this.centralSeleccionada();
    if (!c || this.formEnlace.invalid) return;
    const v = this.formEnlace.value;
    const data: EnlaceCreate = { nombre: v.nombre!, idcentral: c.id, idtipo: v.idtipo ?? undefined };
    this.api.crearEnlace(data).subscribe({
      next: (e) => {
        this.enlaces.update((list) => [...list, e]);
        this.formEnlace.reset();
        this.snack.open('Enlace agregado', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al agregar enlace', 'OK', { duration: 3000 }),
    });
  }

  eliminarEnlace(id: number) {
    this.api.eliminarEnlace(id).subscribe({
      next: () => this.enlaces.update((list) => list.filter((e) => e.id !== id)),
      error: () => this.snack.open('Error al eliminar enlace', 'OK', { duration: 3000 }),
    });
  }

  cambiarRol(id: number, rol: string | null) {
    this.api.actualizarEnlace(id, { rol }).subscribe({
      next: (updated) => this.enlaces.update((list) => list.map((e) => (e.id === id ? updated : e))),
      error: () => this.snack.open('Error al actualizar rol', 'OK', { duration: 3000 }),
    });
  }

  // Obtener enlaces desde la central
  obtenerEnlaces() {
    if (!this.ipCentral) return;
    this.loadingEnlaces.set(true);
    this.enlacesObtenidos.set([]);
    this.api.checkEnlaces(this.ipCentral).subscribe({
      next: (raw) => {
        this.enlacesObtenidos.set(this.parseEnlacesRaw(raw));
        this.loadingEnlaces.set(false);
      },
      error: () => {
        this.snack.open('Error al obtener enlaces de la central', 'OK', { duration: 4000 });
        this.loadingEnlaces.set(false);
      },
    });
  }

  get nuevosCount() { return this.enlacesObtenidos().filter(e => e.esNuevo).length; }

  private parseEnlacesRaw(raw: string): EnlaceObtenido[] {
    try {
      const arr: string[] = JSON.parse(raw.trim());
      const existentes = new Set(this.enlaces().map(e => e.nombre.toUpperCase()));
      return arr.map(nombre => ({
        nombre,
        editando: false,
        nombreEdit: nombre,
        esNuevo: !existentes.has(nombre.toUpperCase()),
      }));
    } catch {
      this.snack.open('No se pudo interpretar la respuesta', 'OK', { duration: 3000 });
      return [];
    }
  }

  importarEnlace(index: number) {
    const c = this.centralSeleccionada();
    if (!c) return;
    const e = this.enlacesObtenidos()[index];
    this.api.crearEnlace({ nombre: e.nombre, idcentral: c.id }).subscribe({
      next: (created) => {
        this.enlaces.update(list => [...list, created]);
        this.enlacesObtenidos.update(list =>
          list.map((item, i) => i === index ? { ...item, esNuevo: false } : item)
        );
        this.snack.open(`"${e.nombre}" guardado`, 'OK', { duration: 2000 });
      },
      error: () => this.snack.open('Error al guardar enlace', 'OK', { duration: 3000 }),
    });
  }

  importarTodosNuevos() {
    const c = this.centralSeleccionada();
    if (!c) return;
    const nuevos = this.enlacesObtenidos()
      .map((e, i) => ({ ...e, i }))
      .filter(e => e.esNuevo);
    if (!nuevos.length) return;
    let done = 0;
    for (const { nombre, i } of nuevos) {
      this.api.crearEnlace({ nombre, idcentral: c.id }).subscribe({
        next: (created) => {
          done++;
          this.enlaces.update(list => [...list, created]);
          this.enlacesObtenidos.update(list =>
            list.map((item, idx) => idx === i ? { ...item, esNuevo: false } : item)
          );
          if (done === nuevos.length)
            this.snack.open(`${done} enlace(s) guardado(s)`, 'OK', { duration: 2500 });
        },
        error: () => { done++; },
      });
    }
  }

  iniciarEdicion(index: number) {
    this.enlacesObtenidos.update(list =>
      list.map((e, i) => i === index ? { ...e, editando: true, nombreEdit: e.nombre } : e)
    );
  }

  confirmarEdicion(index: number) {
    this.enlacesObtenidos.update(list =>
      list.map((e, i) => i === index ? { ...e, nombre: e.nombreEdit, editando: false } : e)
    );
  }

  cancelarEdicion(index: number) {
    this.enlacesObtenidos.update(list =>
      list.map((e, i) => i === index ? { ...e, editando: false } : e)
    );
  }

  actualizarNombreEdit(index: number, value: string) {
    this.enlacesObtenidos.update(list =>
      list.map((e, i) => i === index ? { ...e, nombreEdit: value } : e)
    );
  }

  eliminarEnlaceObtenido(index: number) {
    this.enlacesObtenidos.update(list => list.filter((_, i) => i !== index));
  }
}
