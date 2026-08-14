import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormControl, Validators } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { Enlace } from '../../models/enlace';

@Component({
  selector: 'app-cortes-manuales',
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule,
    MatSnackBarModule, MatAutocompleteModule, MatTooltipModule, MatProgressSpinnerModule,
  ],
  templateUrl: './cortes-manuales.html',
  styleUrl: './cortes-manuales.scss',
})
export class CortesManuales implements OnInit {
  private readonly api = inject(ApiService);
  private readonly snack = inject(MatSnackBar);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);

  centrales = signal<Central[]>([]);
  searchCentral = new FormControl('');
  centralFilter = signal('');
  filteredCentrales = computed(() => {
    const term = this.centralFilter().toUpperCase();
    if (!term) return this.centrales();
    return this.centrales().filter(c => c.nemo.toUpperCase().includes(term));
  });
  displayCentral = (c: Central | string | null): string => {
    if (!c || typeof c === 'string') return '';
    return c.nemo;
  };

  enlaces = signal<Enlace[]>([]);
  historial = signal<any[]>([]);
  guardando = signal(false);

  form = this.fb.group({
    idCentral: [null as number | null, Validators.required],
    idEnlace: [null as number | null, Validators.required],
    fechaInicio: ['', Validators.required],
    fechaFin: ['', Validators.required],
  });

  readonly columns = ['fecha', 'tipo', 'enlace', 'acciones'];

  ngOnInit() {
    this.api.getCentrales().subscribe(c => this.centrales.set(c));
    this.searchCentral.valueChanges.subscribe(val => {
      if (typeof val === 'string') this.centralFilter.set(val);
    });

    const qp = this.route.snapshot.queryParams;
    if (qp['central'] && qp['fecha'] && qp['hora']) {
      this._precargar(+qp['central'], qp['fecha'], qp['hora']);
    }
  }

  private _precargar(centralId: number, fecha: string, hora: string) {
    this.api.getCentrales().subscribe(centrales => {
      const central = centrales.find(c => c.id === centralId);
      if (!central) return;
      this.searchCentral.setValue(central as any);
      this.form.controls.idCentral.setValue(central.id);
      this.onCentralChange(central.id);

      this.form.patchValue({
        fechaInicio: `${fecha}T00:00`,
        fechaFin: `${fecha}T${hora.slice(0, 5)}`,
      });
    });
  }

  onCentralSelected(event: any) {
    const central: Central = event.option.value;
    this.form.controls.idCentral.setValue(central.id);
    this.onCentralChange(central.id);
  }

  onCentralChange(id: number) {
    this.form.patchValue({ idEnlace: null });
    this.api.getEnlaces(id).subscribe(e => this.enlaces.set(e));
    this.cargarHistorial(id);
  }

  onEnlaceChange(idEnlace: number) {
    this.cargarHistorialEnlace(idEnlace);
  }

  guardar() {
    if (this.form.invalid) return;
    const v = this.form.value;
    this.guardando.set(true);

    this.api.insertarCorteManual({
      id_enlace: v.idEnlace!,
      fecha_inicio: v.fechaInicio!,
      fecha_fin: v.fechaFin!,
    }).subscribe({
      next: () => {
        this.snack.open('Corte manual insertado correctamente', 'OK', { duration: 4000 });
        this.guardando.set(false);
        this.form.patchValue({ fechaInicio: '', fechaFin: '' });
        if (v.idEnlace) this.cargarHistorialEnlace(v.idEnlace);
      },
      error: (e) => {
        this.snack.open(e.error?.detail ?? 'Error al insertar', 'OK', { duration: 4000 });
        this.guardando.set(false);
      },
    });
  }

  eliminar(id: number) {
    if (!confirm('¿Eliminar este registro manual?')) return;
    this.api.eliminarCorteManual(id).subscribe({
      next: () => {
        this.historial.update(list => list.filter(r => r.id !== id));
        this.snack.open('Registro eliminado', 'OK', { duration: 3000 });
      },
      error: () => this.snack.open('Error al eliminar', 'OK', { duration: 3000 }),
    });
  }

  private cargarHistorial(idCentral: number) {
    const enlaces$ = this.api.getEnlaces(idCentral);
    enlaces$.subscribe(enlaces => {
      if (enlaces.length > 0) {
        this.cargarHistorialEnlace(enlaces[0].id);
      } else {
        this.historial.set([]);
      }
    });
  }

  private cargarHistorialEnlace(idEnlace: number) {
    this.api.listarCortesManuales(idEnlace).subscribe(h => {
      const enlace = this.enlaces().find(e => e.id === idEnlace);
      this.historial.set(h.map(r => ({ ...r, enlace_nombre: enlace?.nombre ?? `#${idEnlace}` })));
    });
  }

  formatFecha(val: string | null): string {
    if (!val) return '—';
    const s = val.replace('T', ' ').replace('Z', '');
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2}:\d{2})/);
    if (!m) return val;
    return `${m[3]}/${m[2]}/${m[1].slice(2)} ${m[4]}`;
  }

  tipoLabel(tipo: string | null): string {
    if (tipo === 'i+') return 'Desconexión';
    if (tipo === 'e+') return 'Establecimiento';
    return tipo ?? '—';
  }

  tipoBadge(tipo: string | null): string {
    if (tipo === 'i+') return 'badge-danger';
    if (tipo === 'e+') return 'badge-success';
    return 'badge-muted';
  }
}
