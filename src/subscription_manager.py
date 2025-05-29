import asyncio
import contextlib
import logging
import time

import httpx

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


class ServerProber:
    def __init__(self, timeout: float = 1.0, max_concurrent: int = 50) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def check_connection_time(self, server: Server) -> None:
        start_time = time.time()
        async with self._semaphore:
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        server.connection_details.address,
                        server.connection_details.port,
                    ),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                server.connection_time = round(time.time() - start_time, 3)


class SubscriptionManager:
    def __init__(
        self,
        urls: list[str],
        *,
        only_443port: bool = False,
        connection_timeout: int = 1,
        max_concurrent_connections: int = 50,
    ):
        self.urls = urls
        self.subscriptions: list[Subscription] = []

        self._fetcher = SubscriptionFetcher(
            only_443port=only_443port,
            timeout=connection_timeout,
        )
        self._prober = ServerProber(
            timeout=connection_timeout,
            max_concurrent=max_concurrent_connections,
        )

    async def collect_subscription_data(self) -> None:
        async with httpx.AsyncClient() as client:
            for url in self.urls:
                subscription = await self._fetcher.fetch(url, client)
                if not subscription:
                    continue
                self.subscriptions.append(subscription)

                await asyncio.gather(
                    *(
                        self._prober.check_connection_time(server)
                        for server in subscription.servers
                    ),
                    return_exceptions=True,
                )

                logger.info(
                    "Processed %d servers from %s",
                    len(subscription.servers),
                    url,
                )

    def top_fastest_connention_time_servers(self, n: int = 100) -> list[Server]:
        all_servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(all_servers, key=lambda s: s.connection_time)[:n]
