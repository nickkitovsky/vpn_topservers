from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Config(_message.Message):
    __slots__ = ("subject_selector", "ping_config")
    SUBJECT_SELECTOR_FIELD_NUMBER: _ClassVar[int]
    PING_CONFIG_FIELD_NUMBER: _ClassVar[int]
    subject_selector: _containers.RepeatedScalarFieldContainer[str]
    ping_config: HealthPingConfig
    def __init__(self, subject_selector: _Optional[_Iterable[str]] = ..., ping_config: _Optional[_Union[HealthPingConfig, _Mapping]] = ...) -> None: ...

class HealthPingConfig(_message.Message):
    __slots__ = ("destination", "connectivity", "interval", "samplingCount", "timeout")
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    CONNECTIVITY_FIELD_NUMBER: _ClassVar[int]
    INTERVAL_FIELD_NUMBER: _ClassVar[int]
    SAMPLINGCOUNT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    destination: str
    connectivity: str
    interval: int
    samplingCount: int
    timeout: int
    def __init__(self, destination: _Optional[str] = ..., connectivity: _Optional[str] = ..., interval: _Optional[int] = ..., samplingCount: _Optional[int] = ..., timeout: _Optional[int] = ...) -> None: ...
