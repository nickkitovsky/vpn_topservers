import asyncio
import contextlib
import logging
import time

import httpx

from .server import ServerEntity

logger = logging.getLogger(__name__)


class Subscription:
    def __init__(
        self,
        url: str,
        client: httpx.AsyncClient,
        connection_timeout: int = 1,
        max_concurrent_connections: int = 50,
        *,
        only_443port: bool = False,
    ) -> None:
        self.url = url
        self.client = client
        self.connection_timeout = connection_timeout
        self.max_concurrent_connections = max_concurrent_connections
        self.only_443port = only_443port
        self.servers: list[ServerEntity] = []

    async def parse_subscription(
        self,
        subscription_response: str,
        semaphore: asyncio.Semaphore,
    ) -> list[ServerEntity]:
        tasks = []

        for link in subscription_response.splitlines():
            try:
                server = ServerEntity.from_url(link.strip())
                if self.only_443port and server.connection_details.port != 443:  # noqa: PLR2004
                    continue
                tasks.append(self._get_connection_time(server, semaphore))
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping invalid link: %s. Reason: %s", link, e)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, ServerEntity)]

    async def fetch_subscription_content(self) -> str:
        logger.info("Fetching proxies from %s", self.url)
        try:
            resp = await self.client.get(self.url, timeout=self.connection_timeout)
            resp.raise_for_status()
        except (httpx.RequestError, ValueError) as e:
            msg = f"Failed fetch from {self.url}: {e}"
            logger.exception(msg)
            raise
        return resp.text

    async def _get_connection_time(
        self,
        server_entity: ServerEntity,
        semaphore: asyncio.Semaphore,
    ) -> ServerEntity:
        start_time = time.time()
        async with semaphore:
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        server_entity.connection_details.address,
                        server_entity.connection_details.port,
                    ),
                    timeout=self.connection_timeout,
                )
                writer.close()
                await writer.wait_closed()
                server_entity.connection_time = round(time.time() - start_time, 3)
        return server_entity

    async def process_servers(self, semaphore: asyncio.Semaphore) -> None:
        logger.info("Processing subscription from %s", self.url)
        try:
            subscription_content = await self.fetch_subscription_content()
            self.servers = await self.parse_subscription(
                subscription_content,
                semaphore,
            )
            logger.info(
                "Successfully processed %d servers from %s",
                len(self.servers),
                self.url,
            )
        except Exception:
            logger.exception("Failed to process subscription %s.", self.url)
            self.servers = []


class SubscriptionManager:
    def __init__(
        self,
        urls: list[str],
        max_concurrent_connections: int = 50,
    ):
        self.urls = urls
        self.max_concurrent_connections = max_concurrent_connections
        self._semaphore = asyncio.Semaphore(self.max_concurrent_connections)
        self.subscriptions: list[Subscription] = []

    async def run(self) -> None:
        async with httpx.AsyncClient() as client:
            self.subscriptions = [Subscription(url, client) for url in self.urls]
            await asyncio.gather(
                *(s.process_servers(self._semaphore) for s in self.subscriptions),
            )

    def top_fastest_connention_time_servers(self, n: int = 100) -> list[ServerEntity]:
        servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(servers, key=lambda x: x.connection_time)[:n]
