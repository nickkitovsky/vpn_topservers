import contextlib
import logging
import pathlib
import time
from collections.abc import Generator, Iterable
from typing import TYPE_CHECKING, Any

import psutil
from src.config import settings
from src.xray.api import XrayApi

if TYPE_CHECKING:
    from src.server import Server

logger = logging.getLogger(__name__)


class XrayProcessHandler:
    def __init__(self, xray_dir: pathlib.Path = settings.XRAY_DIR) -> None:
        self.binary_path = xray_dir / pathlib.Path("xray")
        self.process: psutil.Popen | None = None

    def run(self) -> None:
        if self.is_running():
            logger.info("Xray is already running.")
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
            logger.info("Xray is not running.")

    def restart(self) -> None:
        logger.info("Restarting xray.exe...")
        self.stop()
        self.run()

    def is_running(self) -> bool:
        return bool(self._find_xray_proc())

    def stop_all_xray(self) -> None:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] == "xray.exe":
                proc.terminate()
                logger.info("Stopped xray.exe with PID: %s", proc.pid)

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
        api_url: str = "127.0.0.1:8080",
        start_port: int = 60000,
        pool_size: int = 50,
    ) -> None:
        self.api = XrayApi(api_url)
        self.start_port = start_port
        self.pool_size = pool_size
        self._proc_handler = XrayProcessHandler()

    def add_inbound_pool(self) -> None:
        for i in range(settings.XRAY_POOL_SIZE):
            self.api.add_inbound_http(
                settings.XRAY_START_INBOUND_PORT + i,
                f"inbound{i}",
            )
            # self.api.add_inbound_socks(
            #     settings.XRAY_START_INBOUND_PORT + i,
            #     f"inbound{i}",
            # )
            self.api.add_routing_rule(f"inbound{i}", f"outbound{i}", f"rule{i}")
        logger.info(
            "Inbound servers pool created (%d servers). first port:%d",
            settings.XRAY_POOL_SIZE,
            settings.XRAY_START_INBOUND_PORT,
        )

    @contextlib.contextmanager
    def outbound_pool(
        self,
        servers: Iterable["Server"],
    ) -> Generator[None, Any, None]:
        if self._proc_handler.is_running():
            logger.debug("Xray is already running. Restarting...")
            self._proc_handler.restart()
        else:
            logger.debug("Xray starting...")
            self._proc_handler.run()
        self.add_inbound_pool()
        logger.debug("Add inbound pool")
        for num, server in enumerate(servers):
            logger.debug(
                "Adding outbound %s for server %s",
                f"outbound{num}",
                server.address,
            )
            # TODO: FIX ANY API ERROR
            try:
                self.api.add_outbound(server, f"outbound{num}")
            except Exception:
                logger.exception(
                    "Error adding outbound %s for server %s",
                    num,
                    server.address,
                )
        yield
        logger.debug("Stopping xray...")
        self._proc_handler.stop()
        logger.debug("SLEEPING 3s...")
        time.sleep(3)
