import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.server.protocols.vless import VlessParams
    from src.server.server import Server


from src.common_utils import decode_base64
from src.server.protocols.vless import VlessParams
from src.xray.grpc_api.app.proxyman.config_pb2 import (
    MultiplexingConfig,
    SenderConfig,
)
from src.xray.grpc_api.common.protocol.server_spec_pb2 import ServerEndpoint
from src.xray.grpc_api.common.protocol.user_pb2 import User
from src.xray.grpc_api.core.config_pb2 import OutboundHandlerConfig
from src.xray.grpc_api.proxy.vless.account_pb2 import Account as VlessAccount
from src.xray.grpc_api.proxy.vless.outbound.config_pb2 import (
    Config as VlessOutboundConfig,
)
from src.xray.grpc_api.transport.internet.config_pb2 import (
    StreamConfig,
    TransportConfig,
)
from src.xray.grpc_api.transport.internet.grpc.config_pb2 import Config as GrpcConfig
from src.xray.grpc_api.transport.internet.reality.config_pb2 import (
    Config as RealityConfig,
)
from src.xray.grpc_api.transport.internet.tls.config_pb2 import Config as TlsConfig
from src.xray.grpc_api.transport.internet.websocket.config_pb2 import (
    Config as WebsocketConfig,
)
from src.xray.helpers import get_message_type, parse_address, to_typed_message


def add_vless(
    server: "Server",
    tag: str = "outbound",
) -> OutboundHandlerConfig:
    address = parse_address(server.address)
    if not isinstance(server.params, VlessParams):
        msg = "Invalid VLESS params"
        # TODO: add custom exception
        raise TypeError(msg)
    proxy = VlessOutboundConfig(
        vnext=[
            ServerEndpoint(
                address=address,
                port=server.port,
                user=[
                    User(
                        level=0,
                        account=to_typed_message(
                            VlessAccount(
                                id=server.username,
                                encryption="none",
                                flow=server.params.flow,
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
                stream_settings=_create_stream_settings_vless(server.params),
                multiplex_settings=MultiplexingConfig(enabled=False),
            ),
        ),
    )


def _create_stream_settings_vless(params: "VlessParams") -> StreamConfig:
    ts = []
    if params.type == "ws":
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

    elif params.type == "grpc":
        service_name = (params.service_name or "grpc") + f"_{time.time()}"
        ts.append(
            TransportConfig(
                protocol_name="grpc",
                settings=to_typed_message(
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

    sec = params.security.lower()
    if sec == "tls":
        stype = get_message_type(TlsConfig)
        sconf = [
            to_typed_message(
                TlsConfig(server_name=params.sni, allow_insecure=False),
            ),
        ]
    elif sec == "reality":
        stype = get_message_type(RealityConfig)
        sb = bytes.fromhex(params.sid)
        sconf = [
            to_typed_message(
                RealityConfig(
                    server_name=params.sni,
                    public_key=decode_base64(params.pbk),
                    short_id=sb,
                    Fingerprint=params.fp,
                    show=False,
                ),
            ),
        ]
    else:
        # TODO: check stype = ""
        stype = 0
        sconf = []

    return StreamConfig(
        protocol_name="tcp",
        transport_settings=ts,
        security_type=str(stype),
        security_settings=sconf,
    )
