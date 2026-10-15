import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import anyio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.rate_limit import InMemoryRateLimiter
from backend.app.core.request_limits import RequestBodyLimitMiddleware
from backend.app.ml.registry import (
    ArtifactValidationError,
    FeedbackConflictError,
    MLIntegrationError,
    ModelNotFoundError,
    NoActiveModelError,
    PredictionExecutionError,
)
from backend.app.services.accounting import AccountingError, ConflictError, NotFoundError
from backend.app.services.school import SchoolAccessError


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings: Settings = application.state.settings
    capacity = min(
        settings.DB_MAX_CONCURRENT_SESSIONS, settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    )
    if capacity >= anyio.to_thread.current_default_thread_limiter().total_tokens:
        raise RuntimeError("Database admission must leave worker capacity for request completion")
    application.state.db_limiter = anyio.CapacityLimiter(capacity)
    settings.ML_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    application.state.auth_rate_limiter.clear()
    yield


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Create the application without module-level mutable configuration."""
    settings = settings_override or get_settings()
    is_production = settings.APP_ENV.casefold() == "production"
    application = FastAPI(
        title=settings.APP_NAME,
        version="0.2.0",
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    application.state.settings = settings
    application.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.MAX_REQUEST_BYTES)
    application.state.auth_rate_limiter = InMemoryRateLimiter(
        settings.AUTH_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        # Identity is carried by an explicit Bearer header, never ambient cookies.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @application.exception_handler(PoolTimeoutError)
    @application.exception_handler(OperationalError)
    async def database_unavailable(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable"},
            headers={"Retry-After": "1"},
        )

    @application.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            if not is_production:
                raise
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        route = request.scope.get("route")
        event = json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method[:16],
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
        )
        logger = logging.getLogger("uvicorn.error.security")
        level = (
            logging.ERROR
            if response.status_code >= 500
            else logging.WARNING
            if response.status_code in {401, 403, 429}
            else logging.INFO
        )
        logger.log(level, event)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith(settings.API_V1_PREFIX):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @application.exception_handler(SchoolAccessError)
    async def school_access_error(_: Request, exc: SchoolAccessError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(AccountingError)
    async def accounting_error_handler(_: Request, exc: AccountingError) -> JSONResponse:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if isinstance(exc, NotFoundError):
            code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ConflictError):
            code = status.HTTP_409_CONFLICT
        return JSONResponse(status_code=code, content={"detail": str(exc)})

    @application.exception_handler(MLIntegrationError)
    async def ml_error_handler(_: Request, exc: MLIntegrationError) -> JSONResponse:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if isinstance(exc, (ModelNotFoundError, NoActiveModelError)):
            code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, FeedbackConflictError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(exc, PredictionExecutionError):
            code = status.HTTP_503_SERVICE_UNAVAILABLE
        message = str(exc)
        if isinstance(exc, ArtifactValidationError):
            message = "Model artifact is unavailable or incompatible"
        return JSONResponse(status_code=code, content={"detail": message})

    if is_production:

        @application.exception_handler(Exception)
        async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

    return application


app = create_app()
