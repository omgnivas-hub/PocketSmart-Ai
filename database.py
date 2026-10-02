"""SQLite persistence for users and recommendation history (standard library only)."""
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Optional

import config as cfg


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username      TEXT PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE,
                full_name     TEXT,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id             TEXT PRIMARY KEY,
                username       TEXT NOT NULL,
                rec_type       TEXT NOT NULL,
                created_at     TEXT NOT NULL,
                input_json     TEXT NOT NULL,
                result_json    TEXT NOT NULL,
                input_summary  TEXT,
                result_summary TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_history_user ON history (username, created_at DESC);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ users
def create_user(username: str, email: str, full_name: Optional[str], password_hash: str) -> None:
    """Raises sqlite3.IntegrityError if the username or email already exists."""
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users (username, email, full_name, password_hash, created_at) VALUES (?,?,?,?,?)",
            (username, email, full_name, password_hash, _now()),
        )


def get_user(username: str) -> Optional[dict]:
    with closing(_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with closing(_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------ history
def save_history(username: str, rec_type: str, input_data: dict, result: dict,
                 input_summary: str, result_summary: str) -> str:
    hid = uuid.uuid4().hex
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO history (id, username, rec_type, created_at, input_json, result_json,"
            " input_summary, result_summary) VALUES (?,?,?,?,?,?,?,?)",
            (hid, username, rec_type, _now(), json.dumps(input_data), json.dumps(result),
             input_summary, result_summary),
        )
    return hid


def list_history(username: str, limit: int = 50) -> list[dict[str, Any]]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM history WHERE username = ? ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    items = []
    for r in rows:
        result = json.loads(r["result_json"])
        items.append({
            "id": r["id"],
            "created_at": r["created_at"],
            "rec_type": r["rec_type"],
            "input_summary": r["input_summary"],
            "result_summary": r["result_summary"],
            "input_data": json.loads(r["input_json"]),
            "total_budget": result.get("total_budget"),
            "remaining_budget": result.get("remaining_budget"),
        })
    return items


def get_history_item(username: str, hid: str) -> Optional[dict[str, Any]]:
    with closing(_conn()) as conn:
        r = conn.execute("SELECT * FROM history WHERE id = ? AND username = ?", (hid, username)).fetchone()
    if not r:
        return None
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "rec_type": r["rec_type"],
        "input_summary": r["input_summary"],
        "input_data": json.loads(r["input_json"]),
        "full_result": json.loads(r["result_json"]),
    }
