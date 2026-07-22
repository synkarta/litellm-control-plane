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
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)

        # Additive column migrations — safe to run on existing databases.
        # SQLite does not support ALTER TABLE ADD COLUMN IF NOT EXISTS,
        # so we catch OperationalError and ignore it when the column already exists.
        _safe_add_column(conn, "incidents", "raw_response", "TEXT")
        _safe_add_column(conn, "accounts", "cooldown_until", "TEXT")
        _safe_add_column(conn, "accounts", "failure_count", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "endpoints", "cooldown_until", "TEXT")
        _safe_add_column(conn, "endpoints", "failure_count", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "consumers", "profile_id", "TEXT")

        conn.commit()
    finally:
        conn.close()

def _safe_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it does not already exist."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # Column already exists


@contextmanager
def get_db(db_path: str | None = None):
    """Context manager to yield a database connection with foreign keys enabled."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
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

