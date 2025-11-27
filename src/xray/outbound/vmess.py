from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.server.server import Server


from src.server.protocols.vmess import VmessParams
from src.xray.stubs.app.proxyman.config_pb2 import (
    MultiplexingConfig,
    SenderConfig,
)
from src.xray.stubs.common.protocol.headers_pb2 import AUTO, SecurityConfig
from src.xray.stubs.common.protocol.server_spec_pb2 import ServerEndpoint
from src.xray.stubs.common.protocol.user_pb2 import User
from src.xray.stubs.core.config_pb2 import OutboundHandlerConfig
from src.xray.stubs.proxy.vmess.account_pb2 import Account as VmessAccount
from src.xray.stubs.proxy.vmess.outbound.config_pb2 import (
    Config as VmessOutboundConfig,
)
from src.xray.stubs.transport.internet.config_pb2 import (
    StreamConfig,
    TransportConfig,
)
from src.xray.stubs.transport.internet.grpc.config_pb2 import Config as GrpcConfig
from src.xray.stubs.transport.internet.tls.config_pb2 import Config as TlsConfig
from src.xray.stubs.transport.internet.websocket.config_pb2 import (
    Config as WebsocketConfig,
)
from xray.helpers import get_message_type, parse_address, to_typed_message


def add_vmess(
    server: "Server",
    tag: str = "outbound",
) -> OutboundHandlerConfig:
    if not isinstance(server.params, VmessParams):
        # TODO: add custom exception

        msg = "Invalid VMESS params"
        raise TypeError(msg)
    address = parse_address(server.params.add)
    params = server.params

    proxy = VmessOutboundConfig(
        Receiver=[
            ServerEndpoint(
                address=address,
                port=int(server.port),
                user=[
                    User(
                        level=0,
                        account=to_typed_message(
                            VmessAccount(
                                id=server.username,
                                security_settings=SecurityConfig(
                                    type=AUTO,
                                ),
                            ),
                        ),
                    ),
                ],
            ),
        ],
    )

    return OutboundHandlerConfig(
        tag=tag,
        proxy_settings=to_typed_message(proxy),
        sender_settings=to_typed_message(
            SenderConfig(
                stream_settings=_create_stream_settings_vmess(params),
                multiplex_settings=MultiplexingConfig(enabled=False),
            ),
        ),
    )


def _create_stream_settings_vmess(params: "VmessParams") -> StreamConfig:
    ts = []
    proto = "tcp"

    if params.net == "ws":
        proto = "websocket"
        ts.append(
            TransportConfig(
                protocol_name="websocket",
                settings=to_typed_message(
                    WebsocketConfig(
                        path=params.path,
                        host=params.host or params.sni or "",
                    ),
                ),
            ),
        )

    elif params.net == "grpc":
        proto = "grpc"
        ts.append(
            TransportConfig(
                protocol_name="grpc",
                settings=to_typed_message(
                    GrpcConfig(
                        multi_mode=True,
                        authority=params.host or params.sni or "",
                        idle_timeout=10,
                        health_check_timeout=20,
                    ),
                ),
            ),
        )
    # TODO: add H2 transport
    sec = params.tls.lower()
    if sec == "tls":
        stype = get_message_type(TlsConfig)
        sconf = [
            to_typed_message(
                TlsConfig(server_name=params.sni, allow_insecure=False),
            ),
        ]

    else:
        stype = ""
        sconf = []

    return StreamConfig(
        protocol_name=proto,
        transport_settings=ts,
        security_type=str(stype),
        security_settings=sconf,
    )
