import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { Enlace, Grupo, TransferSet } from '../../models/enlace';

interface GrupoCentral {
  grupo: number;
  tipo: number;
  periodico: number;
  periodo: number;
  direccion: number;
  calcular: number;
  esNuevo: boolean;
}

@Component({
  selector: 'app-gestion-datos',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule, MatTooltipModule,
    MatSnackBarModule, MatProgressSpinnerModule, MatCheckboxModule,
  ],
  templateUrl: './gestion-datos.html',
  styleUrl: './gestion-datos.scss',
})
export class GestionDatos implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snack = inject(MatSnackBar);

  centrales = signal<Central[]>([]);
  enlaces = signal<Enlace[]>([]);
  grupos = signal<Grupo[]>([]);
  editandoId = signal<number | null>(null);

  centralSeleccionada = signal<Central | null>(null);
  enlaceSeleccionado = signal<Enlace | null>(null);
  gruposCentral = signal<GrupoCentral[]>([]);
  loadingGruposCentral = signal(false);
  editandoGrupoCentralIdx = signal<number | null>(null);

  // ICCP TransferSets
  transferSets = signal<TransferSet[]>([]);
  editandoTsId = signal<number | null>(null);

  get esIccp() { return this.centralSeleccionada()?.protocolo === 'iccp'; }

  readonly grupoColumns = ['id', 'grupo', 'tipo', 'periodico', 'periodo', 'direccion', 'calcular', 'acciones'];
  readonly gcColumns = ['grupo', 'tipo', 'periodico', 'periodo', 'direccion', 'calcular', 'estado', 'acciones'];
  readonly tsColumns = ['ts_nombre', 'tipo', 'calcular', 'acciones'];

  form = this.fb.group({
    idCentral: [null as number | null, Validators.required],
    idEnlace:  [null as number | null, Validators.required],
  });

  formGrupo = this.fb.group({
    grupo:    [null as number | null, Validators.required],
    tipo:     [0],
    periodico:[0],
    periodo:  [0],
    direccion:[0],
    calcular: [1],
  });

  formEditar = this.fb.group({
    grupo:    [null as number | null, Validators.required],
    tipo:     [0],
    periodico:[0],
    periodo:  [0],
    direccion:[0],
    calcular: [1],
  });

  // Formulario para editar un grupo obtenido de la central (antes de guardarlo)
  formGrupoCentral = this.fb.group({
    tipo:     [0],
    periodico:[0],
    periodo:  [0],
    direccion:[0],
    calcular: [1],
  });

  // ICCP TransferSet forms
  formTs = this.fb.group({
    ts_nombre: ['', Validators.required],
    tipo:      [0],
    calcular:  [1],
  });

  formTsEditar = this.fb.group({
    ts_nombre: ['', Validators.required],
    tipo:      [0],
    calcular:  [1],
  });

  get nuevosGruposCount() { return this.gruposCentral().filter(g => g.esNuevo).length; }

  ngOnInit() {
    this.api.getCentrales().subscribe({ next: (c) => this.centrales.set(c) });
  }

  onCentralChange(id: number) {
    this.form.patchValue({ idEnlace: null });
    this.grupos.set([]);
    this.gruposCentral.set([]);
    this.editandoId.set(null);
    this.editandoGrupoCentralIdx.set(null);
    this.enlaceSeleccionado.set(null);
    this.centralSeleccionada.set(this.centrales().find(c => c.id === id) ?? null);
    this.api.getEnlaces(id).subscribe({ next: (e) => this.enlaces.set(e) });
  }

  onEnlaceChange(id: number) {
    this.editandoId.set(null);
    this.gruposCentral.set([]);
    this.editandoGrupoCentralIdx.set(null);
    this.editandoTsId.set(null);
    this.enlaceSeleccionado.set(this.enlaces().find(e => e.id === id) ?? null);
    if (this.esIccp) {
      this.api.getTransferSets(id).subscribe({ next: (ts) => this.transferSets.set(ts) });
    } else {
      this.api.getGrupos(id).subscribe({ next: (g) => this.grupos.set(g) });
    }
  }

  // ─── Obtener grupos desde la central ────────────────────────────────────────

  obtenerGruposDeCentral() {
    const central = this.centralSeleccionada();
    const enlace  = this.enlaceSeleccionado();
    const ip = central?.ip1;
    if (!ip || !enlace) return;

    this.loadingGruposCentral.set(true);
    this.gruposCentral.set([]);
    this.editandoGrupoCentralIdx.set(null);
    this.api.checkGrupos(ip, enlace.nombre).subscribe({
      next: (raw) => {
        console.log('[GestionDatos] raw response:', raw);
        const grupos = this.parseGruposRaw(raw, enlace.nombre);
        console.log('[GestionDatos] grupos parseados:', grupos);
        this.gruposCentral.set(grupos);
        this.loadingGruposCentral.set(false);
      },
      error: (err: unknown) => {
        console.error('[GestionDatos] error HTTP:', err);
        this.snack.open('Error al obtener grupos de la central', 'OK', { duration: 4000 });
        this.loadingGruposCentral.set(false);
      },
    });
  }

  private parseGruposRaw(raw: string, enlaceNombre: string): GrupoCentral[] {
    try {
      // Normalizar: la central puede responder con comillas simples (Python-style)
      const normalized = raw.trim().replace(/'/g, '"');
      console.log('[GestionDatos] normalized:', normalized.slice(0, 200));
      let parsed: unknown;
      try {
        parsed = JSON.parse(normalized);
        console.log('[GestionDatos] parsed OK (normalized)');
      } catch (e1) {
        console.warn('[GestionDatos] JSON.parse(normalized) falló, intentando raw:', e1);
        parsed = JSON.parse(raw.trim());
        console.log('[GestionDatos] parsed OK (raw)');
      }

      console.log('[GestionDatos] tipo:', Array.isArray(parsed) ? 'array' : typeof parsed);
      if (!Array.isArray(parsed)) return [];

      console.log('[GestionDatos] entradas en parsed:', parsed.length);
      const existentes = new Set(this.grupos().map(g => g.grupo));
      const resultado: GrupoCentral[] = [];
      const seen = new Set<number>();

      for (const entry of parsed) {
        if (!Array.isArray(entry) || entry.length < 2) {
          console.warn('[GestionDatos] entrada no es par [nombre, filas]:', entry);
          continue;
        }
        const [nombre, filas] = entry as [unknown, unknown];
        console.log('[GestionDatos] enlace en respuesta:', JSON.stringify(nombre), '| buscando:', enlaceNombre);
        // Nota: el nombre del enlace en la respuesta puede diferir del configurado localmente
        // (el nodo puede tener un nombre hardcodeado distinto). Se procesan igualmente.
        if (!Array.isArray(filas)) {
          console.warn('[GestionDatos] filas no es array:', filas);
          continue;
        }

        console.log('[GestionDatos] filas encontradas:', filas.length);
        for (const fila of filas as unknown[]) {
          if (!Array.isArray(fila)) continue;
          const row = fila as string[];
          const num = parseInt(String(row[1]));
          if (isNaN(num) || seen.has(num)) continue;
          seen.add(num);
          const periodo = parseInt(String(row[3])) || 0;
          resultado.push({
            grupo:    num,
            tipo:     row[2] === 'r' ? 1 : 0,
            periodico:periodo > 0 ? 1 : 0,
            periodo,
            direccion:parseInt(String(row[4])) || 0,
            calcular: 1,
            esNuevo:  !existentes.has(num),
          });
        }
      }
      console.log('[GestionDatos] resultado final:', resultado.length, 'grupos');
      return resultado;
    } catch (e) {
      console.error('[GestionDatos] error parseando respuesta:', e);
      this.snack.open('No se pudo interpretar la respuesta de la central', 'OK', { duration: 3000 });
      return [];
    }
  }

  importarGrupo(gc: GrupoCentral, index: number) {
    const idEnlace = this.form.value.idEnlace;
    if (!idEnlace) return;
    this.api.crearGrupo({
      idenlace: idEnlace,
      grupo: gc.grupo, tipo: gc.tipo, periodico: gc.periodico,
      periodo: gc.periodo, direccion: gc.direccion, calcular: gc.calcular,
    }).subscribe({
      next: (g) => {
        this.grupos.update(list => [...list, g]);
        this.gruposCentral.update(list =>
          list.map((item, i) => i === index ? { ...item, esNuevo: false } : item)
        );
        this.snack.open(`Grupo ${gc.grupo} guardado`, 'OK', { duration: 2000 });
      },
      error: () => this.snack.open('Error al guardar grupo', 'OK', { duration: 3000 }),
    });
  }

  importarTodos() {
    const idEnlace = this.form.value.idEnlace;
    if (!idEnlace) return;
    const nuevos = this.gruposCentral()
      .map((gc, i) => ({ ...gc, i }))
      .filter(gc => gc.esNuevo);
    if (!nuevos.length) return;
    let done = 0;
    for (const gc of nuevos) {
      this.api.crearGrupo({
        idenlace: idEnlace,
        grupo: gc.grupo, tipo: gc.tipo, periodico: gc.periodico,
        periodo: gc.periodo, direccion: gc.direccion, calcular: gc.calcular,
      }).subscribe({
        next: (created) => {
          done++;
          this.grupos.update(list => [...list, created]);
          this.gruposCentral.update(list =>
            list.map((item, idx) => idx === gc.i ? { ...item, esNuevo: false } : item)
          );
          if (done === nuevos.length)
            this.snack.open(`${done} grupo(s) guardado(s)`, 'OK', { duration: 2500 });
        },
        error: () => { done++; },
      });
    }
  }

  iniciarEdicionGrupoCentral(index: number) {
    const gc = this.gruposCentral()[index];
    this.editandoGrupoCentralIdx.set(index);
    this.formGrupoCentral.setValue({
      tipo: gc.tipo, periodico: gc.periodico, periodo: gc.periodo,
      direccion: gc.direccion, calcular: gc.calcular,
    });
  }

  guardarEdicionGrupoCentral(index: number) {
    const v = this.formGrupoCentral.value;
    this.gruposCentral.update(list =>
      list.map((item, i) => i === index ? {
        ...item,
        tipo:     v.tipo      ?? 0,
        periodico:v.periodico ?? 0,
        periodo:  v.periodo   ?? 0,
        direccion:v.direccion ?? 0,
        calcular: v.calcular  ?? 1,
      } : item)
    );
    this.editandoGrupoCentralIdx.set(null);
  }

  cancelarEdicionGrupoCentral() {
    this.editandoGrupoCentralIdx.set(null);
  }

  eliminarGrupoCentral(index: number) {
    if (this.editandoGrupoCentralIdx() === index) this.editandoGrupoCentralIdx.set(null);
    this.gruposCentral.update(list => list.filter((_, i) => i !== index));
  }

  // ─── CRUD grupos en DB ───────────────────────────────────────────────────────

  agregarGrupo() {
    const idEnlace = this.form.value.idEnlace;
    if (!idEnlace || this.formGrupo.invalid) return;
    const v = this.formGrupo.value;
    this.api.crearGrupo({
      idenlace:  idEnlace,
      grupo:     v.grupo!,
      tipo:      v.tipo      ?? 0,
      periodico: v.periodico ?? 0,
      periodo:   v.periodo   ?? 0,
      direccion: v.direccion ?? 0,
      calcular:  v.calcular  ?? 1,
    }).subscribe({
      next: (g) => {
        this.grupos.update((list) => [...list, g]);
        this.formGrupo.reset({ tipo: 0, periodico: 0, periodo: 0, direccion: 0, calcular: 1 });
      },
    });
  }

  editarGrupo(g: Grupo) {
    this.editandoId.set(g.id);
    this.formEditar.setValue({
      grupo:     g.grupo,
      tipo:      g.tipo,
      periodico: g.periodico,
      periodo:   g.periodo,
      direccion: g.direccion,
      calcular:  g.calcular ?? 1,
    });
  }

  cancelarEdicion() { this.editandoId.set(null); }

  guardarEdicion(id: number) {
    if (this.formEditar.invalid) return;
    const v = this.formEditar.value;
    this.api.actualizarGrupo(id, {
      grupo:     v.grupo!,
      tipo:      v.tipo      ?? 0,
      periodico: v.periodico ?? 0,
      periodo:   v.periodo   ?? 0,
      direccion: v.direccion ?? 0,
      calcular:  v.calcular  ?? 1,
    }).subscribe({
      next: (updated) => {
        this.grupos.update((list) => list.map((g) => g.id === id ? updated : g));
        this.editandoId.set(null);
      },
    });
  }

  eliminarGrupo(id: number) {
    this.api.eliminarGrupo(id).subscribe({
      next: () => this.grupos.update((list) => list.filter((g) => g.id !== id)),
    });
  }

  // ─── ICCP TransferSets ────────────────────────────────────────────────────────

  crearTsDefaults() {
    const idEnlace = this.form.value.idEnlace;
    if (!idEnlace) return;
    this.api.crearTransferSetsDefaults(idEnlace).subscribe({
      next: (created) => {
        this.transferSets.update(list => [...list, ...created]);
        this.snack.open(`${created.length} TransferSet(s) creados`, 'OK', { duration: 2500 });
      },
      error: () => this.snack.open('Error al crear TransferSets', 'OK', { duration: 3000 }),
    });
  }

  agregarTs() {
    const idEnlace = this.form.value.idEnlace;
    if (!idEnlace || this.formTs.invalid) return;
    const v = this.formTs.value;
    this.api.crearTransferSet({
      id_enlace: idEnlace,
      ts_nombre: v.ts_nombre!,
      tipo: v.tipo ?? 0,
      calcular: v.calcular ?? 1,
    }).subscribe({
      next: (ts) => {
        this.transferSets.update(list => [...list, ts]);
        this.formTs.reset({ tipo: 0, calcular: 1 });
      },
      error: (e) => this.snack.open(e.error?.detail ?? 'Error al crear TransferSet', 'OK', { duration: 3000 }),
    });
  }

  editarTs(ts: TransferSet) {
    this.editandoTsId.set(ts.id);
    this.formTsEditar.setValue({ ts_nombre: ts.ts_nombre, tipo: ts.tipo, calcular: ts.calcular });
  }

  cancelarEdicionTs() { this.editandoTsId.set(null); }

  guardarEdicionTs(id: number) {
    if (this.formTsEditar.invalid) return;
    const v = this.formTsEditar.value;
    this.api.actualizarTransferSet(id, {
      ts_nombre: v.ts_nombre!,
      tipo: v.tipo ?? 0,
      calcular: v.calcular ?? 1,
    }).subscribe({
      next: (updated) => {
        this.transferSets.update(list => list.map(t => t.id === id ? updated : t));
        this.editandoTsId.set(null);
      },
    });
  }

  eliminarTs(id: number) {
    this.api.eliminarTransferSet(id).subscribe({
      next: () => this.transferSets.update(list => list.filter(t => t.id !== id)),
    });
  }
}
