import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from src.server import Server

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    url: str
    servers: set[Server] = field(default_factory=set)

    @classmethod
    def from_url_content(
        cls,
        url: str,
        subscription_content: str,
    ) -> "Subscription":
        servers = set()
        for link in subscription_content.splitlines():
            try:
                server = Server.from_url(link.strip())
                if () or server in servers:
                    continue
                servers.add(server)
            except Exception:  # noqa: BLE001
                logger.warning("Skipping invalid link: %s.", link)
        return cls(
            url,
            servers=servers,
        )


class SubscriptionFetcher:
    def __init__(self, timeout: int = 5, concurent_connections: int = 50) -> None:
        self.timeout = timeout
        self.concurent_connections = concurent_connections

    async def fetch_subscriptions(self, urls: list[str]) -> list[Subscription]:
        async with (
            asyncio.Semaphore(self.concurent_connections),
            httpx.AsyncClient() as client,
        ):
            subscriptions = await asyncio.gather(
                *[
                    self._fetch_subscription_url(
                        url,
                        client,
                    )
                    for url in urls
                ],
            )
            return [s for s in subscriptions if s is not None]

    async def _fetch_subscription_url(
        self,
        url: str,
        client: httpx.AsyncClient,
    ) -> Subscription | None:
        logger.debug("Fetching subscription from %s", url)
        try:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            logger.warning("Failed to fetch subscription from %s", url)
            return None
        else:
            subscription = Subscription.from_url_content(
                url,
                response.text,
            )

            logger.debug(
                "Seccessfully fetched %d servers from %s",
                len(subscription.servers),
                subscription.url,
            )

        return subscription


class SubscriptionManager:
    def __init__(
        self,
    ) -> None:
        pass

    def read_subscriptions_file(self, subscription_file: str | Path) -> list[str]:
        if isinstance(subscription_file, str):
            subscription_file = Path(subscription_file)
        try:
            with subscription_file.open(mode="r", encoding="utf-8") as file:
                content = file.read()
            subscriptions = [line for line in content.splitlines() if line.startswith("https://")]
        except FileNotFoundError:
            logger.exception("Subscription file not found: %s", subscription_file)
            raise
        else:
            logger.info(
                "Loaded %s subscriptions, from %s",
                len(subscriptions),
                str(subscription_file),
            )
            return subscriptions
