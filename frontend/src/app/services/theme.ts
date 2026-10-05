import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly KEY = 'app-theme';
  readonly isDark = signal(this.load());

  constructor() {
    this.apply(this.isDark());
  }

  toggle() {
    const dark = !this.isDark();
    this.isDark.set(dark);
    localStorage.setItem(this.KEY, dark ? 'dark' : 'light');
    this.apply(dark);
  }

  private load(): boolean {
    return localStorage.getItem(this.KEY) !== 'light';
  }

  private apply(dark: boolean) {
    document.body.classList.toggle('light-theme', !dark);
  }
}
