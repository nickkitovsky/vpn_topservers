import json
import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import settings
from src.prober import ConnectionProber, HttpProber
from src.server.exceptions import ServerError
from src.server.parser import parse_url
from src.server.schema import Server

if TYPE_CHECKING:
    from src.models import Subscription

logger = logging.getLogger(__name__)


class ServerManager:
    def __init__(self):
        self.servers: set[Server] = set()
        self.connection_prober = ConnectionProber()
        self.http_prober = HttpProber()
        logger.debug("ServerManager initialized.")

    def add_from_subscription(
        self,
        subscription: "Subscription",
        *,
        only_443_port: bool = False,
    ) -> None:
        logger.debug(
            "Adding servers from subscription: %s (only_443_port=%s)",
            subscription.url,
            only_443_port,
        )
        initial_server_count = len(self.servers)
        for server_url in subscription.servers:
            try:
                server = parse_url(server_url, subscription.url)
            except ServerError:  # noqa: PERF203
                continue
            else:
                if (only_443_port and server.port != 443) or (  # noqa: PLR2004
                    not only_443_port and server
                ):
                    self.servers.add(server)

        added_count = len(self.servers) - initial_server_count
        logger.info(
            "Added %d new servers from subscription %s. Total servers: %d",
            added_count,
            subscription.url,
            len(self.servers),
        )

    def add_from_subscriptions(self, subscriptions: Iterable["Subscription"]) -> None:
        for subscription in subscriptions:
            self.add_from_subscription(subscription)

    async def filter_alive_connection_servers(self) -> None:
        await self.connection_prober.probe(self.servers)
        self.servers = {
            server
            for server in self.servers
            if server.response_time.connection < settings.DONT_ALIVE_CONNECTION_TIME
        }

    async def filter_alive_http_servers(self) -> None:
        await self.http_prober.probe(self.servers)
        self.servers = {
            server
            for server in self.servers
            if sum(server.response_time.http.values())
            < settings.DONT_ALIVE_CONNECTION_TIME
        }

    def fastest_connention_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        logger.debug(
            "Getting %s fastest servers by connection time.",
            "all" if server_amount == 0 else server_amount,
        )
        sorted_servers = sorted(self.servers, key=lambda s: s.response_time.connection)
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def fastest_http_response_time_servers(
        self,
        server_amount: int = 0,
    ) -> Iterator[Server]:
        logger.debug(
            "Getting %s fastest servers by HTTP response time.",
            "all" if server_amount == 0 else server_amount,
        )
        sorted_servers = sorted(
            self.servers,
            key=lambda s: sum(s.response_time.http.values()),
        )
        if server_amount == 0:
            return iter(sorted_servers)
        return islice(sorted_servers, server_amount)

    def export_subscription(
        self,
        subscription_filename: str | Path | None = None,
        num_of_servers: int = 0,
    ) -> None:
        exporter = ServerExporter()
        exporter.write_subscription(
            self.fastest_http_response_time_servers(num_of_servers),
            subscription_filename,
        )


class ServerExporter:
    def generate_subscription(self, servers: Iterable[Server]) -> str:
        subscription_list = [
            "#".join((server.raw_url.split("#")[0], f"server{num}"))
            for num, server in enumerate(servers)
        ]
        return "\n".join(subscription_list)

    def write_subscription(
        self,
        servers: Iterable[Server],
        subscription_filename: str | Path | None = None,
    ) -> None:
        if subscription_filename is None:
            subscription_filename = "subscription.txt"
        if isinstance(subscription_filename, str):
            subscription_filename = Path(subscription_filename)
        subscription_filename.write_text(self.generate_subscription(servers))
        logger.info("Subscription file %s successfully created.", subscription_filename)


class ServerDumper:
    def _generate_dump_filename(self) -> Path:
        now = datetime.now()  # noqa: DTZ005
        seconds_of_day = now.hour * 3600 + now.minute * 60 + now.second
        return Path(f"{now.day}.{now.month}.{now.year}_{seconds_of_day}.json")

    def write_servers_dump(
        self,
        servers: set[Server],
        dump_filename: str | Path | None = None,
    ) -> None:
        if dump_filename is None:
            dump_filename = self._generate_dump_filename()
        elif isinstance(dump_filename, str):
            dump_filename = Path(dump_filename)
        dump_data = defaultdict(list)
        for server in servers:
            dump_data[server.from_subscription].append(server.raw_url)
        try:
            with (settings.DUMPS_DIR / dump_filename).open("w") as dump_file:
                json.dump(dump_data, dump_file)
        except OSError:
            logger.exception("Error of write dump file: %s", str(dump_filename))
        else:
            logger.info("Dump file %s successfully created.", str(dump_filename))

    def read_servers_dump(
        self,
        dump_filename: str | Path,
        servers: set[Server],
    ) -> None:
        try:
            with Path(dump_filename).open("r") as dump_file:
                dump_data = json.load(dump_file)
        except OSError:
            logger.exception("Error of read dump file: %s", dump_filename)
        else:
            for subscription_url, server_urls in dump_data.items():
                for server_url in server_urls:
                    servers.add(
                        parse_url(server_url, subscription_url),
                    )
            logger.info("Dump file %s successfully loaded.", dump_file)
