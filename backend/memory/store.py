"""Persistent memory store — SQLite-backed long-term memory for JARVIS."""

import sqlite3
import json
import time
import threading
from pathlib import Path
from backend.config import MEMORY_DB_PATH


class MemoryStore:
    def __init__(self, db_path: str = MEMORY_DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'fact',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_key ON memories(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_cat ON memories(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id)")
        conn.commit()
        conn.close()

    def save(self, key: str, content: str, category: str = "fact") -> int:
        now = time.time()
        existing = self._conn.execute(
            "SELECT id FROM memories WHERE key = ? AND category = ?", (key, category)
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                (content, now, existing["id"]),
            )
            self._conn.commit()
            return existing["id"]
        else:
            cursor = self._conn.execute(
                "INSERT INTO memories (key, content, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (key, content, category, now, now),
            )
            self._conn.commit()
            return cursor.lastrowid

    def search(self, query: str, category: str | None = None) -> list[dict]:
        sql = "SELECT * FROM memories WHERE (key LIKE ? OR content LIKE ?)"
        params: list = [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY updated_at DESC LIMIT 20"

        rows = self._conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            self._conn.execute(
                "UPDATE memories SET access_count = access_count + 1 WHERE id = ?",
                (row["id"],),
            )
            results.append(dict(row))
        self._conn.commit()
        return results

    def get_recent(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all(self, category: str | None = None) -> list[dict]:
        if category:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC", (category,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM memories ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete(self, memory_id: int) -> bool:
        self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return True

    def save_conversation(self, session_id: str, role: str, content: str):
        self._conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )
        self._conn.commit()

    def get_conversation(self, session_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def log_evolution(self, action: str, details: str = ""):
        self._conn.execute(
            "INSERT INTO evolution_log (action, details, timestamp) VALUES (?, ?, ?)",
            (action, details, time.time()),
        )
        self._conn.commit()


memory_store = MemoryStore()
