import logging
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


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

    @classmethod
    def from_url(cls, url: str) -> "ServerEntity":
        parsed = urlparse(url)

        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {url}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            protocol = Protocols(parsed.scheme)
        except ValueError:
            msg = f"Unsupported protocol in link: {url}"
            logger.exception(msg)
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

        return cls(
            connection_details=conn_detail,
            params=params,
            parent_url=url,
        )
