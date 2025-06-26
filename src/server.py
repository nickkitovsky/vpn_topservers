import logging
from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass, field
from itertools import islice
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from src.subscription import Subscription

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VlessParams:
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
class ResponseTime:
    connection: float = 999.0
    http: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Server:
    protocol: str
    address: str
    port: int
    username: str
    params: VlessParams = field(repr=False)
    raw_url: str = field(repr=False)
    response_time: ResponseTime = field(default_factory=ResponseTime, init=False)
    parent_url: str = field(default="", repr=False)

    def __hash__(self) -> int:
        return hash(
            (
                self.address,
                self.port,
                self.username,
            ),
        )

    def __eq__(self, other: object) -> bool:
        return bool(
            isinstance(other, Server)
            and self.address == other.address
            and self.port == other.port
            and self.username == other.username,
        )


class ServerParser:
    def __init__(self) -> None:
        self.parser_map: dict[str, Callable[[str], VlessParams]] = {
            "vless": self.parse_vless_params,
        }

    def parse_url(self, url: str) -> Server:
        parsed = urlparse(url)
        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {url}"
            logger.error(msg)
            raise ValueError(msg)
        try:
            params = self.parser_map[parsed.scheme](parsed.query)
        except KeyError:
            msg = "Unsupported protocol in link: {url}"
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
            return Server(**connection_data, raw_url=url)

    def parse_vless_params(self, raw_params: str) -> VlessParams:
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
                if s.port == 443  # noqa: PLR2004
            }
        else:
            self.servers = {s for sub in subscriptions for s in sub.servers}

    def fastest_connention_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        sorted_servers = sorted(self.servers, key=lambda s: s.response_time.connection)
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def fastest_http_response_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
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
        chunk = []
        for server in servers:
            chunk.append(server)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk
