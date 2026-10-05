import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatChipsModule } from '@angular/material/chips';
import { ApiService } from '../../services/api';
import { GuardarResultadosResponse, GuardarResultadosMesResponse } from '../../models/resultado';
import { Central } from '../../models/central';

@Component({
  selector: 'app-calculos',
  imports: [
    CommonModule, RouterLink, ReactiveFormsModule,
    MatIconModule, MatButtonModule, MatProgressSpinnerModule, MatTooltipModule,
    MatFormFieldModule, MatInputModule, MatAutocompleteModule, MatChipsModule,
  ],
  templateUrl: './calculos.html',
  styleUrl: './calculos.scss',
})
export class Calculos implements OnInit {
  private readonly api = inject(ApiService);

  centrales = signal<Central[]>([]);

  // --- Cards globales (todas las centrales) ---
  guardandoMesActual = signal(false);
  progresoMesActual = signal('');
  ultimoGuardadoMesActual = signal<GuardarResultadosMesResponse | null>(null);

  guardandoMesAnterior = signal(false);
  progresoMesAnterior = signal('');
  ultimoGuardadoMesAnterior = signal<GuardarResultadosMesResponse | null>(null);

  mesEspecifico = signal(this._mesAnteriorStr());
  guardandoMesEspecifico = signal(false);
  progresoMesEspecifico = signal('');
  ultimoGuardadoMesEspecifico = signal<GuardarResultadosMesResponse | null>(null);

  fechaDia = signal(this._ayer());
  guardandoDia = signal(false);
  ultimoGuardadoDia = signal<GuardarResultadosResponse | null>(null);

  // --- Cards selectivas (centrales seleccionadas) ---
  selectedCentrales = signal<Central[]>([]);
  searchControl = new FormControl('');
  searchFilter = signal('');
  filteredCentrales = computed(() => {
    const term = this.searchFilter().toUpperCase();
    const selectedIds = new Set(this.selectedCentrales().map(c => c.id));
    let list = this.centrales().filter(c => !selectedIds.has(c.id));
    if (term) list = list.filter(c => c.nemo.toUpperCase().includes(term));
    return list;
  });

  guardandoSelMesActual = signal(false);
  progresoSelMesActual = signal('');
  ultimoGuardadoSelMesActual = signal<GuardarResultadosMesResponse | null>(null);

  guardandoSelMesAnterior = signal(false);
  progresoSelMesAnterior = signal('');
  ultimoGuardadoSelMesAnterior = signal<GuardarResultadosMesResponse | null>(null);

  mesEspecificoSel = signal(this._mesAnteriorStr());
  guardandoSelMesEspecifico = signal(false);
  progresoSelMesEspecifico = signal('');
  ultimoGuardadoSelMesEspecifico = signal<GuardarResultadosMesResponse | null>(null);

  fechaDiaSel = signal(this._ayer());
  guardandoSelDia = signal(false);
  ultimoGuardadoSelDia = signal<GuardarResultadosResponse | null>(null);

  private _selectedIds(): number[] {
    return this.selectedCentrales().map(c => c.id);
  }

  ngOnInit() {
    this.api.getCentrales().subscribe(c => this.centrales.set(c));
    this.searchControl.valueChanges.subscribe(val => {
      if (typeof val === 'string') this.searchFilter.set(val);
    });
  }

  private _ayer(): string {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
  }

  private _mesAnteriorStr(): string {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }

  private _suscribirMes(
    obs: ReturnType<typeof this.api.guardarResultadosMes>,
    guardando: ReturnType<typeof signal<boolean>>,
    progreso: ReturnType<typeof signal<string>>,
    resultado: ReturnType<typeof signal<GuardarResultadosMesResponse | null>>
  ) {
    obs.subscribe({
      next: (ev) => {
        if (ev.type === 'progress') {
          progreso.set(`Día ${ev['dia_num']}/${ev['total_dias']} (${ev['dia']})`);
        } else if (ev.type === 'done') {
          resultado.set(ev as any);
          guardando.set(false);
          progreso.set('');
        } else if (ev.type === 'error') {
          guardando.set(false);
          progreso.set('');
        }
      },
      error: () => { guardando.set(false); progreso.set(''); },
    });
  }

  // --- Acciones globales ---
  guardarResultadosMesActual() {
    this.guardandoMesActual.set(true);
    this.ultimoGuardadoMesActual.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(), this.guardandoMesActual, this.progresoMesActual, this.ultimoGuardadoMesActual);
  }

  guardarResultadosMesAnterior() {
    const hoy = new Date();
    const mesAnterior = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
    this.guardandoMesAnterior.set(true);
    this.ultimoGuardadoMesAnterior.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(mesAnterior.getFullYear(), mesAnterior.getMonth() + 1), this.guardandoMesAnterior, this.progresoMesAnterior, this.ultimoGuardadoMesAnterior);
  }

  guardarResultadosMesEspecifico() {
    const [y, m] = this.mesEspecifico().split('-').map(Number);
    if (!y || !m) return;
    this.guardandoMesEspecifico.set(true);
    this.ultimoGuardadoMesEspecifico.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(y, m), this.guardandoMesEspecifico, this.progresoMesEspecifico, this.ultimoGuardadoMesEspecifico);
  }

  guardarResultadosDia() {
    this.guardandoDia.set(true);
    this.ultimoGuardadoDia.set(null);
    this.api.guardarResultados(this.fechaDia()).subscribe({
      next: (res) => { this.ultimoGuardadoDia.set(res); this.guardandoDia.set(false); },
      error: () => this.guardandoDia.set(false),
    });
  }

  // --- Acciones selectivas ---
  addCentral(event: any) {
    const central: Central = event.option.value;
    this.selectedCentrales.update(list => [...list, central]);
    this.searchControl.setValue('');
  }

  removeCentral(id: number) {
    this.selectedCentrales.update(list => list.filter(c => c.id !== id));
  }

  displayCentral = (): string => '';

  guardarSelMesActual() {
    const ids = this._selectedIds();
    if (!ids.length) return;
    this.guardandoSelMesActual.set(true);
    this.ultimoGuardadoSelMesActual.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(undefined, undefined, ids), this.guardandoSelMesActual, this.progresoSelMesActual, this.ultimoGuardadoSelMesActual);
  }

  guardarSelMesAnterior() {
    const ids = this._selectedIds();
    if (!ids.length) return;
    const hoy = new Date();
    const mesAnterior = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
    this.guardandoSelMesAnterior.set(true);
    this.ultimoGuardadoSelMesAnterior.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(mesAnterior.getFullYear(), mesAnterior.getMonth() + 1, ids), this.guardandoSelMesAnterior, this.progresoSelMesAnterior, this.ultimoGuardadoSelMesAnterior);
  }

  guardarSelMesEspecifico() {
    const ids = this._selectedIds();
    if (!ids.length) return;
    const [y, m] = this.mesEspecificoSel().split('-').map(Number);
    if (!y || !m) return;
    this.guardandoSelMesEspecifico.set(true);
    this.ultimoGuardadoSelMesEspecifico.set(null);
    this._suscribirMes(this.api.guardarResultadosMes(y, m, ids), this.guardandoSelMesEspecifico, this.progresoSelMesEspecifico, this.ultimoGuardadoSelMesEspecifico);
  }

  guardarSelDia() {
    const ids = this._selectedIds();
    if (!ids.length) return;
    this.guardandoSelDia.set(true);
    this.ultimoGuardadoSelDia.set(null);
    this.api.guardarResultados(this.fechaDiaSel(), ids).subscribe({
      next: (res) => { this.ultimoGuardadoSelDia.set(res); this.guardandoSelDia.set(false); },
      error: () => this.guardandoSelDia.set(false),
    });
  }
}
