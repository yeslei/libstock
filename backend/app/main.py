from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.admin_catalog_controller import router as admin_catalog_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.book_controller import router as book_router
from app.controllers.catalog_controller import router as catalog_router
from app.controllers.employee_controller import router as employee_router
from app.controllers.copy_controller import router as copy_router
from app.controllers.user_controller import router as user_router
from app.controllers.loan_request_controller import router as loan_request_router
from app.controllers.purchase_request_controller import router as purchase_request_router
from app.controllers.client_tracking_controller import router as client_tracking_router
from app.controllers.circulation_controller import router as circulation_router
from app.controllers.staff_desk_controller import router as staff_desk_router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.controllers.client_pendency_controller import (
    router as client_pendency_router,
)
from app.controllers.loan_controller import router as loan_router
from app.controllers.sale_controller import router as sale_router


settings = get_settings()

# Em produção a documentação interativa fica fora do ar: ela publica o
# desenho inteiro da API — rotas administrativas, formato dos corpos e quais
# papéis cada operação exige — para qualquer visitante.
_documentacao_publica = settings.app_env != "production"

app = FastAPI(
    title="LibStock API",
    version="0.1.0",
    description="API para gestão de acervos e circulação de livros.",
    docs_url="/docs" if _documentacao_publica else None,
    redoc_url="/redoc" if _documentacao_publica else None,
    openapi_url="/openapi.json" if _documentacao_publica else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApplicationError)
async def application_error_handler(
    _request: Request,
    exception: ApplicationError,
) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exception.status_code == 401 else None
    content: dict[str, object] = {"detail": exception.message, "code": exception.code}
    if exception.details is not None:
        content["details"] = exception.details
    return JSONResponse(
        status_code=exception.status_code,
        content=content,
        headers=headers,
    )


@app.get("/health", tags=["Infraestrutura"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(employee_router)
app.include_router(copy_router)
app.include_router(book_router)
app.include_router(catalog_router)
app.include_router(admin_catalog_router)
app.include_router(loan_request_router)
app.include_router(purchase_request_router)
app.include_router(client_tracking_router)

app.include_router(circulation_router)
app.include_router(staff_desk_router)
app.include_router(client_pendency_router)
app.include_router(loan_router)
app.include_router(sale_router)
