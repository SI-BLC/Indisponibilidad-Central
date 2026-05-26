import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../services/api';
import { GuardarResultadosResponse, GuardarResultadosMesResponse } from '../../models/resultado';

@Component({
  selector: 'app-calculos',
  imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, MatProgressSpinnerModule, MatTooltipModule],
  templateUrl: './calculos.html',
  styleUrl: './calculos.scss',
})
export class Calculos {
  private readonly api = inject(ApiService);

  guardandoMesActual = signal(false);
  ultimoGuardadoMesActual = signal<GuardarResultadosMesResponse | null>(null);

  guardandoMesAnterior = signal(false);
  ultimoGuardadoMesAnterior = signal<GuardarResultadosMesResponse | null>(null);

  fechaDia = signal(this._ayer());
  guardandoDia = signal(false);
  ultimoGuardadoDia = signal<GuardarResultadosResponse | null>(null);

  private _ayer(): string {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
  }

  guardarResultadosMesActual() {
    this.guardandoMesActual.set(true);
    this.ultimoGuardadoMesActual.set(null);
    this.api.guardarResultadosMes().subscribe({
      next: (res) => { this.ultimoGuardadoMesActual.set(res); this.guardandoMesActual.set(false); },
      error: () => this.guardandoMesActual.set(false),
    });
  }

  guardarResultadosMesAnterior() {
    const hoy = new Date();
    const mesAnterior = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
    const year = mesAnterior.getFullYear();
    const month = mesAnterior.getMonth() + 1;

    this.guardandoMesAnterior.set(true);
    this.ultimoGuardadoMesAnterior.set(null);
    this.api.guardarResultadosMes(year, month).subscribe({
      next: (res) => { this.ultimoGuardadoMesAnterior.set(res); this.guardandoMesAnterior.set(false); },
      error: () => this.guardandoMesAnterior.set(false),
    });
  }

  guardarResultadosDia() {
    this.guardandoDia.set(true);
    this.ultimoGuardadoDia.set(null);
    this.api.guardarResultados(this.fechaDia()).subscribe({
      next: (res) => { this.ultimoGuardadoDia.set(res); this.guardandoDia.set(false); },
      error: () => this.guardandoDia.set(false),
    });
  }
}
