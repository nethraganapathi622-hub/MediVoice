import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Engine creation with pool pre-ping to detect broken connections
# and connection timeout for PostgreSQL
connect_args = {}
if "postgresql" in settings.DATABASE_URL or "postgres" in settings.DATABASE_URL:
    connect_args["connect_timeout"] = settings.DATABASE_CONNECT_TIMEOUT
elif "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection(db: Session) -> bool:
    """Execute a query against the database to verify connectivity.

    Raises an exception if the database connection cannot be established.
    """
    db.execute(text("SELECT 1"))
    return True
