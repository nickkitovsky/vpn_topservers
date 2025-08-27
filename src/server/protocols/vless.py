import logging
from dataclasses import dataclass
from urllib.parse import ParseResult, parse_qs

from src.server.exceptions import UrlParseError
from src.server.schema import Server, ServerParams

logger = logging.getLogger(__name__)


def parse_url(parsed: ParseResult, subscription_url: str = "") -> Server:
    if not (parsed.scheme and parsed.hostname and parsed.port):
        raise UrlParseError
    params = _parse_vless_params(parsed.query)

    connection_data = {
        "protocol": parsed.scheme,
        "address": str(parsed.hostname),
        "port": parsed.port,
        "username": parsed.username or "",
        "params": params,
    }
    return Server(
        **connection_data,
        raw_url=parsed.geturl(),
        from_subscription=subscription_url,
    )


@dataclass(frozen=True, slots=True)
class VlessParams(ServerParams):
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


def _parse_vless_params(raw_params: str) -> VlessParams:
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
