import asyncio
import logging
import pathlib

from src.logger_config import setup_logging
from src.server import ServerManager
from src.subscription import SubscriptionManager

setup_logging(debug=True)
logger = logging.getLogger(__name__)


def setup_env() -> None:
    pathlib.Path("logs").mkdir(parents=True, exist_ok=True)


async def main() -> None:
    setup_env()
    logger.debug("start vpn-topservers!")
    subscription = SubscriptionManager()
    subscription.add_subscription_from_file("instanbul.txt")
    await subscription.fetch_subscriptions_content()
    server_manager = ServerManager()
    server_manager.add_from_subscriptions(subscription.subscriptions)
    await server_manager.filter_alive_connection_servers()
    await server_manager.filter_alive_http_servers()
    server_manager.write_servers_dump("dump.json")


if __name__ == "__main__":
    asyncio.run(main())
