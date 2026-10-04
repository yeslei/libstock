import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

import { ApiError, ApiValidationError } from '../models/auth.model';

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
  user_already_inactive: 'Este usuário já está inativo.',
  user_self_inactivation: 'Você não pode inativar a própria conta.',
  user_self_role_removal: 'Você não pode remover o próprio acesso administrativo.',
  last_active_administrator: 'O último administrador ativo não pode perder o acesso.',
  duplicate_isbn: 'Este ISBN já está cadastrado.',
  duplicate_barcode: 'Este código de barras já está cadastrado.',
  employee_record_required:
    'Seu usuário não possui um cadastro de funcionário apto a realizar esta ação.',
  google_books_not_found: 'O ISBN não foi encontrado no Google Books.',
  google_books_unavailable:
    'Não foi possível consultar os dados externos. Tente novamente em instantes.',
  google_books_rate_limited:
    'O Google Books recebeu consultas demais. Tente novamente em instantes.',
  google_books_invalid_response:
    'O Google Books não retornou título e autor válidos para este ISBN.',
  book_persistence_error: 'Não foi possível cadastrar a obra. Tente novamente.',
  // Balcão V2 (circulação e consultas de funcionário).
  client_required: 'Este usuário não possui cadastro de cliente.',
  client_ineligible: 'O cliente está inativo, penalizado ou com empréstimo em atraso.',
  loan_request_not_found: 'A solicitação de empréstimo não foi encontrada. Atualize a lista.',
  pickup_already_confirmed: 'A retirada desta solicitação já foi confirmada.',
  loan_unavailable: 'O exemplar escolhido não está mais disponível para retirada.',
  copy_not_for_loan: 'Somente exemplares didáticos podem ser emprestados. Escolha outro exemplar.',
  loan_not_found: 'O empréstimo não foi encontrado. Atualize a lista.',
  loan_already_closed: 'Este empréstimo já foi encerrado.',
  book_not_found: 'A obra não foi encontrada ou está inativa.',
  reservation_not_found: 'Reserva não encontrada ou sem fila aguardando. Atualize a lista.',
  reservation_not_ready: 'Esta reserva ainda não tem exemplar destinado para retirada.',
  reservation_expired: 'O prazo de retirada desta reserva expirou.',
  reservation_not_cancellable: 'Esta reserva já foi encerrada e não pode ser cancelada. Atualize a lista.',
  no_eligible_reservation: 'Nenhuma reserva da fila tem cliente elegível no momento. Nada foi destinado.',
  purchase_unavailable: 'Não há exemplar comercial livre para esta operação.',
  circulation_persistence_error: 'Não foi possível concluir a operação. Nada foi alterado; tente novamente.',
  search_term_too_short: 'Informe ao menos 2 caracteres para buscar.',
  search_term_required: 'Informe o código do exemplar, o ISBN ou o título.',
  desk_query_error: 'Não foi possível consultar o balcão. Tente novamente.',
  // Exclusão de exemplar e inativação de obra (Issue #135).
  copy_not_found: 'O exemplar não foi encontrado. Atualize a obra.',
  copy_not_available: 'Este exemplar não está disponível e não pode ser excluído.',
  copy_has_history: 'Este exemplar possui histórico (empréstimo, venda, reserva ou solicitação) e não pode ser excluído.',
  last_active_copy: 'Este é o último exemplar ativo de uma obra ativa e não pode ser excluído.',
  copy_delete_persistence_error: 'Não foi possível excluir o exemplar. Nada foi alterado; tente novamente.',
  copy_without_price: 'Este exemplar comercial não tem preço de venda cadastrado e não pode ser vendido.',
  book_inactive: 'A obra deste exemplar está inativa e não aceita novas operações.',
  book_has_active_operations: 'Esta obra possui operações em andamento e não pode ser inativada.',
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

function readDetails(body: unknown): unknown {
  if (typeof body !== 'object' || body === null || !('details' in body)) {
    return undefined;
  }
  return (body as { details: unknown }).details ?? undefined;
}

function readValidationErrors(body: unknown): ApiValidationError[] | undefined {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return undefined;
  }

  const detail = (body as { detail: unknown }).detail;
  if (!Array.isArray(detail)) {
    return undefined;
  }

  const errors = detail.flatMap((item): ApiValidationError[] => {
    if (typeof item !== 'object' || item === null || !('msg' in item)) {
      return [];
    }
    const message = (item as { msg: unknown }).msg;
    const location = 'loc' in item ? (item as { loc: unknown }).loc : undefined;
    if (typeof message !== 'string') {
      return [];
    }
    const field = Array.isArray(location)
      ? [...location].reverse().find((part): part is string => typeof part === 'string')
      : undefined;
    return [{ field, message }];
  });

  return errors.length ? errors : undefined;
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
    validationErrors: readValidationErrors(error.error),
    details: readDetails(error.error),
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
