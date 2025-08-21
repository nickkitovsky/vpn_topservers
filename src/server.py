import json
import logging
import pathlib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from itertools import islice
from typing import TYPE_CHECKING, Callable
from urllib.parse import parse_qs, urlparse

from src.config import settings
from src.models import Server, VlessParams
from src.prober import ConnectionProber, HttpProber

if TYPE_CHECKING:
    from src.models import Subscription

logger = logging.getLogger(__name__)


class ServerParser:
    def __init__(self) -> None:
        self.supported_protocols: dict[str, Callable[[str], VlessParams]] = {
            "vless": self.parse_vless_params,
        }

    @classmethod
    def get_supported_protocols(cls) -> set[str]:
        return set(cls().supported_protocols.keys())

    def parse_url(self, url: str, subscription_url: str = "") -> Server:
        logger.debug("Parsing server URL: %s", url)
        parsed = urlparse(url)
        if not (parsed.scheme and parsed.hostname and parsed.port):
            msg = f"Error parsing link: {url}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            params = self.supported_protocols[parsed.scheme](parsed.query)
        except KeyError:
            msg = f"Unsupported protocol in link: {url}"
            logger.error(msg)  # noqa: TRY400
            raise ValueError(msg)  # noqa: B904
        else:
            connection_data = {
                "protocol": parsed.scheme,
                "address": str(parsed.hostname),
                "port": parsed.port,
                "username": parsed.username or "",
                "params": params,
            }
            server = Server(
                **connection_data,
                raw_url=url,
                from_subscription=subscription_url,
            )
            logger.debug("Successfully parsed server: %s", server)
            return server

    def parse_vless_params(self, raw_params: str) -> VlessParams:
        logger.debug("Parsing VLESS params from: %s", raw_params)
        query = parse_qs(raw_params)

        def get_param(key: str) -> str:
            return query.get(key, [""])[0]

        return VlessParams(
            sni=get_param("sni"),
            pbk=get_param("pbk"),
            security=get_param("security") or "none",
            type=get_param("type") or "tcp",
            fp=get_param("fp"),
            path=get_param("path") or "/",
            service_name=get_param("serviceName"),
            host=get_param("host"),
            alpn=query.get("alpn"),
            sid=get_param("sid"),
            flow=get_param("flow"),
        )


class ServerManager:
    def __init__(self):
        self.servers: set[Server] = set()
        self.parser = ServerParser()
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
                server = self.parser.parse_url(server_url, subscription.url)
            except ValueError:  # noqa: PERF203
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

    def write_servers_dump(self, dump_file_location: str | pathlib.Path) -> None:
        dump_data = defaultdict(list)
        if isinstance(dump_file_location, str):
            dump_file_location = pathlib.Path(dump_file_location)
        for server in self.servers:
            dump_data[server.from_subscription].append(server.raw_url)
        try:
            with dump_file_location.open("w") as dump_file:
                json.dump(dump_data, dump_file)
        except OSError:
            logger.exception("Error of write dump file: %s")
        else:
            logger.info("Dump file %s successfully created.", dump_file_location)

    def read_servers_dump(self, dump_file_location: str | pathlib.Path) -> None:
        if isinstance(dump_file_location, str):
            dump_file_location = pathlib.Path(dump_file_location)
        try:
            with dump_file_location.open("r") as dump_file:
                dump_data = json.load(dump_file)
        except OSError:
            logger.exception("Error of read dump file: %s")
        else:
            for subscription_url, server_urls in dump_data.items():
                for server_url in server_urls:
                    self.servers.add(
                        self.parser.parse_url(server_url, subscription_url),
                    )
            logger.info("Dump file %s successfully loaded.", dump_file_location)

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
