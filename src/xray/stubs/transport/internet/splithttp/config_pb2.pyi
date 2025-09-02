from transport.internet import config_pb2 as _config_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RangeConfig(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: int
    def __init__(self, to: _Optional[int] = ..., **kwargs) -> None: ...

class XmuxConfig(_message.Message):
    __slots__ = ("maxConcurrency", "maxConnections", "cMaxReuseTimes", "hMaxRequestTimes", "hMaxReusableSecs", "hKeepAlivePeriod")
    MAXCONCURRENCY_FIELD_NUMBER: _ClassVar[int]
    MAXCONNECTIONS_FIELD_NUMBER: _ClassVar[int]
    CMAXREUSETIMES_FIELD_NUMBER: _ClassVar[int]
    HMAXREQUESTTIMES_FIELD_NUMBER: _ClassVar[int]
    HMAXREUSABLESECS_FIELD_NUMBER: _ClassVar[int]
    HKEEPALIVEPERIOD_FIELD_NUMBER: _ClassVar[int]
    maxConcurrency: RangeConfig
    maxConnections: RangeConfig
    cMaxReuseTimes: RangeConfig
    hMaxRequestTimes: RangeConfig
    hMaxReusableSecs: RangeConfig
    hKeepAlivePeriod: int
    def __init__(self, maxConcurrency: _Optional[_Union[RangeConfig, _Mapping]] = ..., maxConnections: _Optional[_Union[RangeConfig, _Mapping]] = ..., cMaxReuseTimes: _Optional[_Union[RangeConfig, _Mapping]] = ..., hMaxRequestTimes: _Optional[_Union[RangeConfig, _Mapping]] = ..., hMaxReusableSecs: _Optional[_Union[RangeConfig, _Mapping]] = ..., hKeepAlivePeriod: _Optional[int] = ...) -> None: ...

class Config(_message.Message):
    __slots__ = ("host", "path", "mode", "headers", "xPaddingBytes", "noGRPCHeader", "noSSEHeader", "scMaxEachPostBytes", "scMinPostsIntervalMs", "scMaxBufferedPosts", "scStreamUpServerSecs", "xmux", "downloadSettings")
    class HeadersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    HOST_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    XPADDINGBYTES_FIELD_NUMBER: _ClassVar[int]
    NOGRPCHEADER_FIELD_NUMBER: _ClassVar[int]
    NOSSEHEADER_FIELD_NUMBER: _ClassVar[int]
    SCMAXEACHPOSTBYTES_FIELD_NUMBER: _ClassVar[int]
    SCMINPOSTSINTERVALMS_FIELD_NUMBER: _ClassVar[int]
    SCMAXBUFFEREDPOSTS_FIELD_NUMBER: _ClassVar[int]
    SCSTREAMUPSERVERSECS_FIELD_NUMBER: _ClassVar[int]
    XMUX_FIELD_NUMBER: _ClassVar[int]
    DOWNLOADSETTINGS_FIELD_NUMBER: _ClassVar[int]
    host: str
    path: str
    mode: str
    headers: _containers.ScalarMap[str, str]
    xPaddingBytes: RangeConfig
    noGRPCHeader: bool
    noSSEHeader: bool
    scMaxEachPostBytes: RangeConfig
    scMinPostsIntervalMs: RangeConfig
    scMaxBufferedPosts: int
    scStreamUpServerSecs: RangeConfig
    xmux: XmuxConfig
    downloadSettings: _config_pb2.StreamConfig
    def __init__(self, host: _Optional[str] = ..., path: _Optional[str] = ..., mode: _Optional[str] = ..., headers: _Optional[_Mapping[str, str]] = ..., xPaddingBytes: _Optional[_Union[RangeConfig, _Mapping]] = ..., noGRPCHeader: bool = ..., noSSEHeader: bool = ..., scMaxEachPostBytes: _Optional[_Union[RangeConfig, _Mapping]] = ..., scMinPostsIntervalMs: _Optional[_Union[RangeConfig, _Mapping]] = ..., scMaxBufferedPosts: _Optional[int] = ..., scStreamUpServerSecs: _Optional[_Union[RangeConfig, _Mapping]] = ..., xmux: _Optional[_Union[XmuxConfig, _Mapping]] = ..., downloadSettings: _Optional[_Union[_config_pb2.StreamConfig, _Mapping]] = ...) -> None: ...
