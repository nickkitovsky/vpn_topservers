import asyncio
import contextlib
import logging
import time

import httpx
from schemas import Server, Subscription

logger = logging.getLogger(__name__)
DONT_ALIVE_CONNECTION_TIME = 999


class SubscriptionManager:
    def __init__(
        self,
        urls: list[str],
        timeout: int = 3,
        max_concurrent_connections: int = 100,
        *,
        only_443port: bool = False,
    ):
        self.urls = urls
        self.subscriptions: list[Subscription] = []
        self.timeout = timeout
        self.max_concurrent_connections = max_concurrent_connections
        self.only_443port = only_443port
        self._semaphore = asyncio.Semaphore(self.max_concurrent_connections)

    async def fetch_subscription_data(self, *, only_alive: bool = True) -> None:
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
                    self.get_connection_time(
                        server.connection_details.address,
                        server.connection_details.port,
                    )
                    for server in subscription.servers
                ]
                connection_times = await asyncio.gather(*server_tasks)

                for server, conn_time in zip(subscription.servers, connection_times):
                    server.connection_time = conn_time or DONT_ALIVE_CONNECTION_TIME

                if only_alive:
                    subscription.servers = {
                        s
                        for s in subscription.servers
                        if s.connection_time < DONT_ALIVE_CONNECTION_TIME
                    }

                logger.info(
                    "Processed %d servers from %s",
                    len(subscription.servers),
                    subscription.url,
                )

    def top_fastest_connention_time_servers(self, proxy_count: int = 0) -> list[Server]:
        all_servers = [s for sub in self.subscriptions for s in sub.servers]
        if proxy_count == 0:
            return sorted(all_servers, key=lambda s: s.connection_time)
        return sorted(all_servers, key=lambda s: s.connection_time)[:proxy_count]

    def top_fastest_http_response_time_servers(
        self,
        proxy_count: int = 0,
    ) -> list[Server]:
        all_servers = [s for sub in self.subscriptions for s in sub.servers]
        if proxy_count == 0:
            return sorted(all_servers, key=lambda s: sum(s.response_time.values()))
        return sorted(all_servers, key=lambda s: sum(s.response_time.values()))[
            :proxy_count
        ]

    async def get_connection_time(
        self,
        address: str,
        port: int,
    ) -> float | None:
        async with self._semaphore:
            start_time = time.time()
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        address,
                        port,
                    ),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                return round(time.time() - start_time, 3)

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
            logger.error("Failed to fetch subscription from %s", url)  # noqa: TRY400
            return None

        return Subscription.from_url_content(
            url,
            response.text,
            only_443port=self.only_443port,
        )
