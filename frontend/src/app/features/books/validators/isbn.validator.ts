import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

export function compactIsbn(value: string): string {
  return value.trim().toUpperCase().replace(/[\s-]/g, '');
}

/** Mesma validação de formato e checksum de `book_schema.normalize_isbn`. */
export const isbnValidator: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
  const value = control.value;
  if (typeof value !== 'string' || value.length === 0) {
    return null;
  }
  if (!/^[0-9X\s-]+$/i.test(value.trim())) {
    return { isbn: true };
  }

  const compact = compactIsbn(value);
  if (/^\d{9}[\dX]$/.test(compact)) {
    const sum = [...compact].reduce(
      (total, character, index) =>
        total + (character === 'X' ? 10 : Number(character)) * (10 - index),
      0,
    );
    return sum % 11 === 0 ? null : { isbn: true };
  }

  if (/^(978|979)\d{10}$/.test(compact)) {
    const weighted = [...compact.slice(0, 12)].reduce(
      (total, character, index) => total + Number(character) * (index % 2 === 0 ? 1 : 3),
      0,
    );
    return Number(compact[12]) === (10 - (weighted % 10)) % 10 ? null : { isbn: true };
  }

  return { isbn: true };
};
