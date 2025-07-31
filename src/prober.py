import asyncio
import contextlib
import logging
import time
from collections.abc import Generator, Iterable, Sequence
from typing import Any, cast

import httpx
from src.server import Server
from src.xray.controller import XrayPoolManager

DONT_ALIVE_CONNECTION_TIME = 999.0

logger = logging.getLogger(__name__)


class ConnectionProber:
    def __init__(
        self,
        timeout: int = 3,
        max_concurrent: int = 50,
    ) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def probe(self, servers: Iterable[Server]) -> None:
        server_tasks = [
            self._get_connection_time(
                server.address,
                server.port,
            )
            for server in servers
        ]
        connection_times = await asyncio.gather(*server_tasks)

        for server, conn_time in zip(servers, connection_times):
            server.response_time.connection = cast(
                "float",
                conn_time or DONT_ALIVE_CONNECTION_TIME,
            )

    async def _get_connection_time(
        self,
        address: str,
        port: int,
    ) -> float | None:
        async with self._semaphore:
            start_time = time.time()
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        address,
                        port,
                    ),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                return round(time.time() - start_time, 3)


class HttpProber:
    RESPONSE_204_URLS = (
        "https://www.google.com/generate_204",
        "https://www.cloudflare.com/cdn-cgi/trace",
        "https://httpbin.org/status/204",
    )

    def __init__(
        self,
        timeout: int = 10,
        concurent_connections: int = 50,
    ):
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurent_connections)

    def setup_pool(
        self,
        api_url: str = "127.0.0.1:8080",
        start_port: int = 60000,
        pool_size: int = 50,
    ) -> None:
        self.pool_manager = XrayPoolManager(api_url, start_port, pool_size)

    async def probe(
        self,
        servers: Iterable["Server"],
        urls: Sequence[str],
    ) -> None:
        logger.debug(
            "Checking servers %s for URLs %s",
            [s.address for s in servers],
            urls,
        )
        await asyncio.gather(
            *(
                self._check_server(server, proxy_number, urls)
                for proxy_number, server in enumerate(servers)
            ),
        )

    def _chunk_servers_iter(
        self,
        servers: Iterable["Server"],
        chunk_size: int,
    ) -> Generator[list["Server"], Any, None]:
        logger.debug("Chunking servers into chunks of size %d.", chunk_size)
        chunk = []
        for server in servers:
            chunk.append(server)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    async def _get_url_response_time(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> float:
        start_time = time.time()
        try:
            response = await client.get(url, timeout=self.timeout)
            logger.debug(
                "URL: %s, Status: %s, Client ID: %s",
                url,
                response.status_code,
                id(client),
            )
            _ = response.text
            return time.time() - start_time
        except Exception as e:
            logger.error("Error fetching URL %s: %s", url, e)
            return 999.0

    async def _check_server(
        self,
        server: "Server",
        proxy_number: int,
        urls: Sequence[str],
    ) -> None:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{self.pool_manager.start_port + proxy_number}",
        ) as client:
            logger.debug(
                "Using proxy on port %d for server %s",
                self.pool_manager.start_port + proxy_number,
                server.address,
            )
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url) for url in urls],
            )
            server.response_time.http.update(dict(zip(urls, results)))

    async def _check_servers(
        self,
        servers: Iterable["Server"],
        urls: Sequence[str],
    ) -> None:
        logger.debug(
            "Checking servers %s for URLs %s",
            [s.address for s in servers],
            urls,
        )
        await asyncio.gather(
            *(
                self._check_server(server, proxy_number, urls)
                for proxy_number, server in enumerate(servers)
            ),
        )
