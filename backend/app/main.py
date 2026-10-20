"""MediVoice FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.routes.departments import router as departments_router
from app.api.routes.doctors import router as doctors_router
from app.api.routes.appointments import router as appointments_router
from app.api.routes.queue import router as queue_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.patient_portal import router as patient_portal_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.consultations import router as consultations_router
from app.ws.router import router as ws_router
from app.core.config import get_settings

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("medivoice")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    settings = get_settings()
    logger.info("Starting %s (v%s) in %s mode", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_application() -> FastAPI:
    """Application factory for configuring FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register API routers under configured prefix (e.g., /api)
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(departments_router, prefix=settings.API_V1_PREFIX)
    app.include_router(doctors_router, prefix=settings.API_V1_PREFIX)
    app.include_router(appointments_router, prefix=settings.API_V1_PREFIX)
    app.include_router(queue_router, prefix=settings.API_V1_PREFIX)
    app.include_router(alerts_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(assistant_router, prefix=settings.API_V1_PREFIX)
    app.include_router(patient_portal_router, prefix=settings.API_V1_PREFIX)
    app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
    app.include_router(consultations_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ws_router)

    # Global Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Validation error", "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log stack trace internally without leaking secrets, credentials, or internal details
        logger.exception("Unhandled server error processing request %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please contact system administrator if this persists.",
            },
        )

    return app


app = create_application()
