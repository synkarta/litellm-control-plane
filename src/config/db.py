import os
import sqlite3
from contextlib import contextmanager

# Default fallback path — prefer reading env at call-time via get_db_path()
_DEFAULT_DB_PATH = "control_plane.db"

def get_db_path() -> str:
    """Read the active database path at call-time so env overrides take effect."""
    return os.getenv("DATABASE_URL", _DEFAULT_DB_PATH)

# Kept for backward compatibility in CLI imports (bootstrap.py)
DB_PATH = _DEFAULT_DB_PATH

def init_db(db_path: str | None = None) -> None:
    """Initialize the SQLite database by running schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

@contextmanager
def get_db(db_path: str | None = None):
    """Context manager to yield a database connection with foreign keys enabled."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db_dep():
    """FastAPI dependency that yields a connection and closes it afterward."""
    with get_db(get_db_path()) as conn:
        yield conn

