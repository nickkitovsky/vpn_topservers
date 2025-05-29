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

    async def fetch_url(self, client: httpx.AsyncClient, url: str):
        async with self._semaphore:
            start = time.time()
            try:
                response = await client.get(url)
                response.raise_for_status()
                response_time = time.time() - start
                logger.info(
                    f"  -> {url} | Status: {response.status_code} | Time: {response_time:.2f}s",
                )
                return url, response_time
            except Exception as e:
                logger.exception(f"{url} | Error: {e}")
                return url, None


async def fetch_all_with_proxy(proxy: str) -> dict[str, float | None]:
    print(f"\n[Запуск клиента через {proxy}]")
    results = {}
    async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
        tasks = [fetch_url(client, url) for url in urls]
        completed = await asyncio.gather(*tasks)
        results = {url: duration for url, duration in completed}
    return results


async def main():
    tasks = {
        proxy: asyncio.create_task(fetch_all_with_proxy(proxy)) for proxy in proxies
    }
    results = await asyncio.gather(*tasks.values())

    # Вывод результатов
    for proxy, result in zip(tasks.keys(), results):
        print(f"\nРезультаты для {proxy}:")
        for url, time_taken in result.items():
            if time_taken is not None:
                print(f"  {url} -> {time_taken:.2f}s")
            else:
                print(f"  {url} -> ошибка")


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
