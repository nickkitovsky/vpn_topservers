from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Config(_message.Message):
    __slots__ = ("tag", "listen")
    TAG_FIELD_NUMBER: _ClassVar[int]
    LISTEN_FIELD_NUMBER: _ClassVar[int]
    tag: str
    listen: str
    def __init__(self, tag: _Optional[str] = ..., listen: _Optional[str] = ...) -> None: ...
