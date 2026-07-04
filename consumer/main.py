"""Consumer entry point: resolve gap, stream events, flush completed ticks."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

import clickhouse_connect
from aiohttp import web

from bucketizer import Bucketizer
from source import LiveEventSource
from storage import get_since, insert_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

last_flush_time: float = time.time()


async def livez(request: web.Request) -> web.Response:
    """
    Liveness probe. Returns 500 if no flush has occurred in the last 5 minutes,
    which indicates the consumer loop has stalled without crashing.
    """
    if time.time() - last_flush_time > 300:
        return web.Response(status=500, text="stale")
    return web.Response(text="ok")


async def start_health_server() -> None:
    app = web.Application()
    app.router.add_get("/livez", livez)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8080).start()
    logger.info("Health server listening on :8080")


async def consume(client) -> None:
    global last_flush_time

    since = get_since(client)
    logger.info("Starting from %s", since)

    bucketizer = Bucketizer()

    async for event in LiveEventSource(since=since):
        rows = bucketizer.add(event)
        if rows:
            insert_rows(client, rows)
            last_flush_time = time.time()


async def run(client) -> None:
    await asyncio.gather(
        start_health_server(),
        consume(client),
    )


def main() -> None:
    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "default"),
    )
    try:
        asyncio.run(run(client))
    except Exception:
        logger.exception("Consumer crashed, exiting")
        sys.exit(1)


if __name__ == "__main__":
    main()