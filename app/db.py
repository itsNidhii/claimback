"""Tiny SQLite store. On Cloud Run the disk is temporary, so cases are lost when the
instance restarts. That is fine for a demo; swap in Firestore later if you need it."""
import json
import os
import sqlite3
import threading
import time
import uuid

_PATH = os.getenv("DB_PATH", "/tmp/claimback.db")
_lock = threading.Lock()
_conn = sqlite3.connect(_PATH, check_same_thread=False)
_conn.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, created REAL, status TEXT, data TEXT)")
_conn.commit()


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def save(case: dict):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO cases (id, created, status, data) VALUES (?,?,?,?)",
            (case["id"], case.get("created", time.time()), case.get("status", ""), json.dumps(case, ensure_ascii=False)),
        )
        _conn.commit()


def get(case_id: str):
    with _lock:
        row = _conn.execute("SELECT data FROM cases WHERE id=?", (case_id,)).fetchone()
    return json.loads(row[0]) if row else None


def delete(case_id: str) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
        _conn.commit()
    return cur.rowcount > 0


def pending():
    with _lock:
        rows = _conn.execute("SELECT data FROM cases WHERE status='pending_review' ORDER BY created ASC").fetchall()
    return [json.loads(r[0]) for r in rows]
