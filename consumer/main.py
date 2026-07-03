"""Consumer entry point: resolve gap, stream events, flush completed ticks."""
from __future__ import annotations

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

import clickhouse_connect

from bucketizer import Bucketizer
from source import LiveEventSource
from storage import get_since, insert_rows


async def run(client) -> None:
    since = get_since(client)
    bucketizer = Bucketizer()

    async for event in LiveEventSource(since=since):
        rows = bucketizer.add(event)
        if rows:
            insert_rows(client, rows)


def main() -> None:
    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "default"),
    )
    asyncio.run(run(client))


if __name__ == "__main__":
    main()