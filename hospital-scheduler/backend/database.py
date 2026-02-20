"""
Database setup and session management.

Uses SQLite for v1 local deployment. Schema is designed to be
PostgreSQL-compatible for v2 web deployment.

v2: Replace SQLite with PostgreSQL via DATABASE_URL env var,
add connection pooling, migration support (Alembic).
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import Base

DATABASE_URL = "sqlite:///./scheduler.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite-specific
    echo=False,
)

# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session.
    Ensures session is closed after request completes.

    v2: Add request-scoped session with proper transaction management.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
