from common.net import address_pb2 as _address_pb2
from common.net import network_pb2 as _network_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Config(_message.Message):
    __slots__ = ("address", "port", "networks", "follow_redirect", "user_level")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    NETWORKS_FIELD_NUMBER: _ClassVar[int]
    FOLLOW_REDIRECT_FIELD_NUMBER: _ClassVar[int]
    USER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    address: _address_pb2.IPOrDomain
    port: int
    networks: _containers.RepeatedScalarFieldContainer[_network_pb2.Network]
    follow_redirect: bool
    user_level: int
    def __init__(self, address: _Optional[_Union[_address_pb2.IPOrDomain, _Mapping]] = ..., port: _Optional[int] = ..., networks: _Optional[_Iterable[_Union[_network_pb2.Network, str]]] = ..., follow_redirect: bool = ..., user_level: _Optional[int] = ...) -> None: ...
