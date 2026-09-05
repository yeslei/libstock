from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.admin_catalog_controller import router as admin_catalog_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.book_controller import router as book_router
from app.controllers.catalog_controller import router as catalog_router
from app.controllers.employee_controller import router as employee_router
from app.controllers.user_controller import router as user_router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError


settings = get_settings()

app = FastAPI(
    title="LibStock API",
    version="0.1.0",
    description="API para gestão de acervos e circulação de livros.",
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
    return JSONResponse(
        status_code=exception.status_code,
        content={"detail": exception.message, "code": exception.code},
        headers=headers,
    )


@app.get("/health", tags=["Infraestrutura"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(employee_router)
app.include_router(book_router)
app.include_router(catalog_router)
app.include_router(admin_catalog_router)