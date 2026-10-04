import { TestBed } from '@angular/core/testing';

import { SnackbarService } from './snackbar.service';

/** Apoio de specs: mensagem e variante do snackbar atualmente exibido ('' / null se não houver). */
export function snackbarMessage(): string {
  return TestBed.inject(SnackbarService).notification()?.message ?? '';
}

export function snackbarVariant(): string | null {
  return TestBed.inject(SnackbarService).notification()?.variant ?? null;
}
