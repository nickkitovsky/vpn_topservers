import asyncio
import contextlib
import logging
import time
from collections.abc import Generator, Iterable, Iterator
from itertools import islice
from typing import TYPE_CHECKING, Any, Callable, cast
from urllib.parse import parse_qs, urlparse

from src.models import Server, VlessParams

if TYPE_CHECKING:
    from src.models import Subscription
DONT_ALIVE_CONNECTION_TIME = 999.0
logger = logging.getLogger(__name__)


class ServerParser:
    def __init__(self) -> None:
        self.supported_protocols: dict[str, Callable[[str], VlessParams]] = {
            "vless": self.parse_vless_params,
        }

    @classmethod
    def get_supported_protocols(cls) -> set[str]:
        return set(cls().supported_protocols.keys())

    def parse_url(self, url: str, subscription_url: str = "") -> Server:
        logger.debug("Parsing server URL: %s", url)
        parsed = urlparse(url)
        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {url}"
            logger.error(msg)
            raise ValueError(msg)
        try:
            params = self.supported_protocols[parsed.scheme](parsed.query)
        except KeyError:
            msg = f"Unsupported protocol in link: {url}"
            logger.error(msg)  # noqa: TRY400
            raise ValueError(msg)  # noqa: B904
        else:
            connection_data = {
                "protocol": parsed.scheme,
                "address": str(parsed.hostname),
                "port": parsed.port,
                "username": parsed.username or "",
                "params": params,
            }
            server = Server(
                **connection_data,
                raw_url=url,
                from_subscription=subscription_url,
            )
            logger.debug("Successfully parsed server: %s", server)
            return server

    def parse_vless_params(self, raw_params: str) -> VlessParams:
        logger.debug("Parsing VLESS params from: %s", raw_params)
        query = parse_qs(raw_params)

        def get_param(key: str) -> str:
            return query.get(key, [""])[0]

        return VlessParams(
            sni=get_param("sni"),
            pbk=get_param("pbk"),
            security=get_param("security") or "none",
            type=get_param("type") or "tcp",
            fp=get_param("fp"),
            path=get_param("path") or "/",
            service_name=get_param("serviceName"),
            host=get_param("host"),
            alpn=query.get("alpn"),
            sid=get_param("sid"),
            flow=get_param("flow"),
        )


class ServerProber:
    def __init__(
        self,
        timeout: int = 1,
        max_concurrent: int = 50,
    ) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def probe(self, servers: Iterable[Server]) -> None:
        server_tasks = [
            self._get_connection_time(
                server.address,
                server.port,
            )
            for server in servers
        ]
        connection_times = await asyncio.gather(*server_tasks)

        for server, conn_time in zip(servers, connection_times):
            server.response_time.connection = cast(
                "float",
                conn_time or DONT_ALIVE_CONNECTION_TIME,
            )

    async def _get_connection_time(
        self,
        address: str,
        port: int,
        timeout: float = 1.0,
    ) -> float | None:
        async with self._semaphore:
            start_time = time.time()
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        address,
                        port,
                    ),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                return round(time.time() - start_time, 3)


class ServerManager:
    def __init__(self):
        self.servers = set()
        self.parser = ServerParser()
        logger.debug("ServerManager initialized.")

    def add_from_subscription(
        self,
        subscription: "Subscription",
        *,
        only_443_port: bool = False,
    ) -> None:
        logger.debug(
            "Adding servers from subscription: %s (only_443_port=%s)",
            subscription.url,
            only_443_port,
        )
        initial_server_count = len(self.servers)
        if only_443_port:
            servers = {
                server
                for server_url in subscription.servers
                if (server := self.parser.parse_url(server_url, subscription.url)).port
                == 443  # noqa: PLR2004
            }
        else:
            servers = {
                self.parser.parse_url(server_url, subscription.url)
                for server_url in subscription.servers
            }

        self.servers |= servers
        added_count = len(self.servers) - initial_server_count
        logger.info(
            "Added %d new servers from subscription %s. Total servers: %d",
            added_count,
            subscription.url,
            len(self.servers),
        )

    def add_from_subscriptions(self, subscriptions: Iterable["Subscription"]) -> None:
        for subscription in subscriptions:
            self.add_from_subscription(subscription)

    async def filter_alive_servers(
        self,
        timeout: int = 1,
        max_concurrent: int = 50,
    ) -> None:
        prober = ServerProber(timeout=timeout, max_concurrent=max_concurrent)
        logger.info("Filtering alive servers...")
        await prober.probe(self.servers)
        servers_count = len(self.servers)
        self.servers = {
            server
            for server in self.servers
            if server.response_time.connection < DONT_ALIVE_CONNECTION_TIME
        }
        logger.info(
            "Filtered %d servers out of %d.",
            servers_count - len(self.servers),
            servers_count,
        )

    def fastest_connention_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        logger.debug(
            "Getting %s fastest servers by connection time.",
            "all" if server_amount == 0 else server_amount,
        )
        sorted_servers = sorted(self.servers, key=lambda s: s.response_time.connection)
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def fastest_http_response_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        logger.debug(
            "Getting %s fastest servers by HTTP response time.",
            "all" if server_amount == 0 else server_amount,
        )
        sorted_servers = sorted(
            self.servers,
            key=lambda s: sum(s.response_time.http.values()),
        )
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def chunk_servers_iter(
        self,
        servers: Iterable[Server],
        chunk_size: int,
    ) -> Generator[list[Server], Any, None]:
        logger.debug("Chunking servers into chunks of size %d.", chunk_size)
        chunk = []
        for server in servers:
            chunk.append(server)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk
