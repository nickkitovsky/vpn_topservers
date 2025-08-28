import json
import logging
from dataclasses import dataclass
from urllib.parse import ParseResult

from src.common_utils import decode_base64
from src.server.schema import Server, ServerParams

logger = logging.getLogger(__name__)


def parse_url(parsed: ParseResult, subscription_url: str = "") -> Server:
    raw_params = json.loads(decode_base64(parsed.netloc))
    params = _parse_vmess_params(raw_params)

    connection_data = {
        "protocol": parsed.scheme,
        "address": raw_params["add"],
        "port": raw_params["port"],
        "username": raw_params["id"] or "",
        "params": params,
    }
    return Server(
        **connection_data,
        raw_url=parsed.geturl(),
        from_subscription=subscription_url,
    )


@dataclass(frozen=True, slots=True)
class VmessParams(ServerParams):
    add: str
    host: str
    id: str
    net: str
    port: int
    ps: str
    aid: int = 0
    path: str = "/"
    tls: str = "tls"
    type: str = "auto"
    security: str = "auto"
    sni: str = ""
    #  rename 'skip-cert-verify'
    skip_cert_verify: bool = True


def _parse_vmess_params(raw_params: dict) -> VmessParams:
    logger.debug("Parsing VMESS params from: %s", raw_params)
    if skip_cert_verify := raw_params.get("skip-cert-verify"):
        raw_params["skip_cert_verify"] = skip_cert_verify
        del raw_params["skip-cert-verify"]
    return VmessParams(
        add=raw_params.get("add", ""),
        host=raw_params.get("host", ""),
        id=raw_params.get("id", ""),
        net=raw_params.get("net", ""),
        port=raw_params.get("port", 0),
        ps=raw_params.get("ps", ""),
        aid=raw_params.get("aid", 0),
        path=raw_params.get("path", "/"),
        tls=raw_params.get("tls", "tls"),
        type=raw_params.get("type", "auto"),
        security=raw_params.get("security", "auto"),
        sni=raw_params.get("sni", ""),
        skip_cert_verify=raw_params.get("skip_cert_verify", True),
    )
