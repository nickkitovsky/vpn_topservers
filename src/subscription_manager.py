import asyncio
import contextlib
import logging
import time

import httpx

from .schemas import Server, Subscription

logger = logging.getLogger(__name__)


class SubscriptionManager:
    def __init__(
        self,
        urls: list[str],
        max_concurrent_connections: int = 50,
        connection_timeout: int = 1,
        *,
        only_443port: bool = False,
    ):
        self.urls = urls
        self.connection_timeout = connection_timeout
        self.only_443port = only_443port
        self.subscriptions: list[Subscription] = []
        self._semaphore = asyncio.Semaphore(max_concurrent_connections)

    async def fetch_subscription_content(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> str:
        logger.info("Fetching proxies from %s", url)
        try:
            resp = await client.get(url, timeout=self.connection_timeout)
            resp.raise_for_status()
        except (httpx.RequestError, ValueError):
            logger.exception("Failed fetch from %s", url)
            raise
        return resp.text

    async def _get_connection_time(
        self,
        server_entity: Server,
    ) -> Server:
        start_time = time.time()
        async with self._semaphore:
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

    async def add_subscription(self, client: httpx.AsyncClient, url: str) -> None:
        logger.info("Processing subscription from %s", url)
        try:
            subscription_content = await self.fetch_subscription_content(client, url)
            subscription = Subscription.from_url_content(
                url,
                subscription_content,
                only_443port=self.only_443port,
            )
            self.subscriptions.append(subscription)
            await asyncio.gather(
                *(self._get_connection_time(s) for s in subscription.servers),
            )
            logger.info(
                "Successfully processed %d servers from %s",
                len(subscription.servers),
                url,
            )
        except Exception:
            logger.exception("Failed to process subscription %s.", url)

    async def run(self) -> None:
        async with httpx.AsyncClient() as client:
            for url in self.urls:
                await self.add_subscription(client, url)

    def top_fastest_connention_time_servers(self, n: int = 100) -> list[Server]:
        servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(servers, key=lambda x: x.connection_time)[:n]
