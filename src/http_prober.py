import asyncio
import contextlib
import logging
import time
from collections.abc import Generator
from typing import Any

import httpx
from schemas import Server
from xray import XrayApi

logger = logging.getLogger(__name__)

MAX_CONCURENT_REQUESTS = 50
MAX_CONCURENT_SERVERS = 5
TIMEOUT = 10
START_INBOUND_PORT = 60000
API_URL = "127.0.0.1:8080"


class HttpProbber:
    def __init__(
        self,
        max_concurent_requests: int = MAX_CONCURENT_REQUESTS,
        max_concurent_servers: int = MAX_CONCURENT_SERVERS,
        timeout: int = TIMEOUT,
        api_url: str = API_URL,
    ) -> None:
        self.timeout = timeout
        self.max_concurent_requests = max_concurent_requests
        self.max_concurent_servers = max_concurent_servers
        self._xray_api = XrayApi(api_url)
        self._setup_pool()

    async def run(self, servers: list[Server], urls: list[str]) -> None:
        for chunk in self._chunk_servers(servers):
            with self.outbound_pool(chunk):
                await self._check_all_servers(chunk, urls)

    @contextlib.contextmanager
    def outbound_pool(
        self,
        servers: list[Server],
    ) -> Generator[None, Any, None]:
        for num, server in enumerate(servers):
            self._xray_api.add_outbound_vless(server, f"outbound{num}")
        yield
        for num, _ in enumerate(servers):
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
                response.raise_for_status()
                # _ = response.text  # читаем тело, чтобы запрос был завершён корректно
                return time.time() - start_time
            except Exception:  # noqa: BLE001
                return 999.0

    async def _check_server(
        self,
        server: Server,
        proxy_number: int,
        urls: list[str],
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{START_INBOUND_PORT + proxy_number}",
        ) as client:
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url, semaphore) for url in urls],
            )
            server.response_time.update(dict(zip(urls, results)))
            # tasks = {
            #     url: asyncio.create_task(
            #         self._get_url_response_time(client, url, semaphore),
            #     )
            #     for url in urls
            # }
            # for url, task in tasks.items():
            #     server.response_time[url] = await task

    async def _check_all_servers(
        self,
        servers: list[Server],
        urls: list[str],
    ) -> None:
        semaphore = asyncio.Semaphore(self.max_concurent_requests)
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

    def _setup_pool(self) -> None:
        for i in range(self.max_concurent_servers):
            self._xray_api.add_inbound_socks(START_INBOUND_PORT + i, f"inbound{i}")
            self._xray_api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
