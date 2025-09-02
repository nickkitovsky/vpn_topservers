from common.net import destination_pb2 as _destination_pb2
from app.router import config_pb2 as _config_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DomainMatchingType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Full: _ClassVar[DomainMatchingType]
    Subdomain: _ClassVar[DomainMatchingType]
    Keyword: _ClassVar[DomainMatchingType]
    Regex: _ClassVar[DomainMatchingType]

class QueryStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USE_IP: _ClassVar[QueryStrategy]
    USE_IP4: _ClassVar[QueryStrategy]
    USE_IP6: _ClassVar[QueryStrategy]
    USE_SYS: _ClassVar[QueryStrategy]
Full: DomainMatchingType
Subdomain: DomainMatchingType
Keyword: DomainMatchingType
Regex: DomainMatchingType
USE_IP: QueryStrategy
USE_IP4: QueryStrategy
USE_IP6: QueryStrategy
USE_SYS: QueryStrategy

class NameServer(_message.Message):
    __slots__ = ("address", "client_ip", "skipFallback", "prioritized_domain", "expected_geoip", "original_rules", "query_strategy", "actPrior", "tag", "timeoutMs", "disableCache", "finalQuery", "unexpected_geoip", "actUnprior")
    class PriorityDomain(_message.Message):
        __slots__ = ("type", "domain")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        DOMAIN_FIELD_NUMBER: _ClassVar[int]
        type: DomainMatchingType
        domain: str
        def __init__(self, type: _Optional[_Union[DomainMatchingType, str]] = ..., domain: _Optional[str] = ...) -> None: ...
    class OriginalRule(_message.Message):
        __slots__ = ("rule", "size")
        RULE_FIELD_NUMBER: _ClassVar[int]
        SIZE_FIELD_NUMBER: _ClassVar[int]
        rule: str
        size: int
        def __init__(self, rule: _Optional[str] = ..., size: _Optional[int] = ...) -> None: ...
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_IP_FIELD_NUMBER: _ClassVar[int]
    SKIPFALLBACK_FIELD_NUMBER: _ClassVar[int]
    PRIORITIZED_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_GEOIP_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_RULES_FIELD_NUMBER: _ClassVar[int]
    QUERY_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    ACTPRIOR_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    TIMEOUTMS_FIELD_NUMBER: _ClassVar[int]
    DISABLECACHE_FIELD_NUMBER: _ClassVar[int]
    FINALQUERY_FIELD_NUMBER: _ClassVar[int]
    UNEXPECTED_GEOIP_FIELD_NUMBER: _ClassVar[int]
    ACTUNPRIOR_FIELD_NUMBER: _ClassVar[int]
    address: _destination_pb2.Endpoint
    client_ip: bytes
    skipFallback: bool
    prioritized_domain: _containers.RepeatedCompositeFieldContainer[NameServer.PriorityDomain]
    expected_geoip: _containers.RepeatedCompositeFieldContainer[_config_pb2.GeoIP]
    original_rules: _containers.RepeatedCompositeFieldContainer[NameServer.OriginalRule]
    query_strategy: QueryStrategy
    actPrior: bool
    tag: str
    timeoutMs: int
    disableCache: bool
    finalQuery: bool
    unexpected_geoip: _containers.RepeatedCompositeFieldContainer[_config_pb2.GeoIP]
    actUnprior: bool
    def __init__(self, address: _Optional[_Union[_destination_pb2.Endpoint, _Mapping]] = ..., client_ip: _Optional[bytes] = ..., skipFallback: bool = ..., prioritized_domain: _Optional[_Iterable[_Union[NameServer.PriorityDomain, _Mapping]]] = ..., expected_geoip: _Optional[_Iterable[_Union[_config_pb2.GeoIP, _Mapping]]] = ..., original_rules: _Optional[_Iterable[_Union[NameServer.OriginalRule, _Mapping]]] = ..., query_strategy: _Optional[_Union[QueryStrategy, str]] = ..., actPrior: bool = ..., tag: _Optional[str] = ..., timeoutMs: _Optional[int] = ..., disableCache: bool = ..., finalQuery: bool = ..., unexpected_geoip: _Optional[_Iterable[_Union[_config_pb2.GeoIP, _Mapping]]] = ..., actUnprior: bool = ...) -> None: ...

class Config(_message.Message):
    __slots__ = ("name_server", "client_ip", "static_hosts", "tag", "disableCache", "query_strategy", "disableFallback", "disableFallbackIfMatch")
    class HostMapping(_message.Message):
        __slots__ = ("type", "domain", "ip", "proxied_domain")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        DOMAIN_FIELD_NUMBER: _ClassVar[int]
        IP_FIELD_NUMBER: _ClassVar[int]
        PROXIED_DOMAIN_FIELD_NUMBER: _ClassVar[int]
        type: DomainMatchingType
        domain: str
        ip: _containers.RepeatedScalarFieldContainer[bytes]
        proxied_domain: str
        def __init__(self, type: _Optional[_Union[DomainMatchingType, str]] = ..., domain: _Optional[str] = ..., ip: _Optional[_Iterable[bytes]] = ..., proxied_domain: _Optional[str] = ...) -> None: ...
    NAME_SERVER_FIELD_NUMBER: _ClassVar[int]
    CLIENT_IP_FIELD_NUMBER: _ClassVar[int]
    STATIC_HOSTS_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    DISABLECACHE_FIELD_NUMBER: _ClassVar[int]
    QUERY_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    DISABLEFALLBACK_FIELD_NUMBER: _ClassVar[int]
    DISABLEFALLBACKIFMATCH_FIELD_NUMBER: _ClassVar[int]
    name_server: _containers.RepeatedCompositeFieldContainer[NameServer]
    client_ip: bytes
    static_hosts: _containers.RepeatedCompositeFieldContainer[Config.HostMapping]
    tag: str
    disableCache: bool
    query_strategy: QueryStrategy
    disableFallback: bool
    disableFallbackIfMatch: bool
    def __init__(self, name_server: _Optional[_Iterable[_Union[NameServer, _Mapping]]] = ..., client_ip: _Optional[bytes] = ..., static_hosts: _Optional[_Iterable[_Union[Config.HostMapping, _Mapping]]] = ..., tag: _Optional[str] = ..., disableCache: bool = ..., query_strategy: _Optional[_Union[QueryStrategy, str]] = ..., disableFallback: bool = ..., disableFallbackIfMatch: bool = ...) -> None: ...
