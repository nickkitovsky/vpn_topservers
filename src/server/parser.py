import logging
from collections.abc import Callable
from urllib.parse import ParseResult, urlparse

from src.server import exceptions as exc
from src.server.exceptions import UrlParseError
from src.server.protocols import vless
from src.server.schema import Server

logger = logging.getLogger(__name__)

PROTOCOLS: dict[str, Callable[[ParseResult, str], Server]] = {
    "vless": vless.parse_url,
}


def parse_url(url: str, subscription_url: str = "") -> Server:
    logger.debug("Parsing server URL: %s", url)
    parsed = urlparse(url)
    try:
        server = PROTOCOLS[parsed.scheme](parsed, subscription_url)
    except exc.UnsupportedProtocolError:
        msg = f"Unsupported protocol in link: {url}"
        logger.error(msg)  # noqa: TRY400
        raise exc.UnsupportedProtocolError(msg)  # noqa: B904
    except UrlParseError:
        msg = f"Parsing error in link: {url}"
        logger.error(msg)  # noqa: TRY400
        raise UrlParseError(msg)  # noqa: B904

    else:
        logger.debug("Successfully parsed server: %s", server)
        return server
