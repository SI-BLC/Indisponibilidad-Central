import { Component, inject, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService, NodoEstado } from '../../services/api';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, MatProgressSpinnerModule, MatTooltipModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private refreshTimer: any;

  nodos = signal<NodoEstado[]>([]);
  loading = signal(true);
  checking = signal(false);
  error = signal<string | null>(null);
  lastCheckTime = signal<Date | null>(null);

  totalNodos = computed(() => this.nodos().length);
  onlineCount = computed(() => this.nodos().filter(n => n.online === true).length);
  offlineCount = computed(() => this.nodos().filter(n => n.online === false).length);
  unknownCount = computed(() => this.nodos().filter(n => n.online === null).length);

  nodosOffline = computed(() =>
    this.nodos()
      .filter(n => n.online === false)
      .sort((a, b) => (a.ultimo_caida ?? '').localeCompare(b.ultimo_caida ?? ''))
  );

  nodosOnline = computed(() =>
    this.nodos()
      .filter(n => n.online === true)
      .sort((a, b) => a.centrales[0]?.nemo.localeCompare(b.centrales[0]?.nemo ?? '') ?? 0)
  );

  nodosDesconocidos = computed(() => this.nodos().filter(n => n.online === null));

  readonly tipoLabels: Record<number, string> = { 1: 'Directa', 2: 'Redundante', 3: 'Solo Backup', 4: 'Concentrador' };

  ngOnInit() {
    this.cargar();
    this.refreshTimer = setInterval(() => this.cargar(), 60000);
  }

  ngOnDestroy() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
  }

  cargar() {
    this.api.getNodos().subscribe({
      next: (data) => {
        this.nodos.set(data);
        this.loading.set(false);
        if (data.length > 0 && data[0].ultimo_check) {
          this.lastCheckTime.set(new Date(data[0].ultimo_check));
        }
      },
      error: () => { this.error.set('Error al cargar nodos.'); this.loading.set(false); },
    });
  }

  ejecutarCheck() {
    this.checking.set(true);
    this.api.checkNodos().subscribe({
      next: () => {
        this.checking.set(false);
        this.cargar();
      },
      error: () => this.checking.set(false),
    });
  }

  tiempoDesde(iso: string | null): string {
    if (!iso) return '—';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Hace instantes';
    if (mins < 60) return `${mins} min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ${mins % 60}m`;
    const days = Math.floor(hrs / 24);
    return `${days}d ${hrs % 24}h`;
  }

  horaCorta(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }
}
