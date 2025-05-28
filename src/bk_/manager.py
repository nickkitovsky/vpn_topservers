import asyncio

import httpx
from server import ServerEntity
from subscription import Subscription


class SubscriptionManager:
    def __init__(self, urls: list[str], max_concurrent_connections: int = 100) -> None:
        self.urls = urls
        self.max_concurrent_connections: int = max_concurrent_connections
        self.subscriptions: list[Subscription] = []

    async def run(self) -> None:
        semaphore = asyncio.Semaphore(self.max_concurrent_connections)
        async with httpx.AsyncClient() as client:
            self.subscriptions = [Subscription(url, client) for url in self.urls]
            await asyncio.gather(*(s.process(semaphore) for s in self.subscriptions))

    def top_fastest_servers(self, n: int = 100) -> list[ServerEntity]:
        servers = [s for sub in self.subscriptions for s in sub.servers]
        return sorted(servers, key=lambda x: x.connection_time)[:n]
