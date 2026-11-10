"""Small platform contracts for Bluetooth control and host audio.

The earbud wire protocol and session only depend on these contracts.  Linux,
macOS, tests, and future platforms can supply their own implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, TypedDict


class _DeviceIdentity(TypedDict):
    address: str
    name: str


class DiscoveredDevice(_DeviceIdentity, total=False):
    paired: bool
    compatible: bool
    rssi: int


class ServiceHealth(TypedDict):
    bluetooth: bool | None
    audio: bool | None


class PlatformServices(Protocol):
    """Host discovery and health; None means unknown, never ready."""

    def inspect_services(self) -> ServiceHealth: ...

    def paired_devices(self) -> list[DiscoveredDevice]: ...

    def scan_devices(self, duration: float, progress: Callable[[int], None] | None = None) -> list[DiscoveredDevice]: ...

    def is_compatible_name(self, name: str) -> bool: ...

    def is_paired(self, address: str) -> bool: ...

    def pair(self, address: str) -> None: ...

    def power_off(self) -> None: ...

    def device_details(self, address: str) -> list[str]: ...

    def audio_diagnostics(self) -> list[DiagnosticSection]: ...

    def recovery_hint(self) -> str: ...


@dataclass(frozen=True)
class DiagnosticSection:
    label: str
    text: str
    ok: bool


class _AudioResultFields(TypedDict, total=False):
    error: str
    profile: str
    sink: str | None
    source: str | None
    codec: str
    hint: str
    device_codec_error: str
    available: list[dict[str, str]]


class AudioResult(_AudioResultFields):
    ok: bool


class ByteChannel(Protocol):
    """Bidirectional byte channel used by the RFCOMM protocol."""

    def sendall(self, data: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def settimeout(self, timeout: float) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class HostAudioState:
    """Platform-neutral description of the host audio route."""

    sink: str | None = None
    source: str | None = None
    profile: str = ""
    codec: str = ""
    codecs: list[dict[str, str]] = field(default_factory=list)
    available: bool = True
    error: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "sink": self.sink,
            "source": self.source,
            "profile": self.profile,
            "codec": self.codec,
            "codecs": [dict(codec) for codec in self.codecs],
            "available": self.available,
            "error": self.error,
        }


class BluetoothTransport(Protocol):
    """Discovery, connection, and byte transport for earbud control."""

    def discover(self, preferred: str = "") -> DiscoveredDevice | None: ...

    def is_connected(self, address: str) -> bool: ...

    def has_audio_sink(self, address: str) -> bool: ...

    def connect(
        self,
        address: str,
        *,
        timeout: float,
        scan: bool,
        max_rounds: int,
    ) -> None: ...

    def abort_connection(self, address: str) -> None: ...

    def disconnect(self, address: str) -> None: ...

    def reset(self, address: str) -> None: ...

    def power_off(self) -> None: ...

    def open_channel(self, address: str) -> ByteChannel: ...

    def permission_hint(self, error: OSError) -> str: ...


class AudioBackend(Protocol):
    """Host-side audio profiles and routing, separate from earbud control."""

    supports_routing: bool

    def ensure_music(self, address: str) -> AudioResult: ...

    def ensure_calls(self, address: str) -> AudioResult: ...

    def ensure_hfp(self, address: str) -> AudioResult: ...

    def reload(self) -> None: ...

    def state(self, address: str) -> HostAudioState: ...

    def set_codec(self, address: str, name: str) -> AudioResult: ...


class UnavailableAudioBackend:
    """Control-only adapter: no host audio commands or platform imports."""

    supports_routing = False

    def state(self, address: str) -> HostAudioState:
        return HostAudioState(available=False, error="Host audio adapter is not configured")

    def ensure_music(self, address: str) -> AudioResult:
        return {"ok": False, "error": "Host audio adapter is not configured"}

    ensure_calls = ensure_music
    ensure_hfp = ensure_music

    def set_codec(self, address: str, name: str) -> AudioResult:
        return self.ensure_music(address)

    def reload(self) -> None:
        pass
