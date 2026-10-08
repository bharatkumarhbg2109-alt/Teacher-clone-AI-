# core/logging_config.py
"""Structured JSON logging for local backend — logs to SQLite + console."""
import logging
import json
import time
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "graph_db" / "ingestor.db"


class SQLiteHandler(logging.Handler):
    """Writes structured log records to SQLite for Electron log viewer."""

    def __init__(self):
        super().__init__()
        self._init_db()

    def _init_db(self):
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backend_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    level TEXT,
                    logger TEXT,
                    message TEXT,
                    extra TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def emit(self, record):
        try:
            extra = {
                k: v for k, v in record.__dict__.items()
                if k not in logging.LogRecord.__dict__ and isinstance(v, (str, int, float, bool))
            }
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "INSERT INTO backend_logs (timestamp, level, logger, message, extra) VALUES (?,?,?,?,?)",
                (record.created, record.levelname, record.name,
                 record.getMessage(), json.dumps(extra))
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Never let logging crash the app


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Console handler — human readable
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(console)

    # SQLite handler — structured
    root.addHandler(SQLiteHandler())

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return logging.getLogger("ai_teacher")
