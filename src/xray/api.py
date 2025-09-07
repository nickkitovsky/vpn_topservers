import logging
from typing import TYPE_CHECKING

from grpc import Channel, insecure_channel
from src.xray.helpers import to_typed_message
from src.xray.protocols import InboundProtocol, OutboundProtocol

# # Add the 'grpc_api' directory to Python path to resolve protobuf imports
# sys.path.append(str(pathlib.Path(__file__).parent.resolve()))
if TYPE_CHECKING:
    from src.server.server import Server


from src.config import settings
from src.xray.stubs.app.proxyman.command.command_pb2 import (
    AddInboundRequest,
    AddOutboundRequest,
    RemoveOutboundRequest,
)
from src.xray.stubs.app.proxyman.command.command_pb2_grpc import (
    HandlerServiceStub,
)
from src.xray.stubs.app.router.command.command_pb2 import (
    AddRuleRequest,
    RemoveRuleRequest,
)
from src.xray.stubs.app.router.command.command_pb2_grpc import RoutingServiceStub
from src.xray.stubs.app.router.config_pb2 import Config, RoutingRule
from src.xray.stubs.common.net.network_pb2 import Network

logger = logging.getLogger(__name__)


class XrayApi:
    def __init__(self, api_url: str = settings.XRAY_API_URL) -> None:
        self.api_url = api_url
        self.init_handler_stubs()

    def init_handler_stubs(self) -> None:
        channel: Channel = insecure_channel(self.api_url)
        self._handler_stub = HandlerServiceStub(channel=channel)
        self._route_stub: RoutingServiceStub = RoutingServiceStub(channel=channel)

    def add_outbound(self, server: "Server", tag: str = "outbound") -> None:
        try:
            handler_config = OutboundProtocol[server.protocol].add(server, tag)
        except KeyError:
            # TODO: Add custom exception
            msg = f"Unsupported protocol: {server.protocol}"
            raise ValueError(msg)  # noqa: B904
        else:
            self._handler_stub.AddOutbound(AddOutboundRequest(outbound=handler_config))
            logger.debug("Added outbound %s (%s)", tag, server.protocol)

    def add_inbound(
        self,
        protocol: InboundProtocol,
        port: int,
        tag: str = "inbound",
    ) -> None:
        handler_config = protocol.add(port, tag)
        self._handler_stub.AddInbound(AddInboundRequest(inbound=handler_config))
        logger.debug("Added inbound %s (%s)", tag, protocol.name)

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
            AddRuleRequest(shouldAppend=True, config=to_typed_message(cfg)),
        )
        logger.debug("Added rule %s", rt)

    def remove_outbound(self, tag: str) -> None:
        self._handler_stub.RemoveOutbound(RemoveOutboundRequest(tag=tag))
        logger.debug("Removed outbound %s", tag)

    def remove_routing_rule(self, rule_tag: str) -> None:
        self._route_stub.RemoveRule(
            RemoveRuleRequest(ruleTag=rule_tag),
        )
