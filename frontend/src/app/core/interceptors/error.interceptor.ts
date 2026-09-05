import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

import { ApiError } from '../models/auth.model';

/**
 * Mensagem de UI por `code` do backend (`app/core/exceptions.py`).
 *
 * `invalid_credentials` é deliberadamente genérico: dizer *qual* dos dois campos
 * está errado transformaria a tela de login em um oráculo de e-mails
 * cadastrados. A distinção só aparece no registro, onde o e-mail duplicado já é
 * observável de qualquer forma.
 */
const MESSAGE_BY_CODE: Readonly<Record<string, string>> = {
  invalid_credentials: 'E-mail ou senha incorretos.',
  duplicate_email: 'Este e-mail já está cadastrado.',
  invalid_token: 'Sua sessão expirou. Entre novamente para continuar.',
  refresh_token_reuse:
    'Detectamos um uso indevido da sua sessão. Por segurança, entre novamente.',
  permission_denied: 'Você não tem permissão para realizar esta ação.',
  user_not_found: 'Não encontramos esse usuário.',
};

const MESSAGE_BY_STATUS: Readonly<Record<number, string>> = {
  0: 'Não foi possível falar com o servidor. Verifique sua conexão e tente de novo.',
  404: 'Recurso não encontrado.',
  409: 'Este e-mail já está cadastrado.',
  422: 'Confira os dados informados e tente novamente.',
  429: 'Muitas tentativas seguidas. Aguarde um instante antes de tentar de novo.',
};

function readDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return null;
  }

  const detail = (body as { detail: unknown }).detail;
  // O FastAPI devolve uma lista de erros em 422; a aplicação devolve string.
  return typeof detail === 'string' ? detail : null;
}

function readCode(body: unknown): string | undefined {
  if (typeof body !== 'object' || body === null || !('code' in body)) {
    return undefined;
  }

  const code = (body as { code: unknown }).code;
  return typeof code === 'string' ? code : undefined;
}

function toApiError(error: HttpErrorResponse): ApiError {
  const code = readCode(error.error);
  const mapped = code ? MESSAGE_BY_CODE[code] : undefined;
  const detail = readDetail(error.error);
  const byStatus = MESSAGE_BY_STATUS[error.status];
  const fallback =
    error.status >= 500
      ? 'Tivemos um problema no servidor. Tente novamente em instantes.'
      : 'Algo deu errado. Tente novamente.';

  return {
    detail: mapped ?? detail ?? byStatus ?? fallback,
    code,
    status: error.status,
  };
}

/**
 * Normaliza toda falha HTTP no contrato `ApiError` — a UI nunca precisa
 * inspecionar `HttpErrorResponse` nem adivinhar o formato do corpo.
 */
export const errorInterceptor: HttpInterceptorFn = (request, next) =>
  next(request).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        return throwError(() => toApiError(error));
      }
      return throwError(() => error);
    }),
  );
