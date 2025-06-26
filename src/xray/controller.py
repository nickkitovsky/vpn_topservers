import logging
import pathlib

import psutil

logger = logging.getLogger(__name__)

XRAY_DIR = pathlib.Path(__file__).resolve().parent.parent / "xray"
BINARY_FILE = "xray"


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
