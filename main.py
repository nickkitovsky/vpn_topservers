import logging
import pathlib

from src.logger_config import setup_logging
from src.xray import XrayController

setup_logging(debug=True)
logger = logging.getLogger(__name__)


def setup_env() -> None:
    pathlib.Path("logs").mkdir(parents=True, exist_ok=True)


def main() -> None:
    setup_env()
    logger.debug("start vpn-topservers!")
    xray_controller = XrayController()
    xray_controller.run()


if __name__ == "__main__":
    main()
