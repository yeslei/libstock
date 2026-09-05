import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/**
 * Validador de grupo: marca `passwordMismatch` no controle de confirmação para
 * que a mensagem apareça ancorada ao campo certo, e não no topo do formulário.
 */
export function matchPassword(passwordKey: string, confirmationKey: string): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const password = group.get(passwordKey);
    const confirmation = group.get(confirmationKey);

    if (!password || !confirmation || confirmation.value === '') {
      return null;
    }

    const mismatch = password.value !== confirmation.value;
    const errors = { ...(confirmation.errors ?? {}) };

    if (mismatch) {
      confirmation.setErrors({ ...errors, passwordMismatch: true });
    } else if ('passwordMismatch' in errors) {
      delete errors['passwordMismatch'];
      confirmation.setErrors(Object.keys(errors).length > 0 ? errors : null);
    }

    return null;
  };
}
