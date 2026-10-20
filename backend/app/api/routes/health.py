import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import check_database_connection, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Liveness probe", status_code=status.HTTP_200_OK)
def get_health(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Return basic service health and metadata."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
    }


@router.get("/ready", summary="Readiness probe")
def get_readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Verify application readiness by testing live database connectivity."""
    try:
        check_database_connection(db)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": {
                    "status": "connected",
                    "details": "PostgreSQL connection operational",
                },
                "environment": settings.ENVIRONMENT,
            },
        )
    except Exception as exc:
        # Log the error server-side without exposing internal details/credentials to clients
        logger.error("Readiness check failed due to database connectivity error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": {
                    "status": "disconnected",
                    "details": "Database connection unavailable",
                },
                "environment": settings.ENVIRONMENT,
            },
        )
