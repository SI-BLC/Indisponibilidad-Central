import { Component, inject, OnInit, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api';

interface EnlaceObtenido {
  nombre: string;
  editando: boolean;
  nombreEdit: string;
}

@Component({
  selector: 'app-agregar-central',
  imports: [
    ReactiveFormsModule, RouterLink, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatSnackBarModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './agregar-central.html',
  styleUrl: './agregar-central.scss',
})
export class AgregarCentral implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly snack = inject(MatSnackBar);
  private readonly fb = inject(FormBuilder);

  loading = signal(false);
  loadingEnlaces = signal(false);
  ipCentral = '';
  enlacesObtenidos = signal<EnlaceObtenido[]>([]);
  concentradores = signal<{id: number; nemo: string}[]>([]);

  form = this.fb.group({
    nemo: ['', [Validators.required, Validators.maxLength(50)]],
    tipo: [null as number | null, Validators.required],
    protocolo: ['elcom', Validators.required],
    id_concentrador: [null as number | null],
    ip1: [''],
    ip2: [''],
  });

  get necesitaConcentrador() { return [2, 3].includes(this.form.value.tipo ?? 0); }

  ngOnInit() {
    this.api.getCentrales().subscribe({
      next: (c) => this.concentradores.set(c.filter(x => x.tipo === 4)),
    });
  }

  readonly tipos = [
    { value: 1, label: 'Tipo 1 — Directa', icon: 'arrow_forward', color: '#539bff', bgColor: 'rgba(83,155,255,.12)', desc: 'Enlace de acceso único directo' },
    { value: 2, label: 'Tipo 2 — Redundante', icon: 'compare_arrows', color: '#4bd08b', bgColor: 'rgba(75,208,139,.12)', desc: 'Enlace principal con backup activo' },
    { value: 3, label: 'Tipo 3 — Solo Backup', icon: 'backup', color: '#f8c076', bgColor: 'rgba(248,192,118,.12)', desc: 'Únicamente enlace de respaldo' },
  ];

  guardar() {
    if (this.form.invalid) return;
    this.loading.set(true);
    const v = this.form.value;
    this.api.crearCentral({ nemo: v.nemo!, tipo: v.tipo!, protocolo: v.protocolo!, id_concentrador: v.id_concentrador || null, ip1: v.ip1 || null, ip2: v.ip2 || null }).subscribe({
      next: (central) => {
        const pendientes = this.enlacesObtenidos();
        if (pendientes.length === 0) {
          this.snack.open('Central creada exitosamente', 'OK', { duration: 3000 });
          this.router.navigate(['/dashboard']);
          return;
        }
        let done = 0;
        const finish = () => {
          done++;
          if (done === pendientes.length) {
            this.snack.open(`Central creada con ${pendientes.length} enlace(s)`, 'OK', { duration: 3000 });
            this.router.navigate(['/dashboard']);
          }
        };
        for (const e of pendientes) {
          this.api.crearEnlace({ nombre: e.nombre, idcentral: central.id }).subscribe({
            next: finish,
            error: finish,
          });
        }
      },
      error: (e) => {
        this.snack.open(e.error?.detail ?? 'Error al crear central', 'OK', { duration: 4000 });
        this.loading.set(false);
      },
    });
  }

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

  private parseEnlacesRaw(raw: string): EnlaceObtenido[] {
    try {
      const arr: string[] = JSON.parse(raw.trim());
      return arr.map(nombre => ({ nombre, editando: false, nombreEdit: nombre }));
    } catch {
      this.snack.open('No se pudo interpretar la respuesta', 'OK', { duration: 3000 });
      return [];
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
