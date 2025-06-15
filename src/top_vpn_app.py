import logging
from pathlib import Path

from subscription import SubscriptionManager
from xray import XrayController

logger = logging.getLogger(__name__)


class TopVPNApp:
    def __init__(
        self,
        subscription_file: str | Path,
    ) -> None:
        self.subsctiption_manager = SubscriptionManager(
            self._read_subscriptions_file(subscription_file),
        )
        self.xray_controller = XrayController()

    async def run(self) -> None:
        await self.subsctiption_manager.fetch_subscription_data()

    def _read_subscriptions_file(self, subscription_file: str | Path) -> list[str]:
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
