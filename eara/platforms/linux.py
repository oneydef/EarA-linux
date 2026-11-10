"""Linux platform adapters backed by BlueZ and PulseAudio/PipeWire."""

from __future__ import annotations

from eara import audio, bluez
from eara.diagnostics import timed
from eara.platforms.base import AudioResult, ByteChannel, DiscoveredDevice, HostAudioState


class LinuxBluetoothTransport:
    def discover(self, preferred: str = "") -> DiscoveredDevice | None:
        device = bluez.find_nothing_device(preferred)
        if device is None:
            return None
        return {"address": device["address"], "name": device["name"]}

    def is_connected(self, address: str) -> bool:
        return bluez.is_connected(address)

    def has_audio_sink(self, address: str) -> bool:
        return bluez.has_audio_sink(address)

    @timed("linux.bluetooth_connect")
    def connect(
        self,
        address: str,
        *,
        timeout: float,
        scan: bool,
        max_rounds: int,
    ) -> None:
        bluez.trust_and_connect(
            address,
            timeout=timeout,
            scan=scan,
            max_rounds=max_rounds,
        )

    def abort_connection(self, address: str) -> None:
        bluez.dbus_disconnect(address)

    def disconnect(self, address: str) -> None:
        bluez.disconnect(address)

    def reset(self, address: str) -> None:
        bluez.reset_link(address)

    def power_off(self) -> None:
        bluez.power_off()

    @timed("linux.rfcomm_open")
    def open_channel(self, address: str) -> ByteChannel:
        return bluez.open_rfcomm(address)

    def permission_hint(self, error: OSError) -> str:
        return bluez.permission_hint(error)


class LinuxAudioBackend:
    supports_routing = True

    @timed("linux.audio_music")
    def ensure_music(self, address: str) -> AudioResult:
        return audio.ensure_music_audio(address)

    @timed("linux.audio_calls")
    def ensure_calls(self, address: str) -> AudioResult:
        return audio.ensure_call_audio(address)

    @timed("linux.audio_hfp")
    def ensure_hfp(self, address: str) -> AudioResult:
        return audio.ensure_hfp_audio(address)

    def reload(self) -> None:
        audio.reload_bluetooth_modules(force=True)

    @timed("linux.audio_read")
    def state(self, address: str) -> HostAudioState:
        return HostAudioState(
            sink=audio.find_sink(address),
            source=audio.find_source(address),
            profile=audio.active_profile(address),
            codec=audio.active_codec(address),
            codecs=audio.list_a2dp_codecs(address),
        )

    def set_codec(self, address: str, name: str) -> AudioResult:
        return audio.set_host_codec(address, name)
