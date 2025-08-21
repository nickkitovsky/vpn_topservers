import asyncio
import base64
import binascii
import logging
from pathlib import Path

import httpx
from src.models import Subscription
from src.server import ServerParser

logger = logging.getLogger(__name__)


class SubscriptionManager:
    def __init__(self) -> None:
        self.subscriptions = set()
        self.supported_protocols = ServerParser.get_supported_protocols()
        logger.debug(
            "SubscriptionManager initialized with supported protocols: %s",
            self.supported_protocols,
        )

    def add_subscription(self, subscription_url: str) -> None:
        logger.debug("Adding subscription: %s", subscription_url)
        self.subscriptions.add(Subscription(url=subscription_url))

    def add_subscription_from_file(self, subscription_file: str | Path) -> None:
        logger.debug("Adding subscriptions from file: %s", subscription_file)
        if isinstance(subscription_file, str):
            subscription_file = Path(subscription_file)
        try:
            with subscription_file.open(mode="r", encoding="utf-8") as file:
                content = file.read()
            subscriptions = {
                line for line in content.splitlines() if line.startswith("https://")
            }
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
            logger.debug("Total subscriptions now: %d", len(self.subscriptions))

    async def fetch_subscriptions_content(
        self,
        timeout: int = 5,
        concurent_connections: int = 50,
    ) -> None:
        logger.info(
            "Fetching content for %d subscriptions with concurrency=%d",
            len(self.subscriptions),
            concurent_connections,
        )
        semaphore = asyncio.Semaphore(concurent_connections)
        async with httpx.AsyncClient() as client:
            tasks = [
                self._fetch_subscription_url(
                    subscription,
                    client,
                    semaphore,
                    timeout=timeout,
                )
                for subscription in self.subscriptions
            ]
            subscription_contents = await asyncio.gather(
                *tasks,
            )

            successful_fetches = 0
            for subscription, subscription_content in subscription_contents:
                if subscription_content:
                    subscription.servers = self._parse_subscription_content(
                        subscription_content,
                    )
                    if subscription.servers:
                        successful_fetches += 1
                        logger.debug(
                            "Parsed %d servers from subscription %s",
                            len(subscription.servers),
                            subscription.url,
                        )
        logger.info(
            "Finished fetching subscriptions. Successfully processed %d out of %d.",
            successful_fetches,
            len(self.subscriptions),
        )

    async def _fetch_subscription_url(
        self,
        subscription: Subscription,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        timeout: int = 5,
    ) -> tuple[Subscription, str]:
        async with semaphore:
            logger.debug("Fetching subscription from %s", subscription.url)
            try:
                response = await client.get(subscription.url, timeout=timeout)
                response.raise_for_status()
            except (httpx.RequestError, httpx.HTTPStatusError):
                logger.warning("Failed to fetch subscription from %s", subscription.url)
                return subscription, ""
            except Exception:
                logger.exception(
                    "An unexpected error occurred while fetching subscription from %s",
                    subscription.url,
                )
                return subscription, ""
            else:
                logger.debug(
                    "Successfully fetched content from %s",
                    subscription.url,
                )
                return subscription, response.text

    def _parse_subscription_content(self, raw_response: str) -> set[str]:
        logger.debug(
            "Parsing subscription content (first 50 chars): %s...",
            raw_response[:50],
        )
        try:
            response_text = base64.b64decode(raw_response).decode("utf-8")
            logger.debug("Content was base64 encoded.")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            logger.debug("Content is not base64 encoded, treating as plain text.")
            response_text = raw_response
        servers = self._filter_supported_protocols(response_text.splitlines())
        logger.debug("Parsed %d supported server URLs.", len(servers))
        return servers

    def _filter_supported_protocols(self, server_urls: list[str]) -> set[str]:
        logger.debug(
            "Filtering %d URLs against supported protocols: %s",
            len(server_urls),
            self.supported_protocols,
        )
        servers = {
            server
            for server in server_urls
            if server.split(":", 1)[0] in self.supported_protocols
        }
        unsupported_count = len(server_urls) - len(servers)
        if unsupported_count > 0:
            logger.debug(
                "Filtered out %d servers with unsupported protocols.",
                unsupported_count,
            )
        return servers
