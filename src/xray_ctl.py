import contextlib
import logging
import pathlib
import subprocess

import psutil

XRAY_DIR = pathlib.Path(__file__).resolve().parent.parent / "xray"
XRAY_BIN = "xray"

logger = logging.getLogger(__name__)


def run() -> None:
    try:
        subprocess.run(  # noqa: S603
            [str(XRAY_DIR / XRAY_BIN)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.exception("Xray failed to start: %s", e.stderr)
        raise
    logger.info("Xray started")


def is_running() -> bool:
    return bool(_get_pid())


def terminate() -> None:
    if pid := _get_pid():
        psutil.Process(pid).terminate()
        logger.info("Xray terminated")
        return
    msg = "Process not found"
    raise psutil.Error(msg)


def restart_to_default() -> None:
    with contextlib.suppress(psutil.Error):
        terminate()
    run()
    logger.info("Xray restarted")


def _get_pid() -> int | None:
    for process in psutil.process_iter(attrs=["pid", "name"]):
        if XRAY_BIN in process.info["name"].lower():
            return process.info["pid"]
    return None
