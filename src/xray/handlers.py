import contextlib
import logging
import pathlib
from collections.abc import Generator, Iterable
from time import sleep
from typing import TYPE_CHECKING, Any

import psutil
from src.config import settings
from src.xray.api import XrayApi
from xray.protocols import InboundProtocol

if TYPE_CHECKING:
    from server.server import Server

logger = logging.getLogger(__name__)


class XrayProcessHandler:
    def __init__(self, xray_dir: pathlib.Path = settings.XRAY_DIR) -> None:
        self.binary_path = xray_dir / pathlib.Path("xray")
        self.process: psutil.Popen | None = None

    def run(self) -> None:
        if self.is_running():
            logger.debug("Xray is already running.")
            return

        self.process = psutil.Popen(
            [self.binary_path],
            cwd=str(settings.XRAY_DIR),
        )
        logger.info("Started xray.exe with PID: %s", self.process.pid)

    def stop(self) -> None:
        if self.process:
            self._terminate_process(self.process)
        elif proc := self._find_xray_proc():
            self._terminate_process(proc)
        else:
            logger.debug("Xray is not running.")

    def restart(self) -> None:
        logger.debug("Restarting xray.exe...")
        self.stop()
        self.run()

    def is_running(self) -> bool:
        return bool(self._find_xray_proc())

    def stop_all_xray(self) -> None:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] == "xray.exe":
                proc.terminate()
                logger.debug("Stopped xray.exe with PID: %s", proc.pid)

    def _terminate_process(self, process: psutil.Process) -> None:
        logger.info("Stopping xray.exe with PID: %s", process.pid)
        try:
            process.terminate()
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            logger.warning("Process %s already terminated.", process.pid)
        except psutil.TimeoutExpired:
            logger.warning(
                "Process %s did not terminate in time, killing it.",
                process.pid,
            )
            process.kill()  # If it doesn't terminate, force kill it.
            process.wait(timeout=5)
        self.process = None

    def _find_xray_proc(self) -> psutil.Process | None:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] == "xray.exe":
                return proc
        return None


class XrayPoolHandler:
    def __init__(
        self,
        api_url: str = settings.XRAY_API_URL,
        start_port: int = settings.XRAY_START_INBOUND_PORT,
        pool_size: int = settings.XRAY_POOL_SIZE,
    ) -> None:
        self.api = XrayApi(api_url)
        self.start_port = start_port
        self.pool_size = pool_size
        self.process_manager = XrayProcessHandler()

    def add_inbound_pool(
        self,
        protocol: InboundProtocol = InboundProtocol.socks,
    ) -> None:
        for i in range(self.pool_size):
            self.api.add_inbound(
                protocol,
                self.start_port + i,
                f"inbound{i}",
            )
            self.api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
        logger.debug(
            "Inbound servers pool created (%d servers). first port:%d",
            self.pool_size,
            self.start_port,
        )

    @contextlib.contextmanager
    def outbound_pool(
        self,
        servers: Iterable["Server"],
    ) -> Generator[None, Any, None]:
        if self.process_manager.is_running():
            self.api.init_handler_stubs()
        else:
            logger.debug("Xray not running. Starting...")
            self.process_manager.run()
            self.api.init_handler_stubs()
            self.add_inbound_pool()
        logger.debug("Add inbound pool")
        outbound_tags = []
        for num, server in enumerate(servers):
            logger.debug(
                "Adding outbound %s for server %s",
                f"outbound{num}",
                server.address,
            )
            # TODO: FIX ANY API ERROR
            try:
                self.api.add_outbound(server, f"outbound{num}")
                outbound_tags.append(f"outbound{num}")
            except Exception as e:
                logger.warning(
                    "Error adding outbound %s | error: %s",
                    server.raw_url,
                    e,
                )
        yield
        # TODO: Add except error and restart xray
        logger.debug("Wait 0.5 sec before removing outbound")
        sleep(0.5)
        for outbound_tag in outbound_tags:
            self.api.remove_outbound(outbound_tag)
