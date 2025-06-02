import asyncio
import logging

import httpx

from .prober import update_server_connection_time
from .schemas import Server, Subscription

logger = logging.getLogger(__name__)


class SubscriptionFetcher:
    def __init__(self, timeout: int = 1, *, only_443port: bool = False):
        self.only_443port = only_443port
        self.timeout = timeout

    async def fetch(
        self,
        url: str,
        client: httpx.AsyncClient,
    ) -> Subscription | None:
        logger.info("Fetching subscription from %s", url)
        try:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            logger.exception("Failed to fetch subscription from %s", url)
            return None

        return Subscription.from_url_content(
            url,
            response.text,
            only_443port=self.only_443port,
        )


class SubscriptionManager:
    def __init__(
        self,
        urls: list[str],
        timeout: int = 1,
        max_concurrent_connections: int = 50,
        *,
        only_443port: bool = False,
    ):
        self.urls = urls
        self.subscriptions: list[Subscription] = []
        self.max_concurrent_connections = max_concurrent_connections
        self.timeout = timeout
        self._fetcher = SubscriptionFetcher(
            only_443port=only_443port,
            timeout=self.timeout,
        )

    async def collect_subscription_data(self) -> None:
        async with httpx.AsyncClient() as client:
            for url in self.urls:
                subscription = await self._fetcher.fetch(url, client)
                if not subscription:
                    continue
                self.subscriptions.append(subscription)
                tasks = [
                    update_server_connection_time(
                        server,
                        self.timeout,
                        self.max_concurrent_connections,
                    )
                    for server in subscription.servers
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                logger.info(
                    "Processed %d servers from %s",
                    len(subscription.servers),
                    url,
                )

    def top_fastest_connention_time_servers(self, n: int = 100) -> list[Server]:
        all_servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(all_servers, key=lambda s: s.connection_time)[:n]
