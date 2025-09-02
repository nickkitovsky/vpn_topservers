from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PeerConfig(_message.Message):
    __slots__ = ("public_key", "pre_shared_key", "endpoint", "keep_alive", "allowed_ips")
    PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    PRE_SHARED_KEY_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    KEEP_ALIVE_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_IPS_FIELD_NUMBER: _ClassVar[int]
    public_key: str
    pre_shared_key: str
    endpoint: str
    keep_alive: int
    allowed_ips: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, public_key: _Optional[str] = ..., pre_shared_key: _Optional[str] = ..., endpoint: _Optional[str] = ..., keep_alive: _Optional[int] = ..., allowed_ips: _Optional[_Iterable[str]] = ...) -> None: ...

class DeviceConfig(_message.Message):
    __slots__ = ("secret_key", "endpoint", "peers", "mtu", "num_workers", "reserved", "domain_strategy", "is_client", "no_kernel_tun")
    class DomainStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FORCE_IP: _ClassVar[DeviceConfig.DomainStrategy]
        FORCE_IP4: _ClassVar[DeviceConfig.DomainStrategy]
        FORCE_IP6: _ClassVar[DeviceConfig.DomainStrategy]
        FORCE_IP46: _ClassVar[DeviceConfig.DomainStrategy]
        FORCE_IP64: _ClassVar[DeviceConfig.DomainStrategy]
    FORCE_IP: DeviceConfig.DomainStrategy
    FORCE_IP4: DeviceConfig.DomainStrategy
    FORCE_IP6: DeviceConfig.DomainStrategy
    FORCE_IP46: DeviceConfig.DomainStrategy
    FORCE_IP64: DeviceConfig.DomainStrategy
    SECRET_KEY_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    PEERS_FIELD_NUMBER: _ClassVar[int]
    MTU_FIELD_NUMBER: _ClassVar[int]
    NUM_WORKERS_FIELD_NUMBER: _ClassVar[int]
    RESERVED_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    IS_CLIENT_FIELD_NUMBER: _ClassVar[int]
    NO_KERNEL_TUN_FIELD_NUMBER: _ClassVar[int]
    secret_key: str
    endpoint: _containers.RepeatedScalarFieldContainer[str]
    peers: _containers.RepeatedCompositeFieldContainer[PeerConfig]
    mtu: int
    num_workers: int
    reserved: bytes
    domain_strategy: DeviceConfig.DomainStrategy
    is_client: bool
    no_kernel_tun: bool
    def __init__(self, secret_key: _Optional[str] = ..., endpoint: _Optional[_Iterable[str]] = ..., peers: _Optional[_Iterable[_Union[PeerConfig, _Mapping]]] = ..., mtu: _Optional[int] = ..., num_workers: _Optional[int] = ..., reserved: _Optional[bytes] = ..., domain_strategy: _Optional[_Union[DeviceConfig.DomainStrategy, str]] = ..., is_client: bool = ..., no_kernel_tun: bool = ...) -> None: ...
