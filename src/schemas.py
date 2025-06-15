import logging
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class Protocols(Enum):
    VLESS = "vless"


class Sites(StrEnum):
    GOOGLE = "https://www.google.com"
    INSTAGRAM = "https://www.instagram.com"


@dataclass
class SitesResponseTime:
    instagram: float = 999.0
    google: float = 999.0


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
        )
        # TODO: move it to constructor
        sid_from_url = get_param("sid")
        if sid_from_url:
            params.sid = sid_from_url
        else:
            params.sid = ""
        if flow_from_url := query.get("flow"):
            params.flow = flow_from_url[0]

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


@dataclass
class Subscription:
    url: str
    servers: set[Server] = field(default_factory=set)

    @classmethod
    def from_url_content(
        cls,
        url: str,
        subscription_content: str,
        *,
        only_443port: bool = False,
    ) -> "Subscription":
        servers = set()
        for link in subscription_content.splitlines():
            try:
                server = Server.from_url(link.strip())
                if (
                    only_443port and server.connection_details.port != 443
                ) or server in servers:
                    continue
                servers.add(server)
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping invalid link: %s. Reason: %s", link, e)
        return cls(
            url,
            servers=servers,
        )
