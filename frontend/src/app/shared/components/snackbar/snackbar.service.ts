import { DestroyRef, Injectable, inject, signal } from '@angular/core';

export type SnackbarVariant = 'success' | 'error' | 'warning' | 'info';

export interface SnackbarAction {
  readonly label: string;
  readonly run: () => void;
}

export interface SnackbarMessage {
  readonly id: number;
  readonly message: string;
  readonly variant: SnackbarVariant;
  readonly action?: SnackbarAction;
}

/** Feedback passageiro; o layout que hospeda `<app-snackbar>` o descarta ao ser destruído. */
@Injectable({ providedIn: 'root' })
export class SnackbarService {
  private readonly current = signal<SnackbarMessage | null>(null);
  readonly notification = this.current.asReadonly();
  private timer?: ReturnType<typeof setTimeout>;
  private sequence = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.dismiss());
  }

  show(message: string, variant: SnackbarVariant = 'info', action?: SnackbarAction): void {
    this.dismiss();
    this.current.set({ id: ++this.sequence, message, variant, action });
    // Errors, warnings and actionable messages remain until explicitly dismissed.
    if (!action && (variant === 'success' || variant === 'info')) {
      this.timer = setTimeout(() => this.dismiss(), 8000);
    }
  }

  dismiss(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
    this.current.set(null);
  }

  act(): void {
    const notification = this.current();
    if (!notification?.action) return;
    notification.action.run();
    if (this.current()?.id === notification.id) this.dismiss();
  }
}
