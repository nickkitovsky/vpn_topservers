import asyncio
import time
from dataclasses import dataclass, field

import httpx

from src.parser import parse
from src.server import ServerEntity


@dataclass
class Subscription:
    url: str
    servers: list[ServerEntity] = field(default_factory=list)


class SubscriptionGroup:
    def __init__(
        self,
        subscriptions: list[Subscription],
        connection_timeout: int = 1,
        max_subscription_requests: int = 5,
        max_concurrent_connections: int = 30,
        *,
        only_443port: bool = False,
    ):
        self.subscriptions = subscriptions
        self.connection_timeout = connection_timeout
        self.only_443port = only_443port
        self._max_subscription_requests_semaphore = asyncio.Semaphore(
            max_subscription_requests,
        )
        self._max_concurrent_connections_semaphore = asyncio.Semaphore(
            max_concurrent_connections,
        )

    async def _fetch_servers(self, subscription: Subscription) -> None:
        async with (
            self._max_subscription_requests_semaphore,
            httpx.AsyncClient() as client,
        ):
            try:
                response = await client.get(
                    subscription.url,
                    timeout=self.connection_timeout,
                )
                response.raise_for_status()
                if self.only_443port:
                    subscription.servers = [
                        srv
                        for uri in response.text.splitlines()
                        if (
                            srv := parse(uri, parent_url=subscription.url)
                        ).connection_details.port
                        == 443  # noqa: PLR2004
                    ]
                else:
                    subscription.servers = [
                        parse(uri, parent_url=subscription.url)
                        for uri in response.text.splitlines()
                    ]
            except (httpx.RequestError, ValueError) as e:
                e.add_note(f"Failed fetch from {subscription.url}")
                raise

    async def _attempt_connection(self, server_entity: ServerEntity) -> None:
        async with self._max_concurrent_connections_semaphore:
            start_time = time.time()
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        server_entity.connection_details.address,
                        server_entity.connection_details.port,
                    ),
                    timeout=self.connection_timeout,
                )
                writer.close()
                await writer.wait_closed()
                server_entity.connection_time = round(
                    time.time() - start_time,
                    3,
                )
            except (TimeoutError, OSError):
                server_entity.connection_time = 999

    async def _check_servers(self) -> None:
        all_servers = [
            server
            for subscription in self.subscriptions
            for server in subscription.servers
        ]
        tasks = [
            self._attempt_connection(server_entity) for server_entity in all_servers
        ]
        await asyncio.gather(*tasks)

    async def _process_all_sources(self) -> None:
        await asyncio.gather(
            *(self._fetch_servers(subscription) for subscription in self.subscriptions),
        )

        all_tasks = [
            self._check_servers() for subscription in self.subscriptions
        ]  # Проверяем подключения
        await asyncio.gather(*all_tasks)

    def fetch_alive_servers(self, *, ordered: bool = True) -> list[ServerEntity]:
        asyncio.run(self._process_all_sources())

        alive_servers = [
            server
            for subscription in self.subscriptions
            for server in subscription.servers
            if server.connection_time <= 1
        ]
        if ordered:
            return sorted(alive_servers, key=lambda x: x.connection_time)
        return alive_servers
