import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Optional


class SignalStorage:
    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
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
        # check recent hashes within the last 6 hours
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

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
