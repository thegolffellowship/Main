"""
Database setup and session management.

Uses SQLite for v1 local deployment. Schema is designed to be
PostgreSQL-compatible for v2 web deployment.

v2: Replace SQLite with PostgreSQL via DATABASE_URL env var,
add connection pooling, migration support (Alembic).
"""

from sqlalchemy import create_engine, event, inspect, text
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
    """Create all tables if they don't exist, then migrate new columns."""
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def _migrate_columns():
    """Add new columns to existing tables (safe for fresh and existing DBs)."""
    insp = inspect(engine)

    # ScheduleEntry.note
    se_cols = [c['name'] for c in insp.get_columns('schedule_entries')]
    if 'note' not in se_cols:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE schedule_entries ADD COLUMN note TEXT'))
            conn.commit()

    # Employee.max_weekly_shifts
    emp_cols = [c['name'] for c in insp.get_columns('employees')]
    if 'max_weekly_shifts' not in emp_cols:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE employees ADD COLUMN max_weekly_shifts INTEGER DEFAULT 3 NOT NULL'))
            conn.commit()


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
