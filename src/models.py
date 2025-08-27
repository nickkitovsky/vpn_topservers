from dataclasses import dataclass, field


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
