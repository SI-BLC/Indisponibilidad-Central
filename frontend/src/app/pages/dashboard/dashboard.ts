import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../services/api';
import { DashboardCentral } from '../../models/central';
import { GuardarResultadosMesResponse } from '../../models/resultado';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, MatProgressSpinnerModule, MatTooltipModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private readonly api = inject(ApiService);
  centrales = signal<DashboardCentral[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  guardandoResultados = signal(false);
  ultimoGuardado = signal<GuardarResultadosMesResponse | null>(null);

  totalEnlaces    = computed(() => this.centrales().reduce((a, c) => a + c.cant_enlaces, 0));
  configuradas    = computed(() => this.centrales().filter(c => c.tiene_grupos).length);
  sinGrupos       = computed(() => this.centrales().filter(c => !c.tiene_grupos).length);

  readonly tipoLabels: Record<number, string> = { 1: 'Directa', 2: 'Redundante', 3: 'Solo Backup' };
  readonly tipoBadge: Record<number, string>  = { 1: 'badge-primary', 2: 'badge-success', 3: 'badge-warning' };

  ngOnInit() {
    this.api.getDashboard().subscribe({
      next: (data) => { this.centrales.set(data); this.loading.set(false); },
      error: () => { this.error.set('Error al cargar el dashboard.'); this.loading.set(false); },
    });
  }

  guardarResultados() {
    this.guardandoResultados.set(true);
    this.ultimoGuardado.set(null);
    this.api.guardarResultadosMes().subscribe({
      next: (res) => { this.ultimoGuardado.set(res); this.guardandoResultados.set(false); },
      error: () => this.guardandoResultados.set(false),
    });
  }
}
