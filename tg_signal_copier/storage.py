import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List


class SignalStorage:
    """Local SQLite store for message deduplication and delivery audit log."""

    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            p = Path(self.db_path)
            if p.parent != Path("."):
                p.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    received_at REAL NOT NULL,
                    UNIQUE(channel_id, message_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_seen_hash 
                ON seen_signals(content_hash)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    parsed_payload TEXT,
                    status TEXT NOT NULL,
                    latency_ms REAL,
                    error_msg TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created 
                ON audit_log(created_at)
            """)

    @staticmethod
    def hash_text(text: str) -> str:
        # normalize whitespace so formatting quirks from cross-posts don't slip through
        cleaned = " ".join(text.strip().lower().split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def is_duplicate(self, channel_id: int, message_id: int, text: str) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM seen_signals WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id)
        )
        if cur.fetchone():
            return True

        h = self.hash_text(text)
        # cross-channel reposts usually happen within 2 hours, 6h window is plenty
        cutoff = time.time() - (6 * 3600)
        cur.execute(
            "SELECT 1 FROM seen_signals WHERE content_hash = ? AND received_at > ?",
            (h, cutoff)
        )
        return cur.fetchone() is not None

    def record_signal(self, channel_id: int, message_id: int, text: str):
        conn = self._get_conn()
        h = self.hash_text(text)
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_signals (channel_id, message_id, content_hash, received_at)
                VALUES (?, ?, ?, ?)
                """,
                (channel_id, message_id, h, time.time())
            )

    def log_audit(
        self,
        channel_id: int,
        message_id: int,
        raw_text: str,
        status: str,
        parsed_payload: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
        error_msg: Optional[str] = None,
    ):
        conn = self._get_conn()
        payload_str = json.dumps(parsed_payload) if parsed_payload else None
        with conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    channel_id, message_id, raw_text, parsed_payload, status, latency_ms, error_msg, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (channel_id, message_id, raw_text, payload_str, status, latency_ms, error_msg, time.time())
            )

    def get_recent_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d["parsed_payload"]:
                d["parsed_payload"] = json.loads(d["parsed_payload"])
            out.append(d)
        return out

    def prune_old_records(self, max_age_days: int = 14) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        conn = self._get_conn()
        with conn:
            cur = conn.execute("DELETE FROM seen_signals WHERE received_at < ?", (cutoff,))
            seen_deleted = cur.rowcount
            cur2 = conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff,))
            audit_deleted = cur2.rowcount
        return seen_deleted + audit_deleted

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
