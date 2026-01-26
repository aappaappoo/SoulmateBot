"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from config import settings
from src.models.database import Base


# Determine connect_args based on database type
def get_connect_args(database_url: str) -> dict:
    """Get database-specific connection arguments"""
    if database_url.startswith("sqlite"):
        # SQLite doesn't support connect_timeout
        return {"check_same_thread": False}
    elif database_url.startswith("postgresql") or database_url.startswith("postgres"):
        return {"connect_timeout": 10}
    else:
        return {}


# Create database engine
_connect_args = get_connect_args(settings.database_url)
_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.sql_echo,  # Controlled by SQL_ECHO env var, defaults to False
    # SQLite doesn't support pool_timeout and pool_recycle the same way
    **({} if _is_sqlite else {"pool_timeout": 30, "pool_recycle": 1800}),
    connect_args=_connect_args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session with context manager
    
    Usage:
        with get_db() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get database session (for dependency injection)
    
    Usage in handlers:
        db = get_db_session()
        try:
            user = db.query(User).first()
            db.commit()
        finally:
            db.close()
    """
    return SessionLocal()
