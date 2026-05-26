import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login').then((m) => m.Login),
  },
  {
    path: 'welcome',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/welcome/welcome').then((m) => m.Welcome),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/dashboard/dashboard').then((m) => m.Dashboard),
  },
  {
    path: 'agregar-central',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/agregar-central/agregar-central').then(
        (m) => m.AgregarCentral
      ),
  },
  {
    path: 'editar-central',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/editar-central/editar-central').then(
        (m) => m.EditarCentral
      ),
  },
  {
    path: 'reportes',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/reportes/reportes').then((m) => m.Reportes),
  },
  {
    path: 'mantenimientos',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/mantenimientos/mantenimientos').then(
        (m) => m.Mantenimientos
      ),
  },
  {
    path: 'gestion-datos',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/gestion-datos/gestion-datos').then(
        (m) => m.GestionDatos
      ),
  },
  {
    path: 'resultados',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/resultados/resultados').then((m) => m.Resultados),
  },
  {
    path: 'resultados/:centralId/:fecha',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/resultado-detalle/resultado-detalle').then((m) => m.ResultadoDetalle),
  },
  {
    path: 'datos',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/datos/datos').then((m) => m.Datos),
  },
  {
    path: 'calculos',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/calculos/calculos').then((m) => m.Calculos),
  },
  { path: '**', redirectTo: 'dashboard' },
];
