import { Component, signal, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  username = '';
  password = '';
  hidePassword = signal(true);
  loading = signal(false);
  errorMessage = signal('');

  ssoEnabled = signal(false);
  ssoChecking = signal(false);

  async ngOnInit() {
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/dashboard']);
      return;
    }
    try {
      const resp = await fetch('/api/auth/sso-check');
      if (resp.ok) this.ssoEnabled.set(true);
    } catch {}
  }

  async trySso() {
    this.ssoChecking.set(true);
    this.errorMessage.set('');
    const ok = await this.auth.trySso();
    if (ok) {
      this.router.navigate(['/dashboard']);
    } else {
      this.ssoChecking.set(false);
      this.errorMessage.set('No se pudo autenticar con Windows. Usá usuario y contraseña.');
    }
  }

  onSubmit(): void {
    if (!this.username || !this.password) return;

    this.loading.set(true);
    this.errorMessage.set('');

    this.auth.login(this.username, this.password).subscribe({
      next: () => {
        this.loading.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading.set(false);
        if (err.status === 401) {
          this.errorMessage.set('Credenciales inválidas o usuario sin acceso autorizado.');
        } else if (err.status === 503) {
          this.errorMessage.set('No se pudo conectar al servidor de autenticación.');
        } else {
          this.errorMessage.set('Error inesperado. Intente nuevamente.');
        }
      },
    });
  }
}
