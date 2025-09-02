from src.xray.api import Messaages
from src.xray.grpc_api.app.proxyman.config_pb2 import (
    ReceiverConfig,
    SniffingConfig,
)
from src.xray.grpc_api.common.net.address_pb2 import IPOrDomain
from src.xray.grpc_api.common.net.port_pb2 import PortList, PortRange
from src.xray.grpc_api.core.config_pb2 import InboundHandlerConfig
from src.xray.grpc_api.proxy.http.config_pb2 import ServerConfig as HttpServerConfig


def add_http(port: int, tag: str = "inbound") -> InboundHandlerConfig:
    return InboundHandlerConfig(
        tag=tag,
        receiver_settings=Messaages.to_typed_message(
            ReceiverConfig(
                port_list=PortList(
                    range=[
                        PortRange(
                            From=port,
                            To=port,
                        ),
                    ],
                ),
                listen=IPOrDomain(
                    ip=bytes([127, 0, 0, 1]),
                ),
                sniffing_settings=SniffingConfig(
                    enabled=True,
                    destination_override=["http", "tls"],
                ),
            ),
        ),
        proxy_settings=Messaages.to_typed_message(
            HttpServerConfig(
                accounts={},
            ),
        ),
    )
