"""
Database setup and session management.

Supports both SQLite (local dev) and PostgreSQL (cloud deployment).
Set DATABASE_URL env var to use PostgreSQL, otherwise defaults to SQLite.
"""

import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./scheduler.db")

# Render and Heroku use postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs = {"echo": False}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Enable WAL mode and foreign keys for SQLite only
if is_sqlite:
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
    existing_tables = insp.get_table_names()

    # ScheduleEntry.note
    if 'schedule_entries' in existing_tables:
        se_cols = [c['name'] for c in insp.get_columns('schedule_entries')]
        if 'note' not in se_cols:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE schedule_entries ADD COLUMN note TEXT'))
                conn.commit()

    # Employee.max_weekly_shifts
    if 'employees' in existing_tables:
        emp_cols = [c['name'] for c in insp.get_columns('employees')]
        if 'max_weekly_shifts' not in emp_cols:
            with engine.connect() as conn:
                if is_sqlite:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN max_weekly_shifts INTEGER DEFAULT 3 NOT NULL'))
                else:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN max_weekly_shifts INTEGER DEFAULT 3'))
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
