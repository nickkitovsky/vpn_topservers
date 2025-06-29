from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class VlessParams:
    sni: str = ""
    pbk: str = ""
    security: str = "none"
    type: str = "tcp"
    fp: str = ""
    path: str = "/"
    service_name: str = ""
    host: str = ""
    alpn: list[str] | None = None
    sid: str = ""
    flow: str = ""


@dataclass
class ResponseTime:
    connection: float = 999.0
    http: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Server:
    protocol: str
    address: str
    port: int
    username: str
    params: VlessParams = field(repr=False)
    raw_url: str = field(repr=False)
    response_time: ResponseTime = field(default_factory=ResponseTime, init=False)
    from_subscription: str = field(default="", repr=False)

    def __hash__(self) -> int:
        return hash(
            (
                self.address,
                self.port,
                self.username,
            ),
        )

    def __eq__(self, other: object) -> bool:
        return bool(
            isinstance(other, Server)
            and self.address == other.address
            and self.port == other.port
            and self.username == other.username,
        )


@dataclass
class Subscription:
    url: str
    servers: set[str] = field(default_factory=set, init=False)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        return bool(
            isinstance(other, Subscription) and self.url == other.url,
        )
