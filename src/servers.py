import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


class Protocols(Enum):
    VLESS = "vless"


@dataclass(frozen=True)
class ConnectionDetails:
    protocol: Protocols
    address: str
    port: int
    raw_link: str


@dataclass
class OutboundParams:
    user_id: str
    sni: str = ""
    pbk: str = ""
    security: str = "none"
    type: str = "tcp"
    fp: str = ""
    path: str = "/"
    service_name: str = ""
    host: str = ""
    alpn: list[str] | None = None
    sid: str = ""
    flow: str = ""


@dataclass
class ServerEntity:
    connection_details: ConnectionDetails
    params: OutboundParams
    parent_url: str = ""
    connection_time: float = 999.0
    download_speed: float = -1.0


class Subscription:
    def __init__(
        self,
        url: str,
        connection_timeout: int = 1,
        max_concurrent_connections: int = 50,
        *,
        only_443port: bool = False,
    ) -> None:
        self.url = url
        self.servers: list[ServerEntity] = []
        self.connection_timeout = connection_timeout
        self.max_concurrent_connections = max_concurrent_connections
        self.only_443port = only_443port
        self._sem_concurrent_connections = asyncio.Semaphore(max_concurrent_connections)

    def parse_link(self, link: str) -> ServerEntity:
        parsed = urlparse(link)

        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {link}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            protocol = Protocols(parsed.scheme)
        except ValueError:
            msg = f"Unsupported protocol in link: {link}"
            logger.exception(msg)
            raise

        conn_detail = ConnectionDetails(
            protocol=protocol,
            address=str(parsed.hostname),
            port=parsed.port,
            raw_link=link,
        )

        query = parse_qs(parsed.query)

        def get_param(key: str) -> str:
            return query.get(key, [""])[0]

        params = OutboundParams(
            user_id=parsed.username or "",
            sni=get_param("sni"),
            pbk=get_param("pbk"),
            security=get_param("security") or "none",
            type=get_param("type") or "tcp",
            fp=get_param("fp"),
            path=get_param("path") or "/",
            service_name=get_param("serviceName"),
            host=get_param("host"),
            alpn=query.get("alpn"),
        )
        return ServerEntity(
            connection_details=conn_detail,
            params=params,
        )

    async def parse_subscription(
        self,
        subscription_response: str,
    ) -> list[ServerEntity]:
        tasks = []

        for link in subscription_response.splitlines():
            try:
                server = self.parse_link(link.strip())
                if self.only_443port and server.connection_details.port != 443:  # noqa: PLR2004
                    continue
                tasks.append(self._get_connection_time(server))
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping invalid link: %s. Reason: %s", link, e)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, ServerEntity)]

    async def fetch_subscription_content(self) -> str:
        async with httpx.AsyncClient() as client:
            logger.info("Fetching proxies from %s", self.url)
            try:
                resp = await client.get(self.url, timeout=self.connection_timeout)
                resp.raise_for_status()
            except (httpx.RequestError, ValueError) as e:
                msg = f"Failed fetch from {self.url}: {e}"
                logger.exception(msg)
                raise
            return resp.text

    async def _get_connection_time(self, server_entity: ServerEntity) -> ServerEntity:
        start_time = time.time()
        async with self._sem_concurrent_connections:
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        server_entity.connection_details.address,
                        server_entity.connection_details.port,
                    ),
                    timeout=self.connection_timeout,
                )
                writer.close()
                await writer.wait_closed()
                server_entity.connection_time = round(time.time() - start_time, 3)
        return server_entity

    async def process_servers(self) -> None:
        logger.info("Processing subscription from %s", self.url)
        try:
            subscription_content = await self.fetch_subscription_content()
            self.servers = await self.parse_subscription(subscription_content)
            logger.info(
                "Successfully processed %d servers from %s",
                len(self.servers),
                self.url,
            )
        except Exception:
            logger.exception("Failed to process subscription %s.", self.url)
            self.servers = []
