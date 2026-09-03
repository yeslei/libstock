import { AbstractControl } from '@angular/forms';

export type ErrorMessages = Readonly<Record<string, string>>;

/**
 * Primeira mensagem aplicável ao controle, ou `null` quando nada deve aparecer.
 *
 * A regra de *quando* mostrar resolve a tensão entre as heurísticas #5 e #9 de
 * Nielsen: a validação roda a cada tecla, mas o erro só fica visível depois que
 * o campo perdeu o foco (`touched`) ou depois do primeiro envio (`submitted`).
 * Assim ninguém vê "e-mail inválido" ao digitar a segunda letra — e, uma vez
 * que o envio falhou, a correção é confirmada em tempo real enquanto digita.
 */
export function fieldError(
  control: AbstractControl | null,
  messages: ErrorMessages,
  submitted: boolean,
): string | null {
  if (control === null || control.valid || !(control.touched || submitted)) {
    return null;
  }

  const errors = control.errors ?? {};
  for (const key of Object.keys(errors)) {
    const message = messages[key];
    if (message !== undefined) {
      return message;
    }
  }

  return 'Confira este campo.';
}
