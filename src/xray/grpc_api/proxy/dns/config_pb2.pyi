from common.net import destination_pb2 as _destination_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Config(_message.Message):
    __slots__ = ("server", "user_level", "non_IP_query", "block_types")
    SERVER_FIELD_NUMBER: _ClassVar[int]
    USER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    NON_IP_QUERY_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TYPES_FIELD_NUMBER: _ClassVar[int]
    server: _destination_pb2.Endpoint
    user_level: int
    non_IP_query: str
    block_types: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, server: _Optional[_Union[_destination_pb2.Endpoint, _Mapping]] = ..., user_level: _Optional[int] = ..., non_IP_query: _Optional[str] = ..., block_types: _Optional[_Iterable[int]] = ...) -> None: ...
