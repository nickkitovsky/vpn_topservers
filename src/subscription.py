import asyncio
import base64
import binascii
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from src.server import Server, ServerParser

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    url: str
    servers: set[Server] = field(default_factory=set, init=False)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        return bool(
            isinstance(other, Subscription) and self.url == other.url,
        )


class SubscriptionManager:
    def __init__(self) -> None:
        self.subscriptions = set()
        self.server_parser = ServerParser()

    def add_subscription_from_file(self, subscription_file: str | Path) -> None:
        if isinstance(subscription_file, str):
            subscription_file = Path(subscription_file)
        try:
            with subscription_file.open(mode="r", encoding="utf-8") as file:
                content = file.read()
            subscriptions = [
                line for line in content.splitlines() if line.startswith("https://")
            ]
        except FileNotFoundError:
            logger.exception("Subscription file not found: %s", subscription_file)
            raise
        else:
            logger.info(
                "Loaded %s subscriptions, from %s",
                len(subscriptions),
                str(subscription_file),
            )
            self.subscriptions |= {Subscription(url=url) for url in subscriptions}

    async def fetch_subscription_servers(
        self,
        timeout: int = 5,
        concurent_connections: int = 50,
    ) -> None:
        async with (
            asyncio.Semaphore(concurent_connections),
            httpx.AsyncClient() as client,
        ):
            subscription_contents = await asyncio.gather(
                *[
                    self._fetch_subscription_url(
                        subscription,
                        client,
                        timeout=timeout,
                    )
                    for subscription in self.subscriptions
                ],
            )
            for subscription, subscription_content in subscription_contents:
                subscription.servers = self._parse_server_urls(subscription_content)

    async def _fetch_subscription_url(
        self,
        subscription: Subscription,
        client: httpx.AsyncClient,
        timeout: int = 5,
    ) -> tuple[Subscription, list[str]]:
        logger.debug("Fetching subscription from %s", subscription.url)
        try:
            response = await client.get(subscription.url, timeout=timeout)
            response.raise_for_status()  # Raise an exception for bad status codes
        except (httpx.RequestError, httpx.HTTPStatusError):
            logger.warning("Failed to fetch subscription from %s", subscription.url)
            return subscription, []
        except Exception:
            logger.exception(
                "An unexpected error occurred while fetching subscription from %s",
                subscription.url,
            )
            return subscription, []
        else:
            try:
                response_text = base64.b64decode(response.text).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                response_text = response.text
            logger.debug(
                "Seccessfully fetched %d servers from %s",
                len(subscription.servers),
                subscription.url,
            )
            return subscription, response_text.splitlines()

    def _parse_server_urls(self, subscription_content: list[str]) -> set[Server]:
        subscription_urls = (
            sub for sub in subscription_content if sub.startswith("https://")
        )
        return {self.server_parser.parse_url(url) for url in subscription_urls}
