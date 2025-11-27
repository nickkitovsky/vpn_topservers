from ipaddress import ip_address
from typing import Any

from xray.stubs.common.net.address_pb2 import IPOrDomain
from xray.stubs.common.serial.typed_message_pb2 import TypedMessage


def to_typed_message(message: Any) -> "TypedMessage":  # noqa: ANN401
    return TypedMessage(
        type=message.DESCRIPTOR.full_name,
        value=message.SerializeToString(),
    )


def get_message_type(message: Any) -> str:  # noqa: ANN401
    return message.DESCRIPTOR.full_name


def parse_address(address: str) -> IPOrDomain:
    try:
        try:
            ip_address(address)
            return IPOrDomain(ip=bytes(map(int, address.split("."))))
        except ValueError:
            return IPOrDomain(domain=address)
    except Exception as e:
        msg = f"Invalid address format: {address}"
        raise ValueError(msg) from e
