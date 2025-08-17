import asyncio
import logging
import time
from collections.abc import Coroutine, Generator, Iterable, Sequence
from typing import TYPE_CHECKING, Any

import httpx
from curl_cffi.requests import AsyncSession
from src.config import settings
from src.xray.handlers import XrayPoolHandler

if TYPE_CHECKING:
    from src.server import Server

logger = logging.getLogger(__name__)


class LegacyHttpxProber:
    def __init__(
        self,
        timeout: int = settings.PROXYPROBER_TIMEOUT,
        concurent_connections: int = settings.HTTP_PROBER_MAX_CONCURRENT_REQUESTS,
        urls: Sequence[str] = settings.HTTP_204_URLS,
    ):
        self.timeout = timeout
        self.urls = urls
        self._semaphore = asyncio.Semaphore(concurent_connections)

        self.pool_manager = XrayPoolHandler(
            api_url=settings.XRAY_API_URL,
            start_port=settings.XRAY_START_INBOUND_PORT,
            pool_size=settings.XRAY_POOL_SIZE,
        )

    async def probe(
        self,
        servers: Iterable["Server"],
    ) -> None:
        for servers_chunk in self._chunk_servers(servers, settings.XRAY_POOL_SIZE):
            with self.pool_manager.outbound_pool(servers_chunk):
                await asyncio.gather(
                    *(
                        self._check_server(server, proxy_number)
                        for proxy_number, server in enumerate(servers_chunk)
                    ),
                    return_exceptions=True,
                )

    def _chunk_servers(
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
        async with self._semaphore:
            start_time = time.perf_counter()
            try:
                response = await client.get(url, timeout=self.timeout)
                logger.debug("STATUS CODE %s", response.status_code)
                if response.status_code < 400:
                    return round(time.perf_counter() - start_time, 3)
                logger.warning(
                    "Bad status code %d for %s",
                    response.status_code,
                    url,
                )
                return 555.0
            except Exception as e:
                logger.warning("Error fetching %s: %s", url, e)
                return 666.0

    async def _check_server(
        self,
        server: "Server",
        proxy_number: int,
    ) -> None:
        async with httpx.AsyncClient(
            proxy=f"http://xray:xray@127.0.0.1:{settings.XRAY_START_INBOUND_PORT + proxy_number}",  # noqa: E501
        ) as client:
            results = await asyncio.gather(
                *[self._get_url_response_time(client, url) for url in self.urls],
                return_exceptions=True,
            )

            response_times = {}
            for url, result in zip(self.urls, results):
                if isinstance(result, Exception):
                    logger.warning(
                        "Exception while probing %s via server %s: %s",
                        url,
                        server.address,
                        result,
                    )
                    response_times[url] = 999.0
                else:
                    response_times[url] = result

            server.response_time.http.update(response_times)


class CurlCffiProber:
    def __init__(
        self,
        timeout: int = settings.PROXYPROBER_TIMEOUT,
        concurent_connections: int = settings.HTTP_PROBER_MAX_CONCURRENT_REQUESTS,
        urls: Sequence[str] = settings.HTTP_204_URLS,
    ) -> None:
        self.timeout = timeout
        self.urls = urls
        self._semaphore = asyncio.Semaphore(concurent_connections)
        self.pool_manager = XrayPoolHandler(
            api_url=settings.XRAY_API_URL,
            start_port=settings.XRAY_START_INBOUND_PORT,
            pool_size=settings.XRAY_POOL_SIZE,
        )

    async def probe(self, servers: Iterable["Server"]) -> None:
        for servers_chunk in self._chunk_servers(servers, settings.XRAY_POOL_SIZE):
            async with (
                self._semaphore,
                AsyncSession() as session,
            ):
                with self.pool_manager.outbound_pool(servers_chunk):
                    tasks = self._create_tasks(session, servers_chunk)
                    await asyncio.gather(*tasks, return_exceptions=True)

                logger.debug("Chunk check completed")

    def _create_tasks(
        self,
        session: AsyncSession,
        servers: Iterable["Server"],
    ) -> list[Coroutine]:
        tasks = []
        for num, server in enumerate(servers):
            # proxy_url = f"socks5://127.0.0.1:{settings.XRAY_START_INBOUND_PORT + num}"
            proxy_url = (
                f"http://xray:xray@127.0.0.1:{settings.XRAY_START_INBOUND_PORT + num}"
            )
            logger.debug(
                "Using proxy %s for server %s, [%s]",
                proxy_url,
                server.address,
                num,
            )
            tasks.extend(
                [self._fetch(session, server, proxy_url, url) for url in self.urls],
            )
        return tasks

    async def _fetch(
        self,
        session: AsyncSession,
        server: "Server",
        proxy: str,
        url: str,
    ) -> None:
        try:
            start_time = time.time()
            resp = await session.get(
                url,
                proxy=proxy,
                timeout=settings.PROXYPROBER_TIMEOUT,
            )
            elapsed_ms = time.time() - start_time
            server.response_time.http[url] = elapsed_ms
            logger.debug(
                "%s → %s | %s | %s",
                proxy,
                url,
                resp.status_code,
                elapsed_ms,
            )
        except Exception as e:  # noqa: BLE001
            server.response_time.http[url] = 998.0
            logger.debug("%s → %s | error: %s", proxy, url, e)

    def _chunk_servers(
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


class HttpxProber:
    def __init__(
        self,
        timeout: int = settings.PROXYPROBER_TIMEOUT,
        concurent_connections: int = settings.HTTP_PROBER_MAX_CONCURRENT_REQUESTS,
        urls: Sequence[str] = settings.HTTP_204_URLS,
    ) -> None:
        self.timeout = timeout
        self.urls = urls
        self._semaphore = asyncio.Semaphore(concurent_connections)
        self.pool_manager = XrayPoolHandler(
            api_url=settings.XRAY_API_URL,
            start_port=settings.XRAY_START_INBOUND_PORT,
            pool_size=settings.XRAY_POOL_SIZE,
        )
        self.clients = self.generate_clients()

    def generate_clients(self) -> list[httpx.AsyncClient]:
        logger.debug("Generating %d clients.", settings.XRAY_POOL_SIZE)
        return [
            httpx.AsyncClient(
                proxy=f"http://127.0.0.1:{settings.XRAY_START_INBOUND_PORT + n}",
            )
            for n in range(settings.XRAY_POOL_SIZE)
        ]

    async def remove_clients(self, clients: list[httpx.AsyncClient]) -> None:
        await asyncio.gather(*[client.aclose() for client in clients])

    async def probe(self, servers: Iterable["Server"]) -> None:
        logger.debug("Starting http probe for servers.")
        for servers_chunk in self._chunk_servers(servers, settings.XRAY_POOL_SIZE):
            with self.pool_manager.outbound_pool(servers_chunk):
                tasks = []
                for num, server in enumerate(servers_chunk):
                    tasks.extend([self._fetch(server, num, url) for url in self.urls])
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.debug("Chunk check completed")

    async def _fetch(
        self,
        server: "Server",
        num: int,
        url: str,
    ) -> None:
        start_time = time.time()
        try:
            resp = await self.clients[num].get(
                url,
                timeout=settings.PROXYPROBER_TIMEOUT,
            )
            print("OKOKOK")
            elapsed_ms = time.time() - start_time
            server.response_time.http[url] = elapsed_ms
            logger.debug(
                "[%s] → %s | %s | %s",
                num,
                url,
                resp.status_code,
                elapsed_ms,
            )
        except Exception as e:  # noqa: BLE001
            server.response_time.http[url] = 888.0
            logger.debug("[%s] → %s | error: %s", num, url, e)

    def _chunk_servers(
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


class Prober:
    def __init__(self) -> None:
        self.conn_prober = ConnectionProber(
            timeout=settings.SUBSCRIPTION_TIMEOUT,
            max_concurrent=settings.SUBSCRIPTION_MAX_CONCURRENT_CONNECTIONS,
        )
        self.http_prober = CurlCffiProber(
            timeout=settings.PROXYPROBER_TIMEOUT,
            concurent_connections=settings.HTTP_PROBER_MAX_CONCURRENT_REQUESTS,
        )

    async def probe_connection(self, servers: Iterable["Server"]) -> None:
        logger.info("Starting connection for servers.")
        await self.conn_prober.probe(servers)
        logger.info("Connection probe complete.")

    async def probe_http_requests(
        self,
        servers: Iterable["Server"],
    ) -> None:
        logger.info("Starting http probe for servers.")
        await self.http_prober.probe(servers)
        logger.info("Connection http probe complete.")
