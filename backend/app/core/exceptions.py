class ApplicationError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        # Dados estruturados opcionais (ex.: motivos de um bloqueio de domínio).
        self.details = details


class DuplicateEmailError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("E-mail já cadastrado.", "duplicate_email", 409)


class DuplicateEmployeeCodeError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Código de funcionário já cadastrado.", "duplicate_employee_code", 409)


class PersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Não foi possível concluir o cadastro.", "persistence_error", 500)


class InactiveUserError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Usuário inativo.", "inactive_user", 403)


class InvalidEmployeeRoleError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Nível de acesso inválido.", "invalid_employee_role", 422)


class InvalidCredentialsError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("E-mail ou senha inválidos.", "invalid_credentials", 401)


class InvalidTokenError(ApplicationError):
    def __init__(self, message: str = "Token inválido ou expirado.") -> None:
        super().__init__(message, "invalid_token", 401)


class PermissionDeniedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Permissão insuficiente.", "permission_denied", 403)


class RefreshTokenReuseError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Reutilização de refresh token detectada. Faça login novamente.",
            "refresh_token_reuse",
            401,
        )


class BookNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Livro não encontrado.", "book_not_found", 404)


class DuplicateIsbnError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("ISBN já cadastrado.", "duplicate_isbn", 409)


class DuplicateBarcodeError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Código de barras já cadastrado.", "duplicate_barcode", 409)


class EmployeeRecordRequiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O usuário autenticado não possui cadastro de funcionário.",
            "employee_record_required",
            403,
        )


class AuditActorRequiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Operação de acervo exige um usuário vinculado a um funcionário.",
            "audit_actor_required",
            403,
        )


class GoogleBooksNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "ISBN não encontrado na base externa do Google Books.",
            "google_books_not_found",
            404,
        )


class GoogleBooksUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível consultar o Google Books.",
            "google_books_unavailable",
            503,
        )


class GoogleBooksRateLimitError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O Google Books está temporariamente indisponível por excesso de consultas.",
            "google_books_rate_limited",
            503,
        )


class GoogleBooksInvalidResponseError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O Google Books não retornou os dados obrigatórios da obra.",
            "google_books_invalid_response",
            502,
        )


class BookPersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível cadastrar a obra.",
            "book_persistence_error",
            500,
        )


class BookUpdatePersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível atualizar a obra.",
            "book_update_persistence_error",
            500,
        )


class DuplicateGenreError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Gênero já cadastrado.", "duplicate_genre", 409)


class GenreNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Gênero não encontrado.", "genre_not_found", 404)


class UserNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Usuário não encontrado.", "user_not_found", 404)


class UserInactiveError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Usuário inativo.", "user_inactive", 403)


class UserAlreadyInactiveError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("O usuário já está inativo.", "user_already_inactive", 409)


class UserSelfInactivationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Um administrador não pode inativar a si mesmo.",
            "user_self_inactivation",
            422,
        )


class UserSelfRoleRemovalError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Um administrador não pode remover o próprio acesso administrativo.",
            "user_self_role_removal",
            422,
        )


class LastActiveAdministratorError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O último administrador ativo não pode perder o acesso.",
            "last_active_administrator",
            409,
        )

class ClientNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Cliente não encontrado.",
            "client_not_found",
            404,
        )


class ClientInactiveError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Cliente inativo.",
            "client_inactive",
            403,
        )


class ClientHasPendingError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Cliente possui pendência ativa e não pode realizar a operação.",
            "client_has_pending",
            409,
        )


class ClientPenaltyApplicationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O cliente não possui pendência ativa para aplicação da penalidade.",
            "client_penalty_application_error",
            409,
        )


class ClientPenaltyRemovalError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O cliente ainda possui pendência ativa e não pode ser desbloqueado.",
            "client_penalty_removal_error",
            409,
        )


class ClientPenaltyPersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível atualizar a situação de penalização do cliente.",
            "client_penalty_persistence_error",
            500,
        )


class CopyWithoutPriceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "O exemplar comercial não tem preço de venda cadastrado.",
            "copy_without_price",
            409,
        )


class BookInactiveError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "A obra do exemplar está inativa e não aceita novas operações.",
            "book_inactive",
            409,
        )


class CopyNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Exemplar não encontrado.", "copy_not_found", 404)


class CopyDeletionBlockedError(ApplicationError):
    """Exclusão de exemplar bloqueada. O código é o do primeiro motivo.

    Os motivos possíveis são `copy_not_available`, `copy_has_history` e
    `last_active_copy`; todos seguem em `details["reasons"]`.
    """

    def __init__(self, reasons: list[dict], history: dict[str, int]) -> None:
        message = "Exclusão bloqueada: " + " ".join(reason["message"] for reason in reasons)
        super().__init__(
            message,
            reasons[0]["code"],
            409,
            {"reasons": reasons, "history": history},
        )


class CopyDeletionPersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível excluir o exemplar. Nada foi alterado.",
            "copy_delete_persistence_error",
            500,
        )


class BookHasActiveOperationsError(ApplicationError):
    def __init__(self, counts: dict[str, int], links: list[dict]) -> None:
        super().__init__(
            "A obra possui operações em andamento e não pode ser inativada.",
            "book_has_active_operations",
            409,
            {"counts": counts, "links": links},
        )


class CopyNotForLoanError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Somente exemplares didáticos podem ser emprestados.", "copy_not_for_loan", 409)


class BookWithoutActiveCopyError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "A obra não pode ser reativada sem ao menos um exemplar ativo.",
            "book_without_active_copy",
            409,
        )


class CopyUpdateBlockedError(ApplicationError):
    """Edição/conversão de exemplar bloqueada. O código é o do primeiro motivo.

    Os motivos possíveis são `copy_inactive`, `copy_not_available`,
    `copy_allocated` e `copy_in_operation`; todos seguem em `details["reasons"]`.
    """

    def __init__(self, reasons: list[dict]) -> None:
        message = "Edição bloqueada: " + " ".join(reason["message"] for reason in reasons)
        super().__init__(message, reasons[0]["code"], 409, {"reasons": reasons})


class CopySalePriceRequiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Exemplar destinado à venda exige preço de venda maior que zero.",
            "copy_sale_price_required",
            422,
        )


class CopySalePriceNotAllowedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Exemplar didático não pode ter preço de venda.",
            "copy_sale_price_not_allowed",
            422,
        )


class CopyUpdatePersistenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "Não foi possível atualizar o exemplar. Nada foi alterado.",
            "copy_update_persistence_error",
            500,
        )


# SQLSTATEs próprios do gatilho `guard_copy_integrity` (migration 20261003_0014).
SQLSTATE_COPY_DESTINATION_FORBIDDEN = "LS001"
SQLSTATE_COPY_DESTINATION_NOT_AVAILABLE = "LS002"
