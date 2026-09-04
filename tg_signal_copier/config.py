from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    api_id: int
    api_hash: str
    session_name: str
    source_channels: list[str]
    webhook_url: str
    webhook_secret: str | None = None
    http_timeout_seconds: float = 5.0
    database_path: Path = Path("signals.db")

    @classmethod
    def from_env(cls) -> AppConfig:
        api_id_raw = os.getenv("TG_API_ID")
        api_hash = os.getenv("TG_API_HASH")
        if not api_id_raw or not api_hash:
            raise ValueError("TG_API_ID and TG_API_HASH environment variables are required")

        channels_raw = os.getenv("SOURCE_CHANNELS", "")
        channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
        if not channels:
            raise ValueError("SOURCE_CHANNELS cannot be empty")

        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("WEBHOOK_URL is required")

        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            session_name=os.getenv("TG_SESSION_NAME", "signal_copier"),
            source_channels=channels,
            webhook_url=webhook_url,
            webhook_secret=os.getenv("WEBHOOK_SECRET"),
            http_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT", "5.0")),
            database_path=Path(os.getenv("DATABASE_PATH", "signals.db")),
        )
