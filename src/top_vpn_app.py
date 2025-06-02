import logging
from pathlib import Path

from subscription import SubscriptionManager

from .xray import XrayApi, XrayController

logger = logging.getLogger(__name__)
API_HOST = "127.0.0.1"
API_PORT = 8080


class TopVPNApp:
    def __init__(
        self,
        subscription_file: str | Path,
        api_host: str = API_HOST,
        api_port: int = API_PORT,
    ) -> None:
        self.subsctiption_manager = SubscriptionManager(
            self._load_subscriptions(subscription_file),
        )
        self.xray_controller = XrayController()
        self.xray_api = XrayApi(api_host, api_port)

    def _load_subscriptions(self, subscription_file: str | Path) -> list[str]:
        if isinstance(subscription_file, str):
            subscription_file = Path(subscription_file)
        try:
            with subscription_file.open(mode="r", encoding="utf-8") as file:
                content = file.read()
            subscriptions = [
                line for line in content.splitlines() if line.startswith("https://")
            ]
        except FileNotFoundError:
            logger.exception("Subscription file not found: %s", subscription_file)
            raise
        else:
            logger.info(
                "Loaded %s subscriptions, from %s",
                len(subscriptions),
                str(subscription_file),
            )
            return subscriptions
