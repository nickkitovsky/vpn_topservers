import logging
import pathlib
from subprocess import CREATE_NO_WINDOW, Popen

XRAY_DIR = pathlib.Path(__file__).resolve().parent.parent / "xray"
logger = logging.getLogger(__name__)


class XrayController:
    def __init__(self) -> None:
        self.binary_path = XRAY_DIR / pathlib.Path("xray.exe")
        self.process: Popen | None = None

    def run(self) -> None:
        if self.is_running():
            logger.info("Xray is already running.")
            return

        self.process = Popen(  # noqa: S603
            [self.binary_path],
            cwd=str(XRAY_DIR),
            creationflags=CREATE_NO_WINDOW,  # Windows only: hides console
        )
        logger.info("Started xray.exe with PID: %s", self.process.pid)

    def stop(self) -> None:
        if self.process and self.is_running():
            logger.info("Stopping xray.exe with PID: %s", self.process.pid)
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
        else:
            logger.info("Xray is not running.")

    def restart(self) -> None:
        logger.info("Restarting xray.exe...")
        self.stop()
        self.run()

    def is_running(self) -> bool:
        if not self.process:
            return False
        return self.process.poll() is None
