import base64
import logging
import pathlib
import time
from ipaddress import ip_address

import psutil
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

from .schemas import OutboundParams, Server

XRAY_DIR = pathlib.Path(__file__).resolve().parent.parent / "xray"
BINARY_FILE = "xray"
logger = logging.getLogger(__name__)


class XrayController:
    def __init__(self, xray_dir: pathlib.Path = XRAY_DIR) -> None:
        self.binary_path = xray_dir / pathlib.Path(BINARY_FILE)
        self.process: psutil.Popen | None = None

    def run(self) -> None:
        if self.is_running():
            logger.info("Xray is already running.")
            return

        self.process = psutil.Popen(
            [self.binary_path],
            cwd=str(XRAY_DIR),
        )
        logger.info("Started xray.exe with PID: %s", self.process.pid)

    def stop(self) -> None:
        if self.process:
            self._terminate_process(self.process)
        elif proc := self._find_xray_proc():
            self._terminate_process(proc)
        else:
            logger.info("Xray is not running.")

    def restart(self) -> None:
        logger.info("Restarting xray.exe...")
        self.stop()
        self.run()

    def is_running(self) -> bool:
        return bool(self._find_xray_proc())

    def _terminate_process(self, process: psutil.Process) -> None:
        logger.info("Stopping xray.exe with PID: %s", process.info["pid"])
        try:
            process.terminate()
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            logger.warning("Process %s already terminated.", process.info["pid"])
        except psutil.TimeoutExpired:
            logger.warning(
                "Process %s did not terminate in time, killing it.",
                process.info["pid"],
            )
            process.kill()  # If it doesn't terminate, force kill it.
            process.wait(timeout=5)
        self.process = None

    def _find_xray_proc(self) -> psutil.Process | None:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] == BINARY_FILE:
                return proc
        return None


class XrayApi:
    def __init__(self, api_host: str = "127.0.0.1", api_port: int = 8080) -> None:
        channel: Channel = insecure_channel(f"{api_host}:{api_port}")
        self._handler_stub = HandlerServiceStub(channel)
        self._route_stub: RoutingServiceStub = RoutingServiceStub(channel)

    def add_outbound_vless(
        self,
        server: Server,
        tag: str = "outbound",
    ) -> None:
        if server.connection_details.protocol != "vless":
            msg = f"Unsupported protocol: {server.connection_details.protocol}"
            raise ValueError(msg)
        address = _parse_address(server.connection_details.address)
        proxy = VlessOutboundConfig(
            vnext=[
                ServerEndpoint(
                    address=address,
                    port=server.connection_details.port,
                    user=[
                        User(
                            level=0,
                            account=ToTypedMessage(
                                VlessAccount(
                                    id=server.params.user_id,
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
            proxy_settings=ToTypedMessage(proxy),
            sender_settings=ToTypedMessage(
                SenderConfig(
                    stream_settings=_create_stream_settings(server.params),
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


def _parse_address(address: str) -> IPOrDomain:
    try:
        try:
            ip_address(address)
            return IPOrDomain(ip=bytes(map(int, address.split("."))))
        except ValueError:
            return IPOrDomain(domain=address)
    except Exception as e:
        msg = f"Invalid address format: {address}"
        logger.exception(msg)
        raise ValueError(msg) from e


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
