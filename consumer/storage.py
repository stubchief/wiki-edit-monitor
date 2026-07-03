"""ClickHouse interaction: row insertion and startup checkpoint resolution."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

MAX_BACKFILL = timedelta(days=31)

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

COLUMNS = [
    "tick_start",
    "wiki",
    "server_name",
    "namespace",
    "title",
    "edit_count",
    "distinct_users",
    "new_user_count",
    "bot_edit_count",
    "byte_diff_abs_sum",
]


def insert_rows(client, rows: list[dict]) -> None:
    """Inserts a batch of aggregated tick rows. A single INSERT call — atomic."""
    if not rows:
        return
    client.insert("agg_edits", [[row[col] for col in COLUMNS] for row in rows], column_names=COLUMNS)


def get_since(client) -> datetime:
    """
    Returns the timestamp to pass as since= when connecting to the stream.

    On first run the table is empty — ClickHouse returns the Unix epoch instead
    of NULL for max() on an empty table. In that case we backfill as far back
    as BACKFILL_DAYS env var allows (default 31, max 31 — Wikimedia API limit).
    On restart we resume from the last recorded tick.
    """
    backfill_days = min(int(os.environ.get("BACKFILL_DAYS", "31")), 31)

    result = client.query("SELECT max(tick_start) FROM agg_edits")
    value = result.result_rows[0][0]

    if value is None or value.replace(tzinfo=timezone.utc) == EPOCH:
        return datetime.now(timezone.utc) - timedelta(days=backfill_days)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value