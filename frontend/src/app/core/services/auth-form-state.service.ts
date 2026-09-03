import { Injectable, signal } from '@angular/core';

import { AlertVariant } from '../../shared/components/alert/alert.component';

export interface FlashMessage {
  readonly message: string;
  readonly variant: AlertVariant;
}

/**
 * Estado que atravessa a navegação entre login e registro:
 *
 * - o e-mail já digitado, para não obrigar a redigitar ao trocar de tela
 *   (Nielsen #6 — reconhecimento em vez de memorização);
 * - uma mensagem única ("flash"), consumida pela próxima tela.
 *
 * Fica em memória de propósito: e-mail em query string vaza para o histórico do
 * browser, para logs de servidor e para o cabeçalho `Referer`.
 */
@Injectable({ providedIn: 'root' })
export class AuthFormStateService {
  private readonly email = signal('');
  private readonly flash = signal<FlashMessage | null>(null);

  get lastEmail(): string {
    return this.email();
  }

  rememberEmail(email: string): void {
    this.email.set(email.trim());
  }

  setFlash(message: string, variant: AlertVariant = 'success'): void {
    this.flash.set({ message, variant });
  }

  /** Lê e descarta: a mensagem não deve sobreviver a um segundo acesso à tela. */
  consumeFlash(): FlashMessage | null {
    const current = this.flash();
    this.flash.set(null);
    return current;
  }

  clear(): void {
    this.email.set('');
    this.flash.set(null);
  }
}
