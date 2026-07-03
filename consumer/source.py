"""Event model and async iterators for the Wikimedia recentchange stream."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import aiohttp

logger = logging.getLogger(__name__)

RELEVANT_TYPES = {"edit", "new"}
RECONNECT_DELAY = 5  # seconds


@dataclass(frozen=True)
class RecentChangeEvent:
    event_type: str
    dt: datetime        # meta.dt — event time, not ingestion time
    wiki: str
    server_name: str
    namespace: int
    title: str
    user: str
    bot: bool
    length_old: Optional[int]
    length_new: Optional[int]

    @property
    def byte_diff_abs(self) -> int:
        if self.length_old is None or self.length_new is None:
            return 0
        return abs(self.length_new - self.length_old)

    @staticmethod
    def from_raw(raw: dict) -> Optional["RecentChangeEvent"]:
        """Returns None for event types that carry no edit payload (log, categorize, external)."""
        if raw.get("type") not in RELEVANT_TYPES:
            return None

        dt_raw = raw.get("meta", {}).get("dt")
        if not dt_raw:
            return None

        length = raw.get("length") or {}
        return RecentChangeEvent(
            event_type=raw["type"],
            dt=datetime.fromisoformat(dt_raw.replace("Z", "+00:00")),
            wiki=raw.get("wiki", "unknown"),
            server_name=raw.get("server_name", ""),
            namespace=int(raw.get("namespace", 0)),
            title=raw.get("title", ""),
            user=raw.get("user", ""),
            bot=bool(raw.get("bot", False)),
            length_old=length.get("old"),
            length_new=length.get("new"),
        )


class LiveEventSource:
    """
    Consumes the Wikimedia EventStreams recentchange endpoint as newline-delimited JSON.

    Reconnects automatically on network errors, resuming from the last successfully
    received event time. The caller sees a single uninterrupted async iterator.
    """

    URL = "https://stream.wikimedia.org/v2/stream/recentchange"
    HEADERS = {
        "User-Agent": "wiki-edit-monitor/0.1 (https://github.com/user/wiki-edit-monitor)",
        "Accept": "application/json",
    }

    def __init__(self, since: Optional[datetime] = None):
        self._since = since

    async def __aiter__(self) -> AsyncIterator[RecentChangeEvent]:
        while True:
            try:
                async for event in self._stream():
                    self._since = event.dt
                    yield event
            except Exception as exc:
                logger.warning("Stream error: %s — reconnecting in %ds", exc, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)

    async def _stream(self) -> AsyncIterator[RecentChangeEvent]:
        params = {}
        if self._since is not None:
            params["since"] = self._since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            async with session.get(self.URL, params=params, timeout=None) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event = RecentChangeEvent.from_raw(raw)
                    if event is not None:
                        yield event


class FixtureEventSource:
    """
    Replays events from a JSONL file — one raw JSON object per line.

    Intended for local development and tests without a live network connection.
    Capture a fixture with:
        curl -s -H 'Accept: application/json' \\
            https://stream.wikimedia.org/v2/stream/recentchange > fixture.jsonl
    """

    def __init__(self, path: str):
        self.path = path

    async def __aiter__(self) -> AsyncIterator[RecentChangeEvent]:
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = RecentChangeEvent.from_raw(json.loads(line))
                if event is not None:
                    yield event