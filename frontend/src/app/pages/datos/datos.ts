import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { forkJoin } from 'rxjs';
import { ApiService } from '../../services/api';
import { Central } from '../../models/central';
import { Enlace } from '../../models/enlace';
import { ConItem, DatItem, ConIccpItem, DatIccpItem } from '../../models/datos';

@Component({
  selector: 'app-datos',
  providers: [provideNativeDateAdapter()],
  imports: [
    CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatTableModule,
    MatProgressSpinnerModule, MatDatepickerModule, MatCheckboxModule,
  ],
  templateUrl: './datos.html',
  styleUrl: './datos.scss',
})
export class Datos implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);

  centrales = signal<Central[]>([]);
  enlaces   = signal<Enlace[]>([]);
  conData   = signal<ConItem[]>([]);
  datData   = signal<DatItem[]>([]);
  conIccpData = signal<ConIccpItem[]>([]);
  datIccpData = signal<DatIccpItem[]>([]);
  loading   = signal(false);
  buscado   = signal(false);

  get esIccp() {
    const id = this.form.value.idCentral;
    return this.centrales().find(c => c.id === id)?.protocolo === 'iccp';
  }

  form = this.fb.group({
    idCentral:   [null as number | null, Validators.required],
    idsEnlace:   [[] as number[]],
    fechaInicio: [null as Date | null, Validators.required],
    horaInicio:  ['00:00'],
    fechaFin:    [null as Date | null, Validators.required],
    horaFin:     ['00:00'],
  });

  readonly colsCon = [
    'fecha', 'id_enlace', 'asoc_ab', 'asoc_ac', 'asoc_bb', 'asoc_bc',
    'elc', 'link', 'integrity_scan', 'id_sotr', 'asoc_change',
  ];
  readonly colsDat = [
    'fecha', 'id_enlace', 'id_gr', 'gr_grupo',
    'siz', 't', 'g', 'h', 'c', 'e', 'm', 'i', 'exp', 'freq', 'st',
  ];
  readonly colsConIccp = [
    'fecha', 'id_enlace', 'srv', 'event_type', 'c_state', 's_state', 'id_sotr',
  ];
  readonly colsDatIccp = [
    'fecha', 'id_enlace', 'srv', 'direction', 'ts', 'ds',
    'siz', 'exp', 't', 'g', 'h', 'c', 'e', 'm', 'i',
  ];

  todosSeleccionados = computed(() => {
    const ids = this.form.value.idsEnlace ?? [];
    const all = this.enlaces();
    return all.length > 0 && ids.length === all.length;
  });

  get formValido(): boolean {
    const v = this.form.value;
    return !!v.idCentral && !!v.fechaInicio && !!v.fechaFin;
  }

  ngOnInit() {
    this.api.getCentrales().subscribe(c => this.centrales.set(c));

    this.form.controls.idCentral.valueChanges.subscribe(id => {
      this.enlaces.set([]);
      this.form.patchValue({ idsEnlace: [] }, { emitEvent: false });
      if (id != null) {
        this.api.getEnlaces(id).subscribe(e => {
          this.enlaces.set(e);
          this.form.patchValue({ idsEnlace: e.map(x => x.id) }, { emitEvent: false });
        });
      }
    });
  }

  toggleTodos() {
    const all  = this.enlaces().map(e => e.id);
    const curr = this.form.value.idsEnlace ?? [];
    this.form.patchValue(
      { idsEnlace: curr.length === all.length ? [] : all },
      { emitEvent: false }
    );
  }

  buscar() {
    if (!this.formValido) return;
    const v = this.form.value;
    const inicio = this.buildDateTime(v.fechaInicio!, v.horaInicio ?? '00:00');
    const fin    = this.buildDateTime(v.fechaFin!,    v.horaFin    ?? '00:00');
    const ids    = (v.idsEnlace?.length ? v.idsEnlace : this.enlaces().map(e => e.id));

    this.loading.set(true);
    this.buscado.set(true);
    this.conData.set([]);
    this.datData.set([]);
    this.conIccpData.set([]);
    this.datIccpData.set([]);

    const filtros = { ids_enlace: ids, fecha_inicio: inicio, fecha_fin: fin };

    if (this.esIccp) {
      forkJoin({
        con: this.api.getDatosConIccp(filtros),
        dat: this.api.getDatosDatIccp(filtros),
      }).subscribe({
        next: ({ con, dat }) => {
          this.conIccpData.set(con);
          this.datIccpData.set(dat);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    } else {
      forkJoin({
        con: this.api.getDatosCon(filtros),
        dat: this.api.getDatosDat(filtros),
      }).subscribe({
        next: ({ con, dat }) => {
          this.conData.set(con);
          this.datData.set(dat);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    }
  }

  private buildDateTime(date: Date, time: string): string {
    const [h, m] = time.split(':').map(Number);
    const dt = new Date(date);
    dt.setHours(h, m, 0, 0);
    return dt.toISOString();
  }

  v(val: unknown): string {
    return val == null ? '—' : String(val);
  }
}
