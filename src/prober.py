import asyncio
import contextlib
import logging
import time

logger = logging.getLogger(__name__)


async def get_connection_time(
    address: str,
    port: int,
    timeout: float = 1.0,
    max_concurrent: int = 50,
) -> float | None:
    start_time = time.time()
    async with asyncio.Semaphore(max_concurrent):
        with contextlib.suppress(asyncio.TimeoutError, OSError):
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    address,
                    port,
                ),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            return round(time.time() - start_time, 3)
