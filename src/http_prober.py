import asyncio
import contextlib
import logging
import time
from collections.abc import Generator
from typing import Any

import httpx
from logger_config import setup_logging
from schemas import Server
from xray import XrayApi

logger = logging.getLogger(__name__)
setup_logging(debug=True)
API_URL = "127.0.0.1:8080"


class HttpProbber:
    def __init__(  # noqa: PLR0913
        self,
        max_concurent_requests: int = 200,
        max_concurent_servers: int = 50,
        timeout: int = 5,
        start_inbound_port: int = 60000,
        api_url: str = API_URL,
        probe_urls: list[str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_concurent_requests = max_concurent_requests
        self.max_concurent_servers = max_concurent_servers
        if not probe_urls:
            self.probe_urls = [
                "https://instagram.com",
                "https://chatgpt.com",
                "http://cp.cloudflare.com/",
                "https://www.google.com/gen_204",
            ]
        self._start_inbound_port = start_inbound_port
        self._xray_api = XrayApi(api_url)
        self.setup_pool()

    async def run(self, servers: list[Server]) -> None:
        for chunk in self._chunk_servers(servers):
            logger.debug(
                "Processing chunk of %d servers: %s",
                len(chunk),
                [s.connection_details.address for s in chunk],
            )
            with self.outbound_pool(chunk):
                await self._check_all_servers(chunk, self.probe_urls)
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
            # TODO FIX ANY API ERROR
            try:
                self._xray_api.add_outbound_vless(server, f"outbound{num}")
            except Exception:  # noqa: BLE001
                logger.error(
                    "Error adding outbound %s for server %s: %s",
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
            except Exception as e:  # noqa: BLE001
                logger.error("Error fetching URL %s: %s", url, e)  # noqa: TRY400
                return 999.0

    async def _check_server(
        self,
        server: Server,
        proxy_number: int,
        urls: list[str],
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{self._start_inbound_port + proxy_number}",
        ) as client:
            logger.debug(
                "Using proxy on port %d for server %s",
                self._start_inbound_port + proxy_number,
                server.connection_details.address,
            )
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url, semaphore) for url in urls],
            )
            server.response_time.update(dict(zip(urls, results)))

    async def _check_all_servers(
        self,
        servers: list[Server],
        urls: list[str],
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

    def _chunk_servers(
        self,
        servers: list[Server],
    ) -> Generator[list[Server], Any, None]:
        chunked_servers = [
            servers[i : i + self.max_concurent_servers]
            for i in range(0, len(servers), self.max_concurent_servers)
        ]
        yield from chunked_servers

    def setup_pool(self) -> None:
        for i in range(self.max_concurent_servers):
            self._xray_api.add_inbound_socks(
                self._start_inbound_port + i,
                f"inbound{i}",
            )
            self._xray_api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
