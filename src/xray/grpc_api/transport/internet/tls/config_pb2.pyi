from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Certificate(_message.Message):
    __slots__ = ("certificate", "key", "usage", "ocsp_stapling", "certificate_path", "key_path", "One_time_loading", "build_chain")
    class Usage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ENCIPHERMENT: _ClassVar[Certificate.Usage]
        AUTHORITY_VERIFY: _ClassVar[Certificate.Usage]
        AUTHORITY_ISSUE: _ClassVar[Certificate.Usage]
    ENCIPHERMENT: Certificate.Usage
    AUTHORITY_VERIFY: Certificate.Usage
    AUTHORITY_ISSUE: Certificate.Usage
    CERTIFICATE_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    OCSP_STAPLING_FIELD_NUMBER: _ClassVar[int]
    CERTIFICATE_PATH_FIELD_NUMBER: _ClassVar[int]
    KEY_PATH_FIELD_NUMBER: _ClassVar[int]
    ONE_TIME_LOADING_FIELD_NUMBER: _ClassVar[int]
    BUILD_CHAIN_FIELD_NUMBER: _ClassVar[int]
    certificate: bytes
    key: bytes
    usage: Certificate.Usage
    ocsp_stapling: int
    certificate_path: str
    key_path: str
    One_time_loading: bool
    build_chain: bool
    def __init__(self, certificate: _Optional[bytes] = ..., key: _Optional[bytes] = ..., usage: _Optional[_Union[Certificate.Usage, str]] = ..., ocsp_stapling: _Optional[int] = ..., certificate_path: _Optional[str] = ..., key_path: _Optional[str] = ..., One_time_loading: bool = ..., build_chain: bool = ...) -> None: ...

class Config(_message.Message):
    __slots__ = ("allow_insecure", "certificate", "server_name", "next_protocol", "enable_session_resumption", "disable_system_root", "min_version", "max_version", "cipher_suites", "fingerprint", "reject_unknown_sni", "pinned_peer_certificate_chain_sha256", "pinned_peer_certificate_public_key_sha256", "master_key_log", "curve_preferences", "verify_peer_cert_in_names")
    ALLOW_INSECURE_FIELD_NUMBER: _ClassVar[int]
    CERTIFICATE_FIELD_NUMBER: _ClassVar[int]
    SERVER_NAME_FIELD_NUMBER: _ClassVar[int]
    NEXT_PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    ENABLE_SESSION_RESUMPTION_FIELD_NUMBER: _ClassVar[int]
    DISABLE_SYSTEM_ROOT_FIELD_NUMBER: _ClassVar[int]
    MIN_VERSION_FIELD_NUMBER: _ClassVar[int]
    MAX_VERSION_FIELD_NUMBER: _ClassVar[int]
    CIPHER_SUITES_FIELD_NUMBER: _ClassVar[int]
    FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    REJECT_UNKNOWN_SNI_FIELD_NUMBER: _ClassVar[int]
    PINNED_PEER_CERTIFICATE_CHAIN_SHA256_FIELD_NUMBER: _ClassVar[int]
    PINNED_PEER_CERTIFICATE_PUBLIC_KEY_SHA256_FIELD_NUMBER: _ClassVar[int]
    MASTER_KEY_LOG_FIELD_NUMBER: _ClassVar[int]
    CURVE_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    VERIFY_PEER_CERT_IN_NAMES_FIELD_NUMBER: _ClassVar[int]
    allow_insecure: bool
    certificate: _containers.RepeatedCompositeFieldContainer[Certificate]
    server_name: str
    next_protocol: _containers.RepeatedScalarFieldContainer[str]
    enable_session_resumption: bool
    disable_system_root: bool
    min_version: str
    max_version: str
    cipher_suites: str
    fingerprint: str
    reject_unknown_sni: bool
    pinned_peer_certificate_chain_sha256: _containers.RepeatedScalarFieldContainer[bytes]
    pinned_peer_certificate_public_key_sha256: _containers.RepeatedScalarFieldContainer[bytes]
    master_key_log: str
    curve_preferences: _containers.RepeatedScalarFieldContainer[str]
    verify_peer_cert_in_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, allow_insecure: bool = ..., certificate: _Optional[_Iterable[_Union[Certificate, _Mapping]]] = ..., server_name: _Optional[str] = ..., next_protocol: _Optional[_Iterable[str]] = ..., enable_session_resumption: bool = ..., disable_system_root: bool = ..., min_version: _Optional[str] = ..., max_version: _Optional[str] = ..., cipher_suites: _Optional[str] = ..., fingerprint: _Optional[str] = ..., reject_unknown_sni: bool = ..., pinned_peer_certificate_chain_sha256: _Optional[_Iterable[bytes]] = ..., pinned_peer_certificate_public_key_sha256: _Optional[_Iterable[bytes]] = ..., master_key_log: _Optional[str] = ..., curve_preferences: _Optional[_Iterable[str]] = ..., verify_peer_cert_in_names: _Optional[_Iterable[str]] = ...) -> None: ...
