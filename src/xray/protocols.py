from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from xray import inbound, outbound

if TYPE_CHECKING:
    from server.schema import Server
    from xray.stubs.core.config_pb2 import (
        InboundHandlerConfig,
        OutboundHandlerConfig,
    )


@dataclass
class InboundFunctions:
    add: Callable[[int, str], "InboundHandlerConfig"]


class InboundProtocol(Enum):
    socks = InboundFunctions(add=inbound.add_socks)
    http = InboundFunctions(add=inbound.add_http)

    def __init__(self, protocol: InboundFunctions) -> None:
        self.add = protocol.add


@dataclass
class OutboundFunctions:
    add: Callable[["Server", str], "OutboundHandlerConfig"]


class OutboundProtocol(Enum):
    vless = OutboundFunctions(add=outbound.add_vless)
    vmess = OutboundFunctions(add=outbound.add_vmess)

    def __init__(self, protocol: OutboundFunctions) -> None:
        self.add = protocol.add
