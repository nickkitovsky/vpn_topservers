import asyncio
import logging

import httpx
from prober import get_connection_time
from schemas import Server, Subscription

logger = logging.getLogger(__name__)
DONT_ALIVE_CONNECTION_TIME = 999


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
        self.timeout = timeout
        self.max_concurrent_connections = max_concurrent_connections
        self.only_443port = only_443port

    async def collect_subscription_data(self, *, only_alive: bool = True) -> None:
        async with httpx.AsyncClient() as client:
            subscription_tasks = [
                self._fetch_subscription_url(
                    url,
                    client,
                )
                for url in self.urls
            ]
            subscriptions = await asyncio.gather(*subscription_tasks)

            for subscription in filter(None, subscriptions):
                self.subscriptions.append(subscription)

                server_tasks = [
                    get_connection_time(
                        server.connection_details.address,
                        server.connection_details.port,
                        self.timeout,
                        self.max_concurrent_connections,
                    )
                    for server in subscription.servers
                ]
                connection_times = await asyncio.gather(*server_tasks)

                for server, conn_time in zip(subscription.servers, connection_times):
                    server.connection_time = conn_time or DONT_ALIVE_CONNECTION_TIME

                if only_alive:
                    subscription.servers = [
                        s
                        for s in subscription.servers
                        if s.connection_time < DONT_ALIVE_CONNECTION_TIME
                    ]

                logger.info(
                    "Processed %d servers from %s",
                    len(subscription.servers),
                    subscription.url,
                )

    def top_fastest_connention_time_servers(self, n: int = 100) -> list[Server]:
        all_servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(all_servers, key=lambda s: s.connection_time)[:n]

    async def _fetch_subscription_url(
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
