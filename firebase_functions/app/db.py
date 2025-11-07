import os
import logging
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session


# Module-level references to engine and session factory so other modules can import.
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _build_db_url_from_parts() -> Optional[str]:
    """
    Build a SQLAlchemy PostgreSQL URL from individual environment variables if POSTGRES_URL is not provided.
    Expected env vars:
      - POSTGRES_HOST
      - POSTGRES_PORT (default: 5432)
      - POSTGRES_DB
      - POSTGRES_USER
      - POSTGRES_PASSWORD
    Returns:
      A SQLAlchemy PostgreSQL URL string or None if required parts are missing.
    """
    host = os.getenv("POSTGRES_HOST")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    port = os.getenv("POSTGRES_PORT", "5432")

    # Require minimal pieces
    if not all([host, db, user, password]):
        return None

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def _get_database_url() -> Optional[str]:
    """
    Resolve database URL from environment variables using the following precedence:
      1) POSTGRES_URL
      2) Construct from POSTGRES_HOST/PORT/DB/USER/PASSWORD
    """
    direct = os.getenv("POSTGRES_URL")
    if direct:
        return direct
    return _build_db_url_from_parts()


# PUBLIC_INTERFACE
def init_engine(echo: bool = False, pool_pre_ping: bool = True, pool_size: int = 5, max_overflow: int = 10) -> Optional[Engine]:
    """
    Initialize and return a global SQLAlchemy Engine based on environment configuration.

    Parameters:
      - echo: Enable SQLAlchemy echo for debugging SQL.
      - pool_pre_ping: Enable engine pool_pre_ping to validate connections before using them.
      - pool_size: The size of the connection pool to maintain.
      - max_overflow: The maximum number of connections to allow in connection pool overflow.

    Returns:
      The initialized SQLAlchemy Engine instance or None if configuration is missing.
    """
    global _engine
    if _engine is not None:
        return _engine

    db_url = _get_database_url()
    if not db_url:
        logging.warning("Database configuration missing. Set POSTGRES_URL or POSTGRES_HOST/PORT/DB/USER/PASSWORD.")
        return None

    try:
        _engine = create_engine(
            db_url,
            echo=echo,
            pool_pre_ping=pool_pre_ping,
            pool_size=pool_size,
            max_overflow=max_overflow,
            future=True,
        )
        return _engine
    except SQLAlchemyError as exc:
        logging.exception("Failed to create database engine: %s", exc)
        _engine = None
        return None


# PUBLIC_INTERFACE
def init_session_factory() -> Optional[sessionmaker]:
    """
    Initialize the global session factory bound to the engine. Engine will be created if necessary.

    Returns:
      A sessionmaker instance or None on failure.
    """
    global _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    engine = init_engine()
    if engine is None:
        return None

    try:
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        return _SessionLocal
    except SQLAlchemyError as exc:
        logging.exception("Failed to create session factory: %s", exc)
        _SessionLocal = None
        return None


# PUBLIC_INTERFACE
def get_db_session() -> Optional[Session]:
    """
    Create and return a new SQLAlchemy Session from the global session factory.
    Caller is responsible for closing the session (session.close()).

    Returns:
      A new Session or None if session factory is not available.
    """
    factory = init_session_factory()
    if factory is None:
        return None
    return factory()


# PUBLIC_INTERFACE
def test_connection() -> Dict[str, Any]:
    """
    Attempt a lightweight DB connectivity check.
    Executes a simple SELECT 1 query and returns a status dictionary.

    Returns:
      {
        "ok": bool,
        "message": str
      }
    """
    engine = init_engine()
    if engine is None:
        return {"ok": False, "message": "Database engine not initialized. Check environment variables."}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "message": "Database connection OK"}
    except OperationalError as exc:
        logging.error("Database connection failed (OperationalError): %s", exc)
        return {"ok": False, "message": f"OperationalError: {exc}"}
    except SQLAlchemyError as exc:
        logging.error("Database connection failed (SQLAlchemyError): %s", exc)
        return {"ok": False, "message": f"SQLAlchemyError: {exc}"}
    except Exception as exc:  # Catch-all for unexpected errors
        logging.exception("Unexpected error during DB connection test: %s", exc)
        return {"ok": False, "message": f"Unexpected error: {exc}"}
