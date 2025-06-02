import asyncio
import contextlib
import logging
import time

from .schemas import Server

logger = logging.getLogger(__name__)


async def _get_connection_time(
    server: Server,
    timeout: float = 1.0,
    max_concurrent: int = 50,
) -> float | None:
    start_time = time.time()
    async with asyncio.Semaphore(max_concurrent):
        with contextlib.suppress(asyncio.TimeoutError, OSError):
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    server.connection_details.address,
                    server.connection_details.port,
                ),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            return round(time.time() - start_time, 3)


async def update_server_connection_time(
    server: Server,
    timeout: float = 1.0,
    max_concurrent: int = 50,
) -> None:
    connection_time = await _get_connection_time(server, timeout, max_concurrent)
    if connection_time:
        server.connection_time = connection_time
        logger.debug(
            "Connection time to %s: %s",
            server.connection_details.address,
            connection_time,
        )
    else:
        logger.warning(
            "Failed to get connection time for server %s",
            server.connection_details.address,
        )
