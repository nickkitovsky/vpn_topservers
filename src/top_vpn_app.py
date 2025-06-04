import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

from schemas import Server
from subscription import SubscriptionManager
from xray import XrayApi, XrayController

logger = logging.getLogger(__name__)
API_HOST = "127.0.0.1"
API_PORT = 8080
# CHUNK_SIZE equals to amount of inbound servers in xray config: inbounds_routes.json
CHUNK_SIZE: int = 50


class TopVPNApp:
    def __init__(
        self,
        subscription_file: str | Path,
        api_host: str = API_HOST,
        api_port: int = API_PORT,
    ) -> None:
        self.subsctiption_manager = SubscriptionManager(
            self._read_subscriptions_file(subscription_file),
        )
        self.xray_controller = XrayController()
        self.xray_api = XrayApi(api_host, api_port)

    async def run(self) -> None:
        await self.subsctiption_manager.collect_subscription_data()

    def _add_outbound_proxies(
        self,
        proxy_count: int = 0,
    ) -> Generator[list[Server], Any, None]:
        all_servers = self.subsctiption_manager.top_fastest_connention_time_servers(
            proxy_count,
        )
        chunked_servers = [
            all_servers[i : i + CHUNK_SIZE]
            for i in range(0, len(all_servers), CHUNK_SIZE)
        ]
        for servers_chunk in chunked_servers:
            for num, server in enumerate(servers_chunk):
                self.xray_api.add_outbound_vless(server, f"outbound{num}")
                # TODO: add __str__ to Server with address and port
                server_data = f"{server.connection_details.address}:{server.connection_details.port}"
                logger.debug("add %s to outbound%s", server_data, num)
            yield servers_chunk

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
