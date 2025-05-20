import logging
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class ProxyProtocols(Enum):
    VLESS = "vless"


@dataclass(frozen=True)
class ConnectionDetails:
    protocol: ProxyProtocols
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
    alpn: list | None = None
    sid: str = ""
    flow: str = ""


@dataclass
class ServerEntity:
    connection_details: ConnectionDetails
    params: OutboundParams
    parent_url: str = ""
    connection_time: float = 999
    download_speed: float = 0


class Protocols(Enum):
    VLESS = "vless"


def parse_link(link: str) -> ServerEntity:
    parsed = urlparse(link)

    if not (parsed.hostname and parsed.port):
        msg = f"Error parsing link: {link}"
        logger.error(msg)
        raise ValueError(msg)
    conn_detail = ConnectionDetails(
        protocol=ProxyProtocols(parsed.scheme),
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
