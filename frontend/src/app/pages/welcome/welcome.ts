import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { CommonModule } from '@angular/common';

interface MenuItem { label: string; icon: string; route: string; desc: string; color: string; }

@Component({
  selector: 'app-welcome',
  imports: [RouterLink, MatButtonModule, MatIconModule, CommonModule],
  templateUrl: './welcome.html',
  styleUrl: './welcome.scss',
})
export class Welcome {
  readonly menu: MenuItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/dashboard', desc: 'Estado general de todas las centrales', color: 'blue' },
    { label: 'Agregar Central', icon: 'add_circle', route: '/agregar-central', desc: 'Registrar una nueva central en el sistema', color: 'green' },
    { label: 'Editar Central', icon: 'edit', route: '/editar-central', desc: 'Modificar centrales y gestionar enlaces', color: 'orange' },
    { label: 'Reportes', icon: 'bar_chart', route: '/reportes', desc: 'Calcular disponibilidad por período', color: 'purple' },
    { label: 'Mantenimientos', icon: 'build', route: '/mantenimientos', desc: 'Programar y gestionar ventanas de mantenimiento', color: 'red' },
    { label: 'Gestión de Datos', icon: 'storage', route: '/gestion-datos', desc: 'Configurar grupos por enlace', color: 'teal' },
  ];
}
