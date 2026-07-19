import json
import sqlite3
from typing import Any, Dict, Optional

def log_audit(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    changes: Dict[str, Any],
    reason: Optional[str] = None
) -> None:
    """Log a state change event to the append-only audit_logs table."""
    changes_json = json.dumps(changes)
    conn.execute(
        """
        INSERT INTO audit_logs (actor, action, target_type, target_id, changes, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor, action, target_type, target_id, changes_json, reason)
    )
