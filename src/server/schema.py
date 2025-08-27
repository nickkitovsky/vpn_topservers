from dataclasses import dataclass, field


@dataclass
class Responses:
    connection: float = 999.0
    http: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ServerParams:
    pass


@dataclass(frozen=True, slots=True)
class Server:
    protocol: str
    address: str
    port: int
    username: str
    params: ServerParams = field(repr=False)
    raw_url: str = field(repr=False)
    response_time: Responses = field(default_factory=Responses, init=False)
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
