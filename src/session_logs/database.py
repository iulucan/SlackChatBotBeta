"""
database.py -- GreenLeaf Bot | Logging Database Layer
======================================================
Handles all SQLite database operations for interaction logging.

Responsibilities:
    - Create the database and interactions table if they don't exist
    - Log each bot interaction with anonymous session IDs (never real names)
    - Clean up records older than 12 months (GDPR retention policy)

Privacy model:
    - Only session_id and conversation_id are stored (never real names or Slack IDs)
    - Masked messages from privacy_gate.py are what gets logged
    - Records are deleted after 12 months via cleanup_old_records()

Database location: data/greenleaf.db
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

# Path to the SQLite database file -- relative to project root
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DATABASE_PATH = os.path.join(PROJECT_ROOT, "data", "greenleaf.db")


class LoggingDatabase:
    """
    Manages the SQLite database for GreenLeaf bot interaction logs.

    Usage:
        db = LoggingDatabase()

        # Log an interaction
        db.log_interaction(
            session_id="0c85646c",
            conversation_id="beat_2026_H1",
            masked_message="What is the expense policy for meals?",
            intent="expense",
            tool_used="expense_tool",
            outcome="success"
        )

        # Clean up old records (run every 6 months)
        db.cleanup_old_records()
    """

    def __init__(self, db_path: str = DATABASE_PATH):
        self._db_path = db_path
        self._ensure_data_folder()
        self.init_schema()

    # -------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------

    def init_schema(self):
        """
        Creates the interactions table if it does not exist yet.
        Safe to call multiple times -- will never overwrite existing data.
        """
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id       VARCHAR(8)  NOT NULL,
                    conversation_id  VARCHAR(50) NOT NULL,
                    masked_message   TEXT        NOT NULL,
                    timestamp        DATETIME    DEFAULT CURRENT_TIMESTAMP,
                    intent           VARCHAR(100),
                    tool_used        VARCHAR(100),
                    outcome          VARCHAR(50)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON interactions (session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_id
                ON interactions (conversation_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON interactions (timestamp)
            """)
            conn.commit()
        print(f"[DB] Schema ready at: {self._db_path}")

    def log_interaction(
        self,
        session_id: str,
        conversation_id: str,
        masked_message: str,
        intent: Optional[str] = None,
        tool_used: Optional[str] = None,
        outcome: Optional[str] = None,
    ):
        """
        Inserts one interaction log entry into the database.

        Args:
            session_id:      8-char anonymous ID (e.g. "0c85646c")
            conversation_id: Human-readable period ID (e.g. "beat_2026_H1")
            masked_message:  The message after PII masking by privacy_gate
            intent:          Classified intent (e.g. "policy", "holiday", "expense")
            tool_used:       Tool that handled the request (e.g. "expense_tool")
            outcome:         Result of the interaction ("success" or "error")
        """
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO interactions
                        (session_id, conversation_id, masked_message, intent, tool_used, outcome)
                    VALUES
                        (?, ?, ?, ?, ?, ?)
                """,
                    (
                        session_id,
                        conversation_id,
                        masked_message,
                        intent,
                        tool_used,
                        outcome,
                    ),
                )
                conn.commit()
            print(
                f"[DB] Logged interaction -- session: {session_id}, intent: {intent}, outcome: {outcome}"
            )

        except Exception as e:
            # Never let a logging failure crash the bot
            print(f"[DB ERROR] Failed to log interaction: {e}")

    def cleanup_old_records(self, months: int = 12):
        """
        Deletes records older than the specified number of months.
        Default is 12 months (GDPR retention policy).

        Args:
            months: Number of months to retain records (default 12)

        Run this manually every 6 months:
            python cleanup.py
        """
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM interactions
                    WHERE timestamp < ?
                """,
                    (cutoff_str,),
                )
                conn.commit()
                deleted = cursor.rowcount
            print(
                f"[DB] Cleanup complete -- deleted {deleted} records older than {months} months"
            )

        except Exception as e:
            print(f"[DB ERROR] Cleanup failed: {e}")

    # -------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Opens and returns a connection to the SQLite database."""
        return sqlite3.connect(self._db_path)

    def _ensure_data_folder(self):
        """Creates the data/ folder if it does not exist yet."""
        folder = os.path.dirname(self._db_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
            print(f"[DB] Created folder: {folder}")
