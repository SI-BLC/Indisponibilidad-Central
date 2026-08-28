import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { ApiService } from '../../services/api';

interface CertInfo {
  cn: string; thumbprint: string; valid: string; pfx_password: string;
}

interface InstaladorInfo {
  filename: string; size_bytes: number;
}

interface ResultadoGeneracion {
  planta: string;
  certificados: Record<string, CertInfo>;
  mysql_users: Record<string, any>;
  instaladores: Record<string, InstaladorInfo>;
}

interface HistorialItem {
  id: number; planta_base: string; central_nombre: string;
  protocolo: string; usuario: string; sotra_cn: string;
  sotrb_cn: string; created_at: string;
}

interface ProgressState {
  step: number; total: number; message: string;
}

@Component({
  selector: 'app-instaladores',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatSnackBarModule,
    MatProgressBarModule,
  ],
  templateUrl: './instaladores.html',
  styleUrl: './instaladores.scss',
})
export class Instaladores {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);
  private readonly fb = inject(FormBuilder);

  private readonly IP_PATTERN = /^\d{1,3}(\.\d{1,3}){3}$/;
  private readonly HOSTNAME_PATTERN = /^[a-z0-9][a-z0-9._-]*$/;

  private hostnameAManual = false;
  private hostnameBManual = false;

  form = this.fb.group({
    planta_base: ['', [Validators.required, Validators.pattern(/^[a-z0-9]+$/)]],
    hostname_sotra: ['', [Validators.required, Validators.pattern(/^[a-z0-9][a-z0-9._-]*$/)]],
    ip_vpn_sotra: ['', [Validators.pattern(/^\d{1,3}(\.\d{1,3}){3}$/)]],
    ip_mpls_sotra: ['', [Validators.pattern(/^\d{1,3}(\.\d{1,3}){3}$/)]],
    hostname_sotrb: ['', [Validators.pattern(/^[a-z0-9][a-z0-9._-]*$/)]],
    ip_vpn_sotrb: ['', [Validators.pattern(/^\d{1,3}(\.\d{1,3}){3}$/)]],
    ip_mpls_sotrb: ['', [Validators.pattern(/^\d{1,3}(\.\d{1,3}){3}$/)]],
    central_nombre: ['', Validators.required],
    protocolo: ['ELCOM', Validators.required],
  });

  generando = signal(false);
  progreso = signal<ProgressState | null>(null);
  resultado = signal<ResultadoGeneracion | null>(null);
  historial = signal<HistorialItem[]>([]);

  constructor() {
    this.cargarHistorial();

    this.form.get('planta_base')!.valueChanges.subscribe(v => {
      if (v && v !== v.toLowerCase()) {
        this.form.get('planta_base')!.setValue(v.toLowerCase(), { emitEvent: false });
      }
      const base = (v || '').toLowerCase();
      if (!this.hostnameAManual) {
        this.form.get('hostname_sotra')!.setValue(base ? base + 'sotra' : '', { emitEvent: false });
      }
      if (!this.hostnameBManual) {
        this.form.get('hostname_sotrb')!.setValue(base ? base + 'sotrb' : '', { emitEvent: false });
      }
    });

    this.form.get('hostname_sotra')!.valueChanges.subscribe(v => {
      const base = this.form.get('planta_base')!.value || '';
      const expected = base ? base.toLowerCase() + 'sotra' : '';
      this.hostnameAManual = v !== expected;
    });

    this.form.get('hostname_sotrb')!.valueChanges.subscribe(v => {
      const base = this.form.get('planta_base')!.value || '';
      const expected = base ? base.toLowerCase() + 'sotrb' : '';
      this.hostnameBManual = v !== expected;
    });
  }

  get sotrAValido(): boolean {
    const vpn = this.form.get('ip_vpn_sotra')?.value;
    const mpls = this.form.get('ip_mpls_sotra')?.value;
    return !!(vpn && this.IP_PATTERN.test(vpn)) || !!(mpls && this.IP_PATTERN.test(mpls));
  }

  get sotrBActivo(): boolean {
    const vpn = this.form.get('ip_vpn_sotrb')?.value;
    const mpls = this.form.get('ip_mpls_sotrb')?.value;
    return !!(vpn || mpls);
  }

  get formValido(): boolean {
    const base = this.form.get('planta_base');
    const central = this.form.get('central_nombre');
    const hostnameA = this.form.get('hostname_sotra');
    if (!base?.valid || !central?.valid || !hostnameA?.valid) return false;
    if (!hostnameA?.value) return false;
    if (!this.sotrAValido) return false;
    if (this.sotrBActivo) {
      const vpnB = this.form.get('ip_vpn_sotrb');
      const mplsB = this.form.get('ip_mpls_sotrb');
      const tieneVpnB = vpnB?.value && this.IP_PATTERN.test(vpnB.value);
      const tieneMplsB = mplsB?.value && this.IP_PATTERN.test(mplsB.value);
      if (!tieneVpnB && !tieneMplsB) return false;
      const hostnameB = this.form.get('hostname_sotrb');
      if (!hostnameB?.value || !this.HOSTNAME_PATTERN.test(hostnameB.value)) return false;
    }
    return true;
  }

  generar() {
    if (!this.formValido || this.generando()) return;
    this.generando.set(true);
    this.resultado.set(null);
    this.progreso.set({ step: 0, total: 1, message: 'Iniciando...' });

    const body: any = { ...this.form.value };
    if (!this.sotrBActivo) {
      body.hostname_sotrb = '';
    }
    this.api.generarInstaladoresSSE(body, {
      onProgress: (p: ProgressState) => this.progreso.set(p),
      onDone: (r: ResultadoGeneracion) => {
        this.resultado.set(r);
        this.generando.set(false);
        this.progreso.set(null);
        this.cargarHistorial();
        this.snack.open('Instaladores generados correctamente', 'OK', { duration: 5000 });
      },
      onError: (msg: string) => {
        this.generando.set(false);
        this.progreso.set(null);
        this.snack.open(msg, 'OK', { duration: 8000 });
      },
    });
  }

  cargarHistorial() {
    this.api.historialInstaladores().subscribe({
      next: (list: any) => this.historial.set(list),
      error: () => {},
    });
  }

  eliminar(planta: string) {
    if (!confirm(`Eliminar registros de "${planta}"? Podrás volver a generarla.`)) return;
    this.api.eliminarPlantaInstalador(planta).subscribe({
      next: () => {
        this.cargarHistorial();
        this.snack.open(`Planta "${planta}" eliminada`, 'OK', { duration: 3000 });
      },
      error: (err) => {
        this.snack.open(err.error?.detail || 'Error al eliminar', 'OK', { duration: 5000 });
      },
    });
  }

  descargar(sotr: string) {
    const res = this.resultado();
    if (!res) return;
    const filename = `BLC_NODE_${res.planta.toUpperCase()}_${sotr.toUpperCase()}.exe`;
    const token = localStorage.getItem('auth_token') || '';

    fetch(`http://10.230.90.220:8000/instaladores/descargar/${res.planta}/${sotr}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error('Error al descargar');
        return r.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => this.snack.open('Error al descargar el instalador', 'OK', { duration: 5000 }));
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  get sotrKeys(): string[] {
    const res = this.resultado();
    return res ? Object.keys(res.certificados) : [];
  }

  limpiar() {
    this.form.reset({ protocolo: 'ELCOM' });
    this.resultado.set(null);
    this.progreso.set(null);
    this.hostnameAManual = false;
    this.hostnameBManual = false;
  }
}
