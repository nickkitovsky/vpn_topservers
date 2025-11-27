from xray.helpers import to_typed_message
from xray.stubs.app.proxyman.config_pb2 import (
    ReceiverConfig,
    SniffingConfig,
)
from xray.stubs.common.net.address_pb2 import IPOrDomain
from xray.stubs.common.net.port_pb2 import PortList, PortRange
from xray.stubs.core.config_pb2 import InboundHandlerConfig
from xray.stubs.proxy.http.config_pb2 import ServerConfig as HttpServerConfig


def add_http(port: int, tag: str = "inbound") -> InboundHandlerConfig:
    return InboundHandlerConfig(
        tag=tag,
        receiver_settings=to_typed_message(
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
        proxy_settings=to_typed_message(
            HttpServerConfig(
                accounts={},
            ),
        ),
    )
