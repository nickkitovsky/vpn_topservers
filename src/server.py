import logging
from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from itertools import islice
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from src.subscription import Subscription

logger = logging.getLogger(__name__)


class Protocols(Enum):
    VLESS = "vless"


@dataclass
class ConnectionDetails:
    protocol: Protocols
    address: str
    port: int
    raw_link: str = field(repr=False)


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
class Server:
    connection_details: ConnectionDetails
    params: OutboundParams = field(repr=False)
    response_time: dict = field(default_factory=dict)
    parent_url: str = field(default="", repr=False)
    connection_time: float = 999.0

    @classmethod
    def from_url(cls, url: str) -> "Server":
        parsed = urlparse(url)

        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {url}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            protocol = Protocols(parsed.scheme)
        except ValueError:
            msg = f"Unsupported protocol in link: {url}"
            logger.error(msg)  # noqa: TRY400
            raise

        conn_detail = ConnectionDetails(
            protocol=protocol,
            address=str(parsed.hostname),
            port=parsed.port,
            raw_link=url,
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
            sid=get_param("sid"),
            flow=get_param("flow"),
        )

        return cls(
            connection_details=conn_detail,
            params=params,
            response_time={},
            parent_url=url,
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.connection_details.address,
                self.connection_details.port,
                self.params.user_id,
            ),
        )

    def __eq__(self, other: object) -> bool:
        return bool(
            isinstance(other, Server)
            and self.connection_details.address == other.connection_details.address
            and self.connection_details.port == other.connection_details.port
            and self.params.user_id == other.params.user_id,
        )


class ServerManager:
    def __init__(self):
        self.servers = set()

    def parse_subscriptions(
        self,
        subscriptions: list["Subscription"],
        *,
        only_433_port: bool = False,
    ) -> None:
        if only_433_port:
            self.servers = {
                s
                for sub in subscriptions
                for s in sub.servers
                if s.connection_details.port == 443  # noqa: PLR2004
            }
        else:
            self.servers = {s for sub in subscriptions for s in sub.servers}

    def fastest_connention_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        sorted_servers = sorted(self.servers, key=lambda s: s.connection_time)
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def fastest_http_response_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        sorted_servers = sorted(
            self.servers,
            key=lambda s: sum(s.response_time.values()),
        )
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def chunk_servers_iter(
        self,
        servers: Iterable[Server],
        chunk_size: int,
    ) -> Generator[list[Server], Any, None]:
        chunk = []
        for server in servers:
            chunk.append(server)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk
