"""Groups incoming events into fixed-width time buckets keyed by event time (meta.dt)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from source import RecentChangeEvent

TICK_INTERVAL = timedelta(minutes=2)


def floor_to_tick(dt: datetime, interval: timedelta = TICK_INTERVAL) -> datetime:
    """Returns the start of the tick that contains dt."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    return epoch + (delta // interval) * interval


@dataclass
class _Counters:
    edit_count: int = 0
    bot_edit_count: int = 0
    byte_diff_abs_sum: int = 0
    users: set = field(default_factory=set)
    server_name: str = ""

    def add(self, event: RecentChangeEvent) -> None:
        self.edit_count += 1
        if event.bot:
            self.bot_edit_count += 1
        self.byte_diff_abs_sum += event.byte_diff_abs
        self.users.add(event.user)
        self.server_name = event.server_name


class Bucketizer:
    """
    Accumulates per-(wiki, namespace, title) counters for the current tick in memory.

    When an event with a later tick boundary arrives, the completed tick is
    returned as a list of rows ready for insertion. The caller is responsible
    for writing those rows to ClickHouse.

    Bucketing is done on event time (meta.dt), not wall-clock ingestion time,
    so that backfill replays produce the same aggregates as a live stream would.
    """

    def __init__(self, interval: timedelta = TICK_INTERVAL):
        self.interval = interval
        self.tick_start: Optional[datetime] = None
        self.buffer: dict[tuple[str, int, str], _Counters] = defaultdict(_Counters)

    def add(self, event: RecentChangeEvent) -> Optional[list[dict]]:
        """
        Adds an event to the current tick.

        Returns a flushed row list when the event belongs to a new tick,
        otherwise returns None.
        """
        tick = floor_to_tick(event.dt, self.interval)

        rows = None
        if self.tick_start is not None and tick != self.tick_start:
            rows = self._drain()

        self.tick_start = tick
        self.buffer[(event.wiki, event.namespace, event.title)].add(event)
        return rows

    def force_flush(self) -> Optional[list[dict]]:
        """Flushes the current tick unconditionally. Used in live mode on a timer."""
        if not self.buffer:
            return None
        return self._drain()

    def _drain(self) -> list[dict]:
        rows = [
            {
                "tick_start": self.tick_start,
                "wiki": wiki,
                "server_name": c.server_name,
                "namespace": namespace,
                "title": title,
                "edit_count": c.edit_count,
                "distinct_users": len(c.users),
                "new_user_count": 0,
                "bot_edit_count": c.bot_edit_count,
                "byte_diff_abs_sum": c.byte_diff_abs_sum,
            }
            for (wiki, namespace, title), c in self.buffer.items()
        ]
        self.buffer.clear()
        return rows