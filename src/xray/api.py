import logging
import pathlib
import sys
import time
from ipaddress import ip_address
from typing import TYPE_CHECKING, Any

from grpc import Channel, insecure_channel

# Add the 'grpc_api' directory to Python path to resolve protobuf imports
sys.path.append(str(pathlib.Path(__file__).parent.resolve()))
if TYPE_CHECKING:
    from src.server.protocols.vless import VlessParams
    from src.server.server import Server


from src.common_utils import decode_base64
from src.config import settings
from src.server.protocols.vless import VlessParams
from src.server.protocols.vmess import VmessParams

from .grpc_api.app.proxyman.command.command_pb2 import (
    AddInboundRequest,
    AddOutboundRequest,
    RemoveOutboundRequest,
)
from .grpc_api.app.proxyman.command.command_pb2_grpc import HandlerServiceStub
from .grpc_api.app.proxyman.config_pb2 import (
    MultiplexingConfig,
    ReceiverConfig,
    SenderConfig,
    SniffingConfig,
)
from .grpc_api.app.router.command.command_pb2 import AddRuleRequest, RemoveRuleRequest
from .grpc_api.app.router.command.command_pb2_grpc import RoutingServiceStub
from .grpc_api.app.router.config_pb2 import Config, RoutingRule
from .grpc_api.common.net.address_pb2 import IPOrDomain
from .grpc_api.common.net.network_pb2 import Network
from .grpc_api.common.net.port_pb2 import PortList, PortRange
from .grpc_api.common.protocol.headers_pb2 import AUTO, SecurityConfig
from .grpc_api.common.protocol.server_spec_pb2 import ServerEndpoint
from .grpc_api.common.protocol.user_pb2 import User
from .grpc_api.common.serial.typed_message_pb2 import TypedMessage
from .grpc_api.core.config_pb2 import InboundHandlerConfig, OutboundHandlerConfig
from .grpc_api.proxy.http.config_pb2 import ServerConfig as HttpServerConfig
from .grpc_api.proxy.socks.config_pb2 import AuthType, ServerConfig as SocksServerConfig
from .grpc_api.proxy.vless.account_pb2 import Account as VlessAccount
from .grpc_api.proxy.vless.outbound.config_pb2 import Config as VlessOutboundConfig
from .grpc_api.proxy.vmess.account_pb2 import Account as VmessAccount
from .grpc_api.proxy.vmess.outbound.config_pb2 import Config as VmessOutboundConfig
from .grpc_api.transport.internet.config_pb2 import StreamConfig, TransportConfig
from .grpc_api.transport.internet.grpc.config_pb2 import Config as GrpcConfig
from .grpc_api.transport.internet.reality.config_pb2 import Config as RealityConfig
from .grpc_api.transport.internet.tls.config_pb2 import Config as TlsConfig
from .grpc_api.transport.internet.websocket.config_pb2 import Config as WebsocketConfig

logger = logging.getLogger(__name__)


class XrayApi:
    def __init__(self, api_url: str = settings.XRAY_API_URL) -> None:
        self.api_url = api_url
        self.init_stubs()

    def init_stubs(self) -> None:
        channel: Channel = insecure_channel(self.api_url)
        self._handler_stub = HandlerServiceStub(channel)
        self._route_stub: RoutingServiceStub = RoutingServiceStub(channel)

    def add_outbound(self, server: "Server", tag: str = "outbound") -> None:
        if server.protocol.lower() == "vless":
            self._add_outbound_vless(server, tag)
        elif server.protocol.lower() == "vmess":
            self._add_outbound_vmess(server, tag)
        else:
            msg = f"Unsupported protocol: {server.protocol}"
            raise ValueError(msg)

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
        logger.debug("Added inbound %s", tag)

    def add_inbound_http(self, port: int, tag: str = "inbound") -> None:
        self._handler_stub.AddInbound(
            AddInboundRequest(
                inbound=InboundHandlerConfig(
                    tag=tag,
                    receiver_settings=self._to_typed_message(
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
                    proxy_settings=self._to_typed_message(
                        HttpServerConfig(
                            accounts={},
                        ),
                    ),
                ),
            ),
        )

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
            AddRuleRequest(shouldAppend=True, config=self._to_typed_message(cfg)),
        )
        logger.debug("Added rule %s", rt)

    def remove_outbound(self, tag: str) -> None:
        self._handler_stub.RemoveOutbound(RemoveOutboundRequest(tag=tag))
        logger.debug("Removed outbound %s", tag)

    def remove_routing_rule(self, rule_tag: str) -> None:
        self._route_stub.RemoveRule(
            RemoveRuleRequest(ruleTag=rule_tag),
        )

    def _add_outbound_vless(
        self,
        server: "Server",
        tag: str = "outbound",
    ) -> None:
        address = self._parse_address(server.address)
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
                            account=self._to_typed_message(
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

        outbound = OutboundHandlerConfig(
            tag=tag,
            proxy_settings=self._to_typed_message(proxy),
            sender_settings=self._to_typed_message(
                SenderConfig(
                    stream_settings=self._create_stream_settings_vless(server.params),
                    multiplex_settings=MultiplexingConfig(enabled=False),
                ),
            ),
        )
        self._handler_stub.AddOutbound(AddOutboundRequest(outbound=outbound))
        logger.debug("Added vless outbound %s", tag)

    def _add_outbound_vmess(
        self,
        server: "Server",
        tag: str = "outbound",
    ) -> None:
        if not isinstance(server.params, VmessParams):
            msg = "Invalid VMESS params"
            raise TypeError(msg)
        address = self._parse_address(server.params.add)
        params = server.params  # type: ignore

        proxy = VmessOutboundConfig(
            Receiver=[
                ServerEndpoint(
                    address=address,
                    port=int(server.port),
                    user=[
                        User(
                            level=0,
                            account=self._to_typed_message(
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

        outbound = OutboundHandlerConfig(
            tag=tag,
            proxy_settings=self._to_typed_message(proxy),
            sender_settings=self._to_typed_message(
                SenderConfig(
                    stream_settings=self._create_stream_settings_vmess(params),
                    multiplex_settings=MultiplexingConfig(enabled=False),
                ),
            ),
        )
        self._handler_stub.AddOutbound(AddOutboundRequest(outbound=outbound))
        logger.debug("Added vmess outbound %s", tag)

    def _parse_address(self, address: str) -> IPOrDomain:
        try:
            try:
                ip_address(address)
                return IPOrDomain(ip=bytes(map(int, address.split("."))))
            except ValueError:
                return IPOrDomain(domain=address)
        except Exception as e:
            msg = f"Invalid address format: {address}"
            logger.error(msg)  # noqa: TRY400
            raise ValueError(msg) from e

    def _create_stream_settings_vless(self, params: "VlessParams") -> StreamConfig:
        ts = []
        if params.type == "ws":
            ts.append(
                TransportConfig(
                    protocol_name="websocket",
                    settings=self._to_typed_message(
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
                    settings=self._to_typed_message(
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
            stype = self._get_message_type(TlsConfig)
            sconf = [
                self._to_typed_message(
                    TlsConfig(server_name=params.sni, allow_insecure=False),
                ),
            ]
        elif sec == "reality":
            stype = self._get_message_type(RealityConfig)
            sb = bytes.fromhex(params.sid)
            sconf = [
                self._to_typed_message(
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

    def _create_stream_settings_vmess(self, params: "VmessParams") -> StreamConfig:
        ts = []
        proto = "tcp"

        if params.net == "ws":
            proto = "websocket"
            ts.append(
                TransportConfig(
                    protocol_name="websocket",
                    settings=self._to_typed_message(
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
                    settings=self._to_typed_message(
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
            stype = self._get_message_type(TlsConfig)
            sconf = [
                self._to_typed_message(
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

    def _to_typed_message(self, message: Any) -> "TypedMessage":  # noqa: ANN401
        return TypedMessage(
            type=message.DESCRIPTOR.full_name,
            value=message.SerializeToString(),
        )

    def _get_message_type(self, message: Any) -> str:  # noqa: ANN401
        return message.DESCRIPTOR.full_name
