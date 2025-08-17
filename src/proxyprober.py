import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.server import Server

from curl_cffi import AsyncCurl, AsyncSession, CurlOpt, exceptions as curl_exceptions
from src.config import settings
from src.xray.api import XrayApi

if TYPE_CHECKING:
    from src.server import Server


# TODO: Add close session
class CurlCFFIProber:
    def __init__(self):
        self._session = self.setup_session()

    def setup_session(
        self,
        timeout: int = settings.PROXYPROBER_TIMEOUT,
        headers: dict[str, str] | None = None,
        *,
        connect_only: bool = False,
    ) -> AsyncSession:
        if headers is None:
            headers = {"Connection": "close"}

        acurl = AsyncCurl()
        # Запрещает повторное использование соединения
        acurl.setopt(CurlOpt.FORBID_REUSE, 1)
        # Всегда создаёт новое TCP-соединение
        acurl.setopt(CurlOpt.FRESH_CONNECT, 1)
        # 1 = только соединение, без HTTP-запроса
        acurl.setopt(CurlOpt.CONNECT_ONLY, int(connect_only))
        # Общий таймаут всего запроса (сек)
        acurl.setopt(CurlOpt.TIMEOUT, timeout)
        # Время ожидания ответа от сервера(сек)
        # acurl.setopt(CurlOpt.SERVER_RESPONSE_TIMEOUT, 5)  # noqa: ERA001
        # Таймаут установки TCP-соединения (сек)
        # acurl.setopt(CurlOpt.CONNECTTIMEOUT, 3)  # noqa: ERA001

        return AsyncSession(async_curl=acurl, headers=headers)

    async def probe(self, url: str) -> tuple[bool, float, int]:
        """Return (ok, elapsed_s, status_code)."""
        start = time.perf_counter()
        try:
            resp = await self._session.get(
                url,
                impersonate="chrome",
                allow_redirects=False,
            )
            elapsed = time.perf_counter() - start
            return (200 <= resp.status_code < 400, elapsed, resp.status_code)  # noqa: TRY300
        except (curl_exceptions.RequestException, OSError):
            elapsed = time.perf_counter() - start
            return (False, elapsed, 0)


class OutboundPoolManager:
    def __init__(
        self,
        servers: list["Server"],
        xray: XrayApi,
        chunk_size: int = 10,
        pool_size: int = settings.XRAY_POOL_SIZE,
        delay_between_chunks: float = 0.5,
    ):
        self.xray = xray
        self.servers_queue = deque(servers)
        self.pool_size = pool_size
        self.chunk_size = chunk_size
        self.delay = delay_between_chunks
        self.active_outbounds = set()

    async def fill_pool(self) -> None:
        while self.servers_queue and len(self.active_outbounds) < self.pool_size:
            to_add = []
            while (
                self.servers_queue
                and len(to_add) < self.chunk_size
                and len(self.active_outbounds) < self.pool_size
            ):
                server = self.servers_queue.popleft()
                tag = f"out_{hash(server)}"
                self.xray.add_outbound(server, tag)
                self.active_outbounds.add(tag)
                to_add.append(tag)
            await asyncio.sleep(self.delay)

    async def replace_outbound(self, old_tag: str) -> str | None:
        self.xray.remove_outbound(old_tag)
        self.active_outbounds.remove(old_tag)
        if self.servers_queue:
            server = self.servers_queue.popleft()
            new_tag = f"out_{hash(server)}"
            self.xray.add_outbound(server, new_tag)
            self.active_outbounds.add(new_tag)
            return new_tag
        return None


# ---------------- Главный тестер ----------------
class OutboundTester:
    def __init__(
        self,
        xray: XrayApi,
        inbound_tags: list[str],
        test_url: str = "http://127.0.0.1:{port}",
    ):
        self.xray = xray
        self.inbound_tags = inbound_tags
        self.prober = CurlCFFIProber()
        self.test_url_template = test_url

    async def test_outbound(
        self,
        inbound_tag: str,
        outbound_tag: str,
        port: int,
    ) -> tuple[bool, float, int]:
        # Переназначаем inbound на outbound
        rule_tag = f"{inbound_tag}_rule"
        self.xray.add_routing_rule(inbound_tag, outbound_tag, rule_tag)
        await asyncio.sleep(0.05)
        # Проверяем
        url = self.test_url_template.format(port=port)
        ok, elapsed, code = await self.prober.probe(url)

        # Удаляем правило, чтобы inbound был свободен
        self.xray.remove_routing_rule(rule_tag)

        return ok, elapsed, code


# ---------------- Инициализация пула inbound ----------------
def init_inbound_pool(
    xray: XrayApi,
    start_port: int = settings.XRAY_START_INBOUND_PORT,
    count: int = settings.XRAY_POOL_SIZE,
) -> tuple[list[str], list[int]]:
    for i in range(count):
        tag = f"socks_in_{i}"
        port = start_port + i
        xray.add_inbound_socks(
            port=port,
            tag=tag,
        )
    return [f"socks_in_{i}" for i in range(count)], list(
        range(start_port, start_port + count),
    )


# ---------------- Пример запуска ----------------
async def execute_test(servers: list["Server"]):
    xray = XrayApi("127.0.0.1:10085")
    inbound_tags, inbound_ports = init_inbound_pool(
        xray,
        start_port=settings.XRAY_START_INBOUND_PORT,
        count=settings.XRAY_POOL_SIZE,
    )

    pool = OutboundPoolManager(
        servers,
        xray,
        pool_size=settings.XRAY_POOL_SIZE,
        chunk_size=10,
        delay_between_chunks=0.5,
    )
    await pool.fill_pool()

    tester = OutboundTester(xray, inbound_tags)

    inbound_cycle = zip(inbound_tags, inbound_ports)
    while pool.active_outbounds:
        for inbound_tag, port in inbound_cycle:
            if not pool.active_outbounds:
                break
            outbound_tag = pool.active_outbounds.pop()
            ok, elapsed, code = await tester.test_outbound(
                inbound_tag,
                outbound_tag,
                port,
            )
            print(
                f"{outbound_tag} — {'OK' if ok else 'FAIL'} — {elapsed * 1000:.1f} ms — {code}",
            )
            await pool.replace_outbound(outbound_tag)


# if __name__ == "__main__":
#     asyncio.run(execute_test())
