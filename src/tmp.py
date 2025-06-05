import asyncio
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class Server:
    name: str
    ip: str
    response_times: dict[str, float] = field(default_factory=dict)


async def _fetch_response_time(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
) -> float:
    async with semaphore:
        start_time = time.time()
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            # _ = response.text  # читаем тело, чтобы запрос был завершён корректно
            return time.time() - start_time
        except Exception:  # noqa: BLE001
            return 999.0


async def check_urls_response_time(
    server: Server,
    proxy_number: int,
    urls: list[str],
    semaphore: asyncio.Semaphore,
) -> None:
    async with httpx.AsyncClient(
        proxy=f"socks5://127.0.0.1:{50000 + proxy_number}",
    ) as client:
        tasks = {
            url: asyncio.create_task(_fetch_response_time(client, url, semaphore))
            for url in urls
        }
        for url, task in tasks.items():
            server.response_times[url] = await task


async def check_all_servers(
    servers: list[Server],
    urls: list[str],
    max_concurrent_requests: int = 10,
) -> None:
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    await asyncio.gather(
        *(
            check_urls_response_time(server, proxy_number, urls, semaphore)
            for proxy_number, server in enumerate(servers)
        ),
    )


# Пример использования
if __name__ == "__main__":
    servers = [
        Server(name="Server 1", ip="192.168.1.1"),
        Server(name="Server 2", ip="192.168.1.2"),
    ]
    urls = ["https://example.com", "https://httpbin.org/get"]

    asyncio.run(check_all_servers(servers, urls, max_concurrent_requests=5))

    # Печать результатов
    for server in servers:
        print(f"{server.name} ({server.ip}):")
        for url, rt in server.response_times.items():
            print(f"  {url}: {rt:.2f} seconds" if rt >= 0 else f"  {url}: ERROR")
