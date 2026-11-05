
"""
SQLite persistence for Bellhaven reconciliation reviews.

This module creates the database and manages review decisions.
It does not make CRM API requests.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "review_queue.db"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    return connection


def initialize_database():
    """Create review and audit tables if they do not exist."""

    with get_connection() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                issue_key TEXT NOT NULL UNIQUE,
                source_hash TEXT NOT NULL,

                website_name TEXT NOT NULL,
                website_detail_url TEXT NOT NULL,

                crm_account_id TEXT,
                crm_name TEXT,

                review_category TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                field_name TEXT,

                old_value TEXT,
                proposed_value TEXT,

                evidence_json TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'approved',
                            'rejected',
                            'applied',
                            'failed',
                            'needs_re_review'
                        )
                    ),

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                decided_at TEXT,
                applied_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_review_status
            ON review_items(status);

            CREATE INDEX IF NOT EXISTS idx_review_account
            ON review_items(crm_account_id);

            CREATE TABLE IF NOT EXISTS review_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                review_item_id INTEGER NOT NULL,
                decision TEXT NOT NULL
                    CHECK (
                        decision IN (
                            'approved',
                            'rejected',
                            'needs_re_review'
                        )
                    ),

                reviewer TEXT NOT NULL,
                reason TEXT,

                decided_at TEXT NOT NULL,

                FOREIGN KEY (review_item_id)
                    REFERENCES review_items(id)
            );

            CREATE TABLE IF NOT EXISTS write_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                review_item_id INTEGER NOT NULL,

                attempted_at TEXT NOT NULL,
                dry_run INTEGER NOT NULL DEFAULT 1,

                crm_account_id TEXT,
                field_name TEXT,

                old_value TEXT,
                proposed_value TEXT,

                result TEXT NOT NULL,
                response_json TEXT,

                FOREIGN KEY (review_item_id)
                    REFERENCES review_items(id)
            );
            """
        )


def get_review_items(status=None):
    """Return review items, optionally filtered by status."""

    with get_connection() as conn:

        if status is None:
            rows = conn.execute(
                """
                SELECT *
                FROM review_items
                ORDER BY id
                """
            ).fetchall()

        else:
            rows = conn.execute(
                """
                SELECT *
                FROM review_items
                WHERE status = ?
                ORDER BY id
                """,
                (status,)
            ).fetchall()

    return [dict(row) for row in rows]


def record_decision(
    review_item_id,
    decision,
    reviewer,
    reason=""
):
    """Record a human decision and update the review item."""

    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be approved or rejected.")

    if not reviewer or not reviewer.strip():
        raise ValueError("Reviewer is required.")

    now = utc_now()

    with get_connection() as conn:

        item = conn.execute(
            """
            SELECT status
            FROM review_items
            WHERE id = ?
            """,
            (review_item_id,)
        ).fetchone()

        if item is None:
            raise ValueError("Review item does not exist.")

        if item["status"] not in ("pending", "needs_re_review"):
            raise ValueError(
                f"Cannot decide an item with status {item['status']}."
            )

        conn.execute(
            """
            INSERT INTO review_decisions (
                review_item_id,
                decision,
                reviewer,
                reason,
                decided_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                review_item_id,
                decision,
                reviewer.strip(),
                reason,
                now
            )
        )

        conn.execute(
            """
            UPDATE review_items
            SET status = ?, decided_at = ?
            WHERE id = ?
            """,
            (decision, now, review_item_id)
        )


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")
