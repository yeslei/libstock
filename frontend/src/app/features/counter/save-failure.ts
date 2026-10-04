import { ApiError } from '../../core/models/auth.model';
import { SnackbarService, SnackbarVariant } from '../../shared/components/snackbar/snackbar.service';

/**
 * Falha de persistência ou de rede (status 0 ou 5xx): o resultado da escrita é incerto, então a tela mostra
 * o estado "Não foi possível salvar" em vez de uma mensagem passageira e nunca reenvia por conta própria.
 */
export function isPersistenceFailure(error: unknown): boolean {
  const status = (error as Partial<ApiError> | null)?.status;
  return status === 0 || (typeof status === 'number' && status >= 500);
}

/** Texto do estado de recuperação (referência 07, "Não foi possível salvar"). */
export const SAVE_FAILURE_TEXT =
  'Não foi possível confirmar o resultado. Atualize a consulta antes de repetir a operação para evitar registros duplicados.';

/** Resposta 4xx de domínio: conflito de estado é "atenção"; as demais recusas são "erro". */
export function failureVariant(error: unknown): SnackbarVariant {
  return (error as Partial<ApiError> | null)?.status === 409 ? 'warning' : 'error';
}

export function showFailure(snackbar: SnackbarService, error: unknown, fallback: string): void {
  const detail = (error as Partial<ApiError> | null)?.detail;
  snackbar.show(typeof detail === 'string' && detail ? detail : fallback, failureVariant(error));
}
