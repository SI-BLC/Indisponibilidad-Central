import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  badge?: string;
}

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive, MatIconModule],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
})
export class Sidebar {
  readonly navItems: NavItem[] = [
    { label: 'Inicio', icon: 'home', route: '/welcome' },
    { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
    { label: 'Agregar Central', icon: 'add_circle', route: '/agregar-central' },
    { label: 'Editar Central', icon: 'edit', route: '/editar-central' },
    { label: 'Reportes', icon: 'bar_chart', route: '/reportes' },
    { label: 'Mantenimientos', icon: 'build', route: '/mantenimientos' },
    { label: 'Gestión de Grupos', icon: 'storage', route: '/gestion-datos' },
    { label: 'Resultados', icon: 'assessment', route: '/resultados' },
    { label: 'Datos', icon: 'table_view', route: '/datos' },
    { label: 'Cálculos', icon: 'calculate', route: '/calculos' },
    { label: 'Carga Manual', icon: 'upload', route: '/carga-manual' },
  ];
}
