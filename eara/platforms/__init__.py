"""Platform boundaries used by the portable EarA session.

Linux implementations are imported lazily so an injected non-Linux backend can
load the protocol/session without importing BlueZ or PulseAudio helpers.
"""

import sys
from eara.platforms.base import AudioBackend, BluetoothTransport, HostAudioState, PlatformServices, UnavailableAudioBackend


def default_backends() -> tuple[BluetoothTransport, AudioBackend]:
    if not sys.platform.startswith("linux"):
        raise RuntimeError(f"No default EarA adapters for {sys.platform}; supply platform adapters explicitly")
    from eara.platforms.linux import LinuxAudioBackend, LinuxBluetoothTransport

    return LinuxBluetoothTransport(), LinuxAudioBackend()


def resolve_backends(
    transport: BluetoothTransport | None = None,
    audio_backend: AudioBackend | None = None,
) -> tuple[BluetoothTransport, AudioBackend]:
    if transport is None:
        transport, default_audio = default_backends()
        if audio_backend is None:
            audio_backend = default_audio
    elif audio_backend is None:
        # Injected transports must not silently acquire Linux audio dependencies.
        audio_backend = UnavailableAudioBackend()
    return transport, audio_backend


def default_services() -> PlatformServices:
    if not sys.platform.startswith("linux"):
        raise RuntimeError(f"No default EarA platform services for {sys.platform}")
    from eara.platforms.linux_services import LinuxPlatformServices
    return LinuxPlatformServices()

__all__ = [
    "AudioBackend",
    "BluetoothTransport",
    "HostAudioState",
    "default_backends",
    "resolve_backends",
    "UnavailableAudioBackend",
    "default_services",
]
