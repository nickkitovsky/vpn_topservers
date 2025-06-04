import asyncio
import contextlib
import logging
import time

import httpx
from schemas import Server, Sites

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


async def get_site_response_time(
    servers: list[Server],
    proxy_url: str,
    default_timeout_seconds: float = 5.0,
    max_concurrent_servers: int = 10,
):
    """Measures response time for predefined sites for each server and updates
    the server.repose_time attribute.

    Args:
        servers: A list of Server objects to test.
        get_proxy_url_for_server: A callable that takes a Server object
            and returns its corresponding local proxy URL (e.g., "socks5://127.0.0.1:1080")
            or None if not applicable.
        default_timeout_seconds: Timeout in seconds for each site request.
        max_concurrent_servers: Maximum number of servers to test concurrently.

    """
    target_sites_map = {
        "google": Sites.GOOGLE.value,
        "instagram": Sites.INSTAGRAM.value,
    }
    semaphore = asyncio.Semaphore(max_concurrent_servers)

    async def _test_and_update_server(server: Server):
        if not proxy_url:
            logger.warning(
                f"No proxy URL for server {server.connection_details.address}:{server.connection_details.port}. Skipping site tests.",
            )
            # server.repose_time will keep its default values (999.0)
            return

        logger.info(
            f"Testing site response times for {server.connection_details.address}:{server.connection_details.port} via {proxy_url}",
        )

        google_task = _get_response_time(
            proxy_url,
            target_sites_map["google"],
        )
        instagram_task = _get_response_time(
            proxy_url,
            target_sites_map["instagram"],
        )

        g_time, i_time = await asyncio.gather(google_task, instagram_task)
        server.repose_time.google = g_time
        server.repose_time.instagram = i_time

        logger.info(
            f"Updated {server.connection_details.address}:{server.connection_details.port} - "
            f"Google: {server.repose_time.google:.3f}s, Instagram: {server.repose_time.instagram:.3f}s",
        )

    tasks = []
    for server_item in servers:

        async def task_wrapper(s):
            async with semaphore:
                await _test_and_update_server(s)

        tasks.append(task_wrapper(server_item))

    await asyncio.gather(*tasks)


async def _get_response_time(proxy: str, url: str, timeout: int = 1) -> float:
    # TODO: test response time without semaphore
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
        start = time.time()
        try:
            response = await client.get(url)
            response.raise_for_status()
            return time.time() - start
        except Exception as e:  # noqa: BLE001
            logger.warning("%s -> %s | Error: %s", proxy, url, e)
            return 999.0
