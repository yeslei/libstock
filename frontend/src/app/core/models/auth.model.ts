import { User } from './user.model';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

/** Resposta de `POST /login` e `POST /refresh`. */
export interface AuthSession {
  readonly access_token: string;
  readonly token_type: string;
  readonly expires_in: number;
  readonly user: User;
}

export interface MessageResponse {
  readonly message: string;
}

/** Formato de erro do backend: `{ detail, code }`. */
export interface ApiError {
  /** Mensagem legível — pode ser exibida ao usuário. */
  readonly detail: string;
  /** Código interno estável — use para lógica condicional. */
  readonly code?: string;
  readonly status: number;
  /** Erros estruturados do FastAPI/Pydantic (normalmente em respostas 422). */
  readonly validationErrors?: readonly ApiValidationError[];
}

export interface ApiValidationError {
  readonly field?: string;
  readonly message: string;
}

/**
 * Estado do formulário como união discriminada: flags booleanas soltas
 * (`isLoading` + `hasError` + `isSuccess`) permitiriam combinações inválidas.
 */
export type FormState =
  | { status: 'idle' }
  | { status: 'submitting' }
  | { status: 'success'; message: string }
  | { status: 'error'; message: string; code?: string };
