import logging
import pathlib
from typing import TYPE_CHECKING, Any

from src.xray.api import XrayApi

if TYPE_CHECKING:
    from src.server import Server
logger = logging.getLogger(__name__)


class XrayPoolManager:
    def __init__(
        self,
        api_url: str = "127.0.0.1:8080",
        start_port: int = 60000,
        pool_size: int = 50,
    ) -> None:
        self.api = XrayApi(api_url)
        self.start_port = start_port
        self.pool_size = pool_size
        self.proc_handler = XrayProcessHandler()
