import logging
import pathlib
import sys

# Add the 'grpc_api' directory to Python path to resolve protobuf imports
sys.path.append(str(pathlib.Path(__file__).parent.resolve()))


from src.xray.stubs.app.proxyman.command.command_pb2 import (
    AddInboundRequest,
)
from src.xray.stubs.app.proxyman.config_pb2 import (
    ReceiverConfig,
    SniffingConfig,
)
from src.xray.stubs.common.net.address_pb2 import IPOrDomain
from src.xray.stubs.common.net.port_pb2 import PortList, PortRange
from src.xray.stubs.core.config_pb2 import InboundHandlerConfig
from src.xray.stubs.proxy.socks.config_pb2 import (
    AuthType,
    ServerConfig as SocksServerConfig,
)

logger = logging.getLogger(__name__)


def add_inbound_socks(self, port: int, tag: str = "inbound") -> None:
    inbound = InboundHandlerConfig(
        tag=tag,
        receiver_settings=self._to_typed_message(
            ReceiverConfig(
                port_list=PortList(range=[PortRange(From=port, To=port)]),
                listen=IPOrDomain(ip=bytes([127, 0, 0, 1])),
                sniffing_settings=SniffingConfig(
                    enabled=True,
                    destination_override=["http", "tls"],
                ),
            ),
        ),
        proxy_settings=self._to_typed_message(
            SocksServerConfig(
                auth_type=AuthType.NO_AUTH,  # type: ignore reportArgumentType
                address=IPOrDomain(ip=bytes([0, 0, 0, 0])),
                udp_enabled=True,
            ),
        ),
    )

    self._handler_stub.AddInbound(AddInboundRequest(inbound=inbound))
