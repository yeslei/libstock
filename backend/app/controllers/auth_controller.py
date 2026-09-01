from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_auth_service
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, MessageResponse
from app.schemas.token_schema import TokenResponse
from app.schemas.user_schema import UserCreate, UserResponse
from app.services.auth_service import AuthenticationResult, AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])
settings = get_settings()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def token_response(result: AuthenticationResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.access_token_expires_in,
        user=UserResponse.model_validate(result.user),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    return auth_service.register(data)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    result = auth_service.login(str(data.email), data.password)
    set_refresh_cookie(response, result.refresh_token)
    return token_response(result)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.refresh_cookie_name,
    ),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    if refresh_token is None:
        raise InvalidTokenError("Refresh token não informado.")
    result = auth_service.refresh(refresh_token)
    set_refresh_cookie(response, result.refresh_token)
    return token_response(result)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.refresh_cookie_name,
    ),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    auth_service.logout(refresh_token)
    delete_refresh_cookie(response)
    return MessageResponse(message="Sessão encerrada com sucesso.")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    auth_service.logout_all(current_user.id)
    delete_refresh_cookie(response)
    return MessageResponse(message="Todas as sessões foram encerradas.")
