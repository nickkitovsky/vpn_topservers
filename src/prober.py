import asyncio
import logging
import time
from collections.abc import Coroutine, Generator, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from curl_cffi import AsyncSession, CurlOpt
from src.config import settings
from src.xray.handlers import XrayPoolHandler

if TYPE_CHECKING:
    from src.server import Server

logger = logging.getLogger(__name__)


class ConnectionProber:
    def __init__(
        self,
        timeout: int = settings.CONNECTION_PROBER_TIMEOUT,
        max_concurrent: int = settings.CONNECTION_PROBER_MAX_CONCURRENT_CONNECTIONS,
    ) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def probe(self, servers: Iterable["Server"]) -> None:
        tasks = [self._safe_connection_measure(server) for server in servers]
        await asyncio.gather(*tasks)

    async def _safe_connection_measure(self, server: "Server") -> None:
        try:
            conn_time = await self._get_connection_time(server.address, server.port)
        except (asyncio.TimeoutError, OSError) as e:
            server.response_time.connection = settings.DONT_ALIVE_CONNECTION_TIME
            logger.debug(
                "Server %s:%d connection FAILED: %s",
                server.address,
                server.port,
                e,
            )
        else:
            server.response_time.connection = conn_time
            logger.debug(
                "Server %s:%d connection OK: %.3fs",
                server.address,
                server.port,
                conn_time,
            )

    async def _get_connection_time(
        self,
        address: str,
        port: int,
    ) -> float:
        async with self._semaphore:
            start_time = time.perf_counter()
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(address, port),
                timeout=self.timeout,
            )
            writer.close()
            await writer.wait_closed()
            return round(time.perf_counter() - start_time, 3)


class HttpProber:
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
        self.session = self.setup_session()

    def setup_session(
        self,
        timeout: int = settings.PROXYPROBER_TIMEOUT,
        headers: dict[str, str] | None = None,
        *,
        connect_only: bool = False,
    ) -> AsyncSession:
        if headers is None:
            headers = {"Connection": "close"}
        curl_options = {
            CurlOpt.FORBID_REUSE: 1,  # Запрещает повторное использование соединения
            CurlOpt.FRESH_CONNECT: 1,  # Всегда создаёт новое TCP-соединение
            CurlOpt.CONNECT_ONLY: int(connect_only),  # 1=только соединение без запроса
            CurlOpt.TIMEOUT: timeout,  # Общий таймаут всего запроса (сек)
            #  CurlOpt.SERVER_RESPONSE_TIMEOUT: 5, # Время ожидания ответа от сервера(сек)
            #  CurlOpt.CONNECTTIMEOUT: 3, # Таймаут установки TCP-соединения (сек)
        }
        return AsyncSession(curl_options=curl_options, headers=headers)

    async def _close_session(self) -> None:
        await self.session.close()

    async def probe(self, servers: Iterable["Server"]) -> None:
        for servers_chunk in self._chunk_servers(servers, settings.XRAY_POOL_SIZE):
            # async with self._semaphore:
            with self.pool_manager.outbound_pool(servers_chunk):
                tasks = self._create_tasks(servers_chunk)
                await asyncio.gather(*tasks, return_exceptions=True)

            logger.debug("Chunk check completed")
        await self._close_session()
        self.pool_manager.process_manager.stop()

    def _create_tasks(
        self,
        servers: Iterable["Server"],
    ) -> list[Coroutine]:
        tasks = []
        for num, server in enumerate(servers):
            proxy_url = f"socks5://127.0.0.1:{settings.XRAY_START_INBOUND_PORT + num}"
            logger.debug(
                "Using proxy %s for server %s, [%s]",
                proxy_url,
                server.address,
                num,
            )
            tasks.extend(
                [self._fetch(server, proxy_url, url) for url in self.urls],
            )
        return tasks

    async def _fetch(
        self,
        server: "Server",
        proxy: str,
        url: str,
    ) -> None:
        try:
            resp = await self.session.get(
                url,
                proxy=proxy,
                timeout=settings.PROXYPROBER_TIMEOUT,
            )

            server.response_time.http[url] = resp.elapsed
            logger.debug(
                "%s → %s | %s | %s",
                proxy,
                url,
                resp.status_code,
                resp.elapsed,
            )
        except Exception as e:  # noqa: BLE001
            server.response_time.http[url] = settings.DONT_ALIVE_CONNECTION_TIME
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
