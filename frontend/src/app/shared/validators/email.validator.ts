import { AbstractControl, ValidationErrors } from '@angular/forms';

/**
 * `Validators.email` do Angular aceita `nome@dominio` (sem TLD), enquanto o
 * `EmailStr` do backend rejeita — a divergência viraria um 422 depois do envio.
 * Validar o domínio completo aqui mantém o erro no campo, antes da requisição
 * (Nielsen #5).
 *
 * A verificação continua deliberadamente frouxa: só o servidor sabe se um
 * endereço existe, e regex ambiciosa demais rejeita e-mails válidos.
 */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

export function emailFormat(control: AbstractControl): ValidationErrors | null {
  const value = (control.value ?? '').toString().trim();
  return value === '' || EMAIL_PATTERN.test(value) ? null : { email: true };
}
