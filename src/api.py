import base64
import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from grpc import Channel, insecure_channel
from xcapi.xray.app.proxyman.command.command_grpc_pb import HandlerServiceStub
from xcapi.xray.app.proxyman.command.command_pb import AddOutboundRequest
from xcapi.xray.app.proxyman.config_pb import MultiplexingConfig, SenderConfig
from xcapi.xray.common.net.address_pb import IPOrDomain
from xcapi.xray.common.protocol.server_spec_pb import ServerEndpoint
from xcapi.xray.common.protocol.user_pb import User
from xcapi.xray.common.serial.typed_message_pb import GetMessageType, ToTypedMessage
from xcapi.xray.core.config_pb import OutboundHandlerConfig
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


def decode_base64url(b64_str: str) -> bytes:
    padding = "=" * (-len(b64_str) % 4)
    return base64.urlsafe_b64decode(b64_str + padding)


def parse_url(link: str) -> OutboundParams:
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    protocol = parsed.scheme
    user_id = parsed.username

    def get_param(key: str, default: str = "") -> str:
        return query.get(key, [default])[0]

    if (
        isinstance(parsed.hostname, str)
        and isinstance(parsed.port, int)
        and isinstance(user_id, str)
    ):
        return OutboundParams(
            protocol=protocol,
            address=parsed.hostname,
            port=parsed.port,
            user_id=user_id,
            sni=get_param("sni"),
            pbk=get_param("pbk"),
            security=get_param("security", "none"),
            type=get_param("type", "tcp"),
            fp=get_param("fp"),
            path=get_param("path", "/"),
            service_name=get_param("serviceName"),
            host=get_param("host"),
            alpn=query.get("alpn"),
        )
    msg = f"Error of parsing {link}"
    raise ValueError(msg)


def create_stream_settings(params: OutboundParams) -> StreamConfig:
    transports = []
    if params.type == "ws":
        transports.append(
            TransportConfig(
                protocol_name="websocket",
                settings=ToTypedMessage(WebsocketConfig(path=params.path)),
            ),
        )
    elif params.type == "grpc":
        transports.append(
            TransportConfig(
                protocol_name="grpc",
                settings=ToTypedMessage(GrpcConfig(service_name=params.service_name)),
            ),
        )
    elif params.type == "h2":
        transports.append(
            TransportConfig(
                protocol_name="http",
                settings=ToTypedMessage(
                    HttpConfig(host=[params.host] if params.host else []),
                ),
            ),
        )

    security = params.security.lower()
    if security == "tls":
        security_type = GetMessageType(TlsConfig)
        security_settings = [
            ToTypedMessage(TlsConfig(server_name=params.sni, allow_insecure=False)),
        ]

    elif security == "reality":
        security_type = GetMessageType(RealityConfig)
        security_settings = [
            ToTypedMessage(
                RealityConfig(
                    server_name=params.sni,
                    public_key=decode_base64url(params.pbk),
                    short_id=bytes.fromhex("1f"),
                    Fingerprint=params.fp,
                    show=False,
                ),
            ),
        ]
    else:
        security_type = 0
        security_settings = []

    return StreamConfig(
        protocol_name=params.type,
        transport_settings=transports,
        # security_type=security_type,
        security_type=str(security_type),
        security_settings=security_settings,
    )


def add_outbound(
    api_host: str,
    api_port: int,
    params: OutboundParams,
    tag: str = "auto-outbound",
) -> None:
    channel: Channel = insecure_channel(f"{api_host}:{api_port}")
    stub = HandlerServiceStub(channel)

    if params.protocol == "vless":
        proxy_config = VlessOutboundConfig(
            vnext=[
                ServerEndpoint(
                    address=IPOrDomain(domain=params.address),
                    port=params.port,
                    user=[
                        User(
                            level=0,
                            account=ToTypedMessage(
                                VlessAccount(id=params.user_id, encryption="none"),
                            ),
                        ),
                    ],
                ),
            ],
        )

    else:
        error_msg = "Unsuported protocol: " + params.protocol
        logger.error(error_msg)
        raise ValueError(error_msg)

    outbound_config = OutboundHandlerConfig(
        tag=tag,
        proxy_settings=ToTypedMessage(proxy_config),
        sender_settings=ToTypedMessage(
            SenderConfig(
                stream_settings=create_stream_settings(params),
                multiplex_settings=MultiplexingConfig(enabled=False),
            ),
        ),
    )

    stub.AddOutbound(AddOutboundRequest(outbound=outbound_config))
    logger.info("Outbound '%s' successfully added", tag)


params = parse_url(
    "vless://ca9ac6fc-7269-42c9-8e48-18d8f0449750@uae.panelmarzban.com:3040?security=reality&type=tcp&sni=refersion.com&pbk=21V_VkMUD2XRbyRDg7hjpblUAwxHvlLmbarATdhhJQI&fp=chrome#%F0%9F%94%92%F0%9F%87%A6%F0%9F%87%AA%20AE%2051.112.83.198%20%E2%97%88%20tcp%3A3040%20%E2%97%88%20Amazon.com%2C%20Inc.%20%2F%20Amazon%20Technologies%20Inc%20%E2%97%88%20a83f9",
)
add_outbound("127.0.0.1", 8080, params)
