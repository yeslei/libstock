class ApplicationError(Exception):
    def __init__(self, message: str, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


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


class UserNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Usuário não encontrado.", "user_not_found", 404)
