import unittest
from unittest.mock import MagicMock

from eara.platforms.base import HostAudioState
from eara.session import Device


class FakeTransport:
    def __init__(self, *, connected=False):
        self.connected = connected
        self.channel = MagicMock()
        self.calls = []

    def discover(self, preferred=""):
        self.calls.append(("discover", preferred))
        return {"address": "aa:bb:cc:dd:ee:ff", "name": "Nothing Ear (a)"}

    def is_connected(self, address):
        self.calls.append(("is_connected", address))
        return self.connected

    def has_audio_sink(self, address):
        return self.connected

    def connect(self, address, *, timeout, scan, max_rounds):
        self.calls.append(("connect", address, timeout, scan, max_rounds))
        self.connected = True

    def abort_connection(self, address):
        self.calls.append(("abort_connection", address))

    def disconnect(self, address):
        self.calls.append(("disconnect", address))
        self.connected = False

    def reset(self, address):
        self.calls.append(("reset", address))

    def power_off(self):
        self.calls.append(("power_off",))

    def open_channel(self, address):
        self.calls.append(("open_channel", address))
        return self.channel

    def permission_hint(self, error):
        return f"permission: {error}"


class FakeAudioBackend:
    supports_routing = True
    def __init__(self):
        self.calls = []

    def ensure_music(self, address):
        self.calls.append(("ensure_music", address))
        return {"ok": True, "profile": "a2dp"}

    def ensure_calls(self, address):
        self.calls.append(("ensure_calls", address))
        return {"ok": True, "profile": "a2dp"}

    def ensure_hfp(self, address):
        self.calls.append(("ensure_hfp", address))
        return {"ok": True, "profile": "headset_head_unit"}

    def reload(self):
        self.calls.append(("reload",))

    def state(self, address):
        self.calls.append(("state", address))
        return HostAudioState(
            sink="test-output",
            profile="a2dp",
            codec="aac",
            codecs=[{"key": "aac", "label": "AAC", "profile": "a2dp"}],
        )

    def set_codec(self, address, name):
        self.calls.append(("set_codec", address, name))
        return {"ok": True, "codec": name}


class PlatformBoundaryTests(unittest.TestCase):
    def test_discovery_and_status_use_injected_backends(self):
        transport = FakeTransport(connected=False)
        host_audio = FakeAudioBackend()

        device = Device.discover(
            "preferred",
            transport=transport,
            audio_backend=host_audio,
        )
        status = device.status()

        self.assertIs(device.transport, transport)
        self.assertIs(device.audio_backend, host_audio)
        self.assertEqual(device.address, "AA:BB:CC:DD:EE:FF")
        self.assertFalse(status["bt_connected"])
        self.assertEqual(status["audio"]["codec"], "aac")
        self.assertIn(("discover", "preferred"), transport.calls)
        self.assertIn(("state", "AA:BB:CC:DD:EE:FF"), host_audio.calls)

    def test_connect_and_shutdown_do_not_require_linux_modules(self):
        transport = FakeTransport(connected=True)
        host_audio = FakeAudioBackend()
        device = Device(
            "AA:BB:CC:DD:EE:FF",
            "Nothing Ear (a)",
            transport=transport,
            audio_backend=host_audio,
        )

        result = device.connect_audio()
        device.shutdown(power_off=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempt"], 0)
        self.assertIn(("ensure_music", device.address), host_audio.calls)
        self.assertIn(("disconnect", device.address), transport.calls)
        self.assertIn(("power_off",), transport.calls)

    def test_open_control_uses_injected_byte_channel(self):
        transport = FakeTransport(connected=True)
        host_audio = FakeAudioBackend()
        device = Device(
            "AA:BB:CC:DD:EE:FF",
            "Nothing Ear (a)",
            transport=transport,
            audio_backend=host_audio,
        )

        device.open_control()
        self.assertIs(device._sock, transport.channel)
        device.close_control()
        transport.channel.close.assert_called_once_with()

    def test_host_audio_routes_are_platform_operations(self):
        transport = FakeTransport(connected=True)
        host_audio = FakeAudioBackend()
        device = Device(
            "AA:BB:CC:DD:EE:FF",
            "Nothing Ear (a)",
            transport=transport,
            audio_backend=host_audio,
        )

        self.assertEqual(device.route_audio("calls")["profile"], "a2dp")
        self.assertEqual(device.route_audio("hfp")["profile"], "headset_head_unit")
        self.assertEqual(device.host_audio_state()["codec"], "aac")
        self.assertIn(("ensure_calls", device.address), host_audio.calls)
        self.assertIn(("ensure_hfp", device.address), host_audio.calls)


if __name__ == "__main__":
    unittest.main()
