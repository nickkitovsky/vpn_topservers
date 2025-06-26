import asyncio
import contextlib
import logging
import time
from collections.abc import Generator, Iterable, Sequence
from typing import Any

import httpx
from src.server import Server
from xray.api import XrayApi

logger = logging.getLogger(__name__)


API_URL = "127.0.0.1:8080"
DONT_ALIVE_CONNECTION_TIME = 999.0
DEFAULT_URLS = (
    "http://cp.cloudflare.com/",
    "https://www.google.com/gen_204",
)


class ConnectionProber:
    def __init__(
        self,
        timeout: int = 1,
        max_concurrent: int = 50,
    ) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def probe(self, servers: Iterable[Server]) -> None:
        server_tasks = [
            self._get_connection_time(
                server.connection_details.address,
                server.connection_details.port,
            )
            for server in servers
        ]
        connection_times = await asyncio.gather(*server_tasks)

        for server, conn_time in zip(servers, connection_times):
            server.connection_time = conn_time or DONT_ALIVE_CONNECTION_TIME

    async def _get_connection_time(
        self,
        address: str,
        port: int,
        timeout: float = 1.0,
    ) -> float | None:
        async with self._semaphore:
            start_time = time.time()
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


class HttpProbber:
    def __init__(
        self,
        max_concurent_requests: int = 100,
        max_concurent_servers: int = 25,
        timeout: int = 5,
        api_url: str = API_URL,
        start_inbound_port: int = 60000,
    ) -> None:
        self.timeout = timeout
        self.start_inbound_port = start_inbound_port
        self.max_concurent_requests = max_concurent_requests
        self.max_concurent_servers = max_concurent_servers
        self._xray_api = XrayApi(api_url)
        self.setup_pool()

    async def probe(
        self,
        servers: list[Server],
        urls: Sequence[str] | None = None,
    ) -> None:
        if not urls:
            urls = DEFAULT_URLS
        with self.outbound_pool(servers):
            await self._check_all_servers(servers, urls)
        logger.info("Finished probing all servers.")

    @contextlib.contextmanager
    def outbound_pool(
        self,
        servers: list[Server],
    ) -> Generator[None, Any, None]:
        for num, server in enumerate(servers):
            logger.debug(
                "Adding outbound %s for server %s",
                f"outbound{num}",
                server.connection_details.address,
            )
            # TODO: FIX ANY API ERROR
            try:
                self._xray_api.add_outbound_vless(server, f"outbound{num}")
            except Exception:  # noqa: BLE001
                logger.error(  # noqa: TRY400
                    "Error adding outbound %s for server %s",
                    f"outbound{num}",
                    server.connection_details,
                )
        yield
        for num, _ in enumerate(servers):
            logger.debug("Removing outbound %s", f"outbound{num}")
            self._xray_api.remove_outbound(f"outbound{num}")

    async def _get_url_response_time(
        self,
        client: httpx.AsyncClient,
        url: str,
        semaphore: asyncio.Semaphore,
    ) -> float:
        async with semaphore:
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
        server: Server,
        proxy_number: int,
        urls: Sequence[str],
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{self.start_inbound_port + proxy_number}",
        ) as client:
            logger.debug(
                "Using proxy on port %d for server %s",
                self.start_inbound_port + proxy_number,
                server.connection_details.address,
            )
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url, semaphore) for url in urls],
            )
            server.response_time.update(dict(zip(urls, results)))

    async def _check_all_servers(
        self,
        servers: Iterable[Server],
        urls: Sequence[str],
    ) -> None:
        semaphore = asyncio.Semaphore(self.max_concurent_requests)
        logger.debug(
            "Checking servers %s for URLs %s",
            [s.connection_details.address for s in servers],
            urls,
        )
        await asyncio.gather(
            *(
                self._check_server(server, proxy_number, urls, semaphore)
                for proxy_number, server in enumerate(servers)
            ),
        )

    def setup_pool(self) -> None:
        for i in range(self.max_concurent_servers):
            self._xray_api.add_inbound_socks(
                self.start_inbound_port + i,
                f"inbound{i}",
            )
            self._xray_api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
