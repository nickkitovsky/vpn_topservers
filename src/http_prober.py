import asyncio
import contextlib
import logging
import time
import typing
from collections.abc import Generator, Iterable, Sequence
from typing import TYPE_CHECKING, Any

import httpx
from src.xray.api import XrayApi
from src.xray.controller import XrayProcessHandler

if typing.TYPE_CHECKING:
    from src.server import Server
logger = logging.getLogger(__name__)


API_URL = "127.0.0.1:8080"

DEFAULT_URLS = (
    "https://openai.com/policies/",
    "https://privacycenter.instagram.com/images/assets_DO_NOT_HARDCODE/company_brand_privacy_center_policy/Privacy-2022-CompanyBrand-56A-Mobile.png",
)


class HttpProbber:
    def __init__(
        self,
        max_concurent_requests: int = 50,
        max_concurent_servers: int = 25,
        timeout: int = 10,
        api_url: str = API_URL,
        start_inbound_port: int = 60000,
    ) -> None:
        self.timeout = timeout
        self.start_inbound_port = start_inbound_port
        self.max_concurent_requests = max_concurent_requests
        self.max_concurent_servers = max_concurent_servers
        self._api = XrayApi(api_url)
        self._controller = XrayProcessHandler()

    async def probe(
        self,
        servers: Iterable["Server"],
        urls: Sequence[str] | None = None,
    ) -> None:
        if not urls:
            urls = DEFAULT_URLS
        server_chunks = self._chunk_servers_iter(servers, self.max_concurent_servers)
        self._controller.run()
        logger.debug("Xray started.")
        self.setup_pool()
        logger.debug("Inbound servers pool created.")
        for chunk in server_chunks:
            with self.outbound_pool(chunk):
                await self._check_all_servers(chunk, urls)
        logger.info("Finished probing all servers.")
        logger.debug("Xray stopped.")
        self._controller.stop()

    @contextlib.contextmanager
    def outbound_pool(
        self,
        servers: Iterable["Server"],
    ) -> Generator[None, Any, None]:
        for num, server in enumerate(servers):
            logger.debug(
                "Adding outbound %s for server %s",
                f"outbound{num}",
                server.address,
            )
            # TODO: FIX ANY API ERROR
            try:
                self._api._add_outbound_vless(server, f"outbound{num}")
            except Exception:  # noqa: BLE001
                logger.error(  # noqa: TRY400
                    "Error adding outbound %s for server %s",
                    num,
                    server.address,
                )
        yield
        for num, _ in enumerate(servers):
            logger.debug("Removing outbound %s", f"outbound{num}")
            self._api.remove_outbound(f"outbound{num}")

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
        server: "Server",
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
                server.address,
            )
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url, semaphore) for url in urls],
            )
            server.response_time.http.update(dict(zip(urls, results)))

    async def _check_all_servers(
        self,
        servers: Iterable["Server"],
        urls: Sequence[str],
    ) -> None:
        semaphore = asyncio.Semaphore(self.max_concurent_requests)
        logger.debug(
            "Checking servers %s for URLs %s",
            [s.address for s in servers],
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
            self._api.add_inbound_socks(
                self.start_inbound_port + i,
                f"inbound{i}",
            )
            self._api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
