class ServerError(Exception):
    pass


class UrlParseError(ServerError):
    pass


class UnsupportedProtocolError(ServerError):
    pass
