"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import get_settings
from .db import init_db
from .errors import AppError
from .routers import projects, prompts, system
from .security import BodyTooLarge, SecurityMiddleware
from .services.ai_service import JobManager, LocalModelService, ProviderFactory, default_provider_factory

log = logging.getLogger("prompt_studio")


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


def create_app(provider_factory: ProviderFactory | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        yield
        await app.state.jobs.cancel_all()

    # Interactive docs are disabled: Swagger UI loads assets from a CDN, which
    # would be an external request. /api/openapi.json remains available.
    app = FastAPI(
        title="Prompt Studio API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    service = LocalModelService(provider_factory or default_provider_factory)
    app.state.local_models = service
    app.state.jobs = JobManager(service)

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = [{"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg", "")} for e in exc.errors()[:20]]
        return _error(422, "validation_error", "Request validation failed.", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, code, str(exc.detail) if exc.status_code < 500 else "Server error.")

    @app.exception_handler(BodyTooLarge)
    async def too_large(_: Request, __: BodyTooLarge):
        return _error(413, "payload_too_large", "Request body is too large.")

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, exc: IntegrityError):
        log.warning("Integrity error: %s", type(exc.orig).__name__)
        return _error(409, "integrity_error", "The change conflicts with existing data and was not saved.")

    @app.exception_handler(OperationalError)
    async def operational_error(_: Request, exc: OperationalError):
        log.error("Database operational error: %s", type(exc.orig).__name__)
        return _error(
            503,
            "database_unavailable",
            "The database is unavailable (locked, read-only or missing). No changes were saved.",
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error(_: Request, exc: SQLAlchemyError):
        log.error("Database error: %s", type(exc).__name__)
        return _error(500, "database_error", "A database error occurred. No changes were saved.")

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.error("Unhandled error: %s", type(exc).__name__)  # no message: may contain user content
        return _error(500, "internal_error", "An unexpected error occurred.")

    app.include_router(system.router)
    app.include_router(projects.router)
    app.include_router(prompts.router)
    app.add_middleware(SecurityMiddleware, settings=settings)
    return app


app = create_app()
