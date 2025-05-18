import base64
import logging
import time
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import parse_qs, urlparse

from grpc import Channel, insecure_channel
from xcapi.xray.app.proxyman.command.command_grpc_pb import HandlerServiceStub
from xcapi.xray.app.proxyman.command.command_pb import (
    AddInboundRequest,
    AddOutboundRequest,
)
from xcapi.xray.app.proxyman.config_pb import (
    MultiplexingConfig,
    ReceiverConfig,
    SenderConfig,
    SniffingConfig,
)
from xcapi.xray.app.router.command.command_grpc_pb import RoutingServiceStub
from xcapi.xray.app.router.command.command_pb import AddRuleRequest
from xcapi.xray.app.router.config_pb import Config, RoutingRule
from xcapi.xray.common.net.address_pb import IPOrDomain
from xcapi.xray.common.net.network_pb import Network
from xcapi.xray.common.net.port_pb import PortList, PortRange
from xcapi.xray.common.protocol.server_spec_pb import ServerEndpoint
from xcapi.xray.common.protocol.user_pb import User
from xcapi.xray.common.serial.typed_message_pb import GetMessageType, ToTypedMessage
from xcapi.xray.core.config_pb import InboundHandlerConfig, OutboundHandlerConfig
from xcapi.xray.proxy.socks.config_pb import AuthType, ServerConfig as SocksServerConfig
from xcapi.xray.proxy.vless.account_pb import Account as VlessAccount
from xcapi.xray.proxy.vless.outbound.config_pb import Config as VlessOutboundConfig
from xcapi.xray.transport.internet.config_pb import StreamConfig, TransportConfig
from xcapi.xray.transport.internet.grpc.config_pb import Config as GrpcConfig
from xcapi.xray.transport.internet.http.config_pb import Config as HttpConfig
from xcapi.xray.transport.internet.reality.config_pb import Config as RealityConfig
from xcapi.xray.transport.internet.tls.config_pb import Config as TlsConfig
from xcapi.xray.transport.internet.websocket.config_pb import Config as WebsocketConfig

logger = logging.getLogger(__name__)


@dataclass
class OutboundParams:
    protocol: str
    address: str
    port: int
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
    sid: str = ""  # будет заполнено позже
    flow: str = ""


def parse_url(link: str) -> OutboundParams:
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    protocol = parsed.scheme
    user_id = parsed.username or ""

    def get_param(key: str) -> str:
        return query.get(key, [""])[0]

    if not (parsed.hostname and parsed.port and user_id):
        msg = f"Error parsing link: {link}"
        logger.error(msg)
        raise ValueError(msg)

    # Парсим все базовые поля
    params = OutboundParams(
        protocol=protocol,
        address=parsed.hostname,
        port=parsed.port,
        user_id=user_id,
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
    sid_from_url = get_param("sid")
    if sid_from_url:
        params.sid = sid_from_url
    else:
        params.sid = ""
    if flow_from_url := query.get("flow"):
        params.flow = flow_from_url[0]
    return params


class XrayApi:
    def __init__(self, api_host: str = "127.0.0.1", api_port: int = 8080) -> None:
        channel: Channel = insecure_channel(f"{api_host}:{api_port}")
        self._handler_stub = HandlerServiceStub(channel)
        self._route_stub: RoutingServiceStub = RoutingServiceStub(channel)

    def add_outbound(self, params: OutboundParams, tag: str = "outbound") -> None:
        try:
            ip_address(params.address)
            address = IPOrDomain(ip=bytes(map(int, params.address.split("."))))
        except ValueError:
            address = IPOrDomain(domain=params.address)

        # Proxy settings по протоколу
        if params.protocol == "vless":
            proxy = VlessOutboundConfig(
                vnext=[
                    ServerEndpoint(
                        address=address,
                        port=params.port,
                        user=[
                            User(
                                level=0,
                                account=ToTypedMessage(
                                    VlessAccount(
                                        id=params.user_id,
                                        encryption="none",
                                        flow=params.flow,
                                    ),
                                ),
                            ),
                        ],
                    ),
                ],
            )
        else:
            msg = f"Unsupported protocol: {params.protocol}"
            raise ValueError(msg)

        outbound = OutboundHandlerConfig(
            tag=tag,
            proxy_settings=ToTypedMessage(proxy),
            sender_settings=ToTypedMessage(
                SenderConfig(
                    stream_settings=_create_stream_settings(params),
                    multiplex_settings=MultiplexingConfig(enabled=False),
                ),
            ),
        )
        self._handler_stub.AddOutbound(AddOutboundRequest(outbound=outbound))
        logger.info("Added outbound %s", tag)

    def add_inbound_socks(self, port: int, tag: str = "inbound") -> None:
        inbound = InboundHandlerConfig(
            tag=tag,
            receiver_settings=ToTypedMessage(
                ReceiverConfig(
                    port_list=PortList(range=[PortRange(From=port, To=port)]),
                    listen=IPOrDomain(ip=bytes([127, 0, 0, 1])),
                    sniffing_settings=SniffingConfig(
                        enabled=True,
                        destination_override=["http", "tls"],
                    ),
                ),
            ),
            proxy_settings=ToTypedMessage(
                SocksServerConfig(
                    auth_type=AuthType.NO_AUTH,  # type: ignore reportArgumentType
                    address=IPOrDomain(ip=bytes([0, 0, 0, 0])),
                    udp_enabled=True,
                ),
            ),
        )
        self._handler_stub.AddInbound(AddInboundRequest(inbound=inbound))
        logger.info("Added inbound %s", tag)

    def add_routing_rule(
        self,
        in_tag: str,
        out_tag: str,
        rule_tag: str | None = None,
    ) -> None:
        rt = rule_tag or f"{in_tag}_to_{out_tag}"
        cfg = Config(
            domain_strategy=Config.DomainStrategy.AsIs,  # type: ignore reportArgumentType
            rule=[
                RoutingRule(
                    networks=[Network.TCP, Network.UDP],  # type: ignore reportArgumentType
                    tag=out_tag,
                    inbound_tag=[in_tag],
                    rule_tag=rt,
                ),
            ],
        )
        self._route_stub.AddRule(
            AddRuleRequest(shouldAppend=True, config=ToTypedMessage(cfg)),
        )
        logger.info("Added rule %s", rt)


def _create_stream_settings(params: OutboundParams) -> StreamConfig:
    ts = []
    if params.type == "ws":
        ts.append(
            TransportConfig(
                protocol_name="websocket",
                settings=ToTypedMessage(WebsocketConfig(path=params.path)),
            ),
        )

    elif params.type == "grpc":
        service_name = (params.service_name or "grpc") + f"_{time.time()}"
        ts.append(
            TransportConfig(
                protocol_name="grpc",
                settings=ToTypedMessage(
                    GrpcConfig(
                        service_name=service_name,
                        multi_mode=True,
                        authority=params.host or params.sni or "",
                        idle_timeout=10,
                        health_check_timeout=20,
                    ),
                ),
            ),
        )
    elif params.type == "h2":
        ts.append(
            TransportConfig(
                protocol_name="http",
                settings=ToTypedMessage(
                    HttpConfig(host=[params.host] if params.host else []),
                ),
            ),
        )

    sec = params.security.lower()
    if sec == "tls":
        stype = GetMessageType(TlsConfig)
        sconf = [
            ToTypedMessage(TlsConfig(server_name=params.sni, allow_insecure=False)),
        ]
    elif sec == "reality":
        stype = GetMessageType(RealityConfig)
        sb = bytes.fromhex(params.sid)
        # длина ровно до 8 байт (16 hex) — так и будет при генерации выше
        sconf = [
            ToTypedMessage(
                RealityConfig(
                    server_name=params.sni,
                    public_key=_decode_base64url(params.pbk),
                    short_id=sb,
                    Fingerprint=params.fp,
                    show=False,
                ),
            ),
        ]
    else:
        stype = 0
        sconf = []

    return StreamConfig(
        protocol_name=params.type,
        transport_settings=ts,
        security_type=str(stype),
        security_settings=sconf,
    )


def _decode_base64url(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)
