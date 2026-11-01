import errno
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from eara import bluez


class BluezTests(unittest.TestCase):
    SDP_CHANNEL_16 = """
    <record>
      <attribute id="0x0001"><sequence>
        <uuid value="aeac4a03-dff5-498f-843a-34487cf133eb" />
      </sequence></attribute>
      <attribute id="0x0004"><sequence><sequence>
        <uuid value="0x0003" /><uint8 value="0x10" />
      </sequence></sequence></attribute>
    </record>
    """

    def test_find_nothing_rejects_unpaired_mac(self):
        with patch.object(bluez, "paired_devices", return_value=[]):
            self.assertIsNone(bluez.find_nothing_device("AA:BB:CC:DD:EE:FF"))

    def test_find_nothing_accepts_paired_mac(self):
        paired = [{"address": "AA:BB:CC:DD:EE:FF", "name": "Nothing Ear (a)"}]
        with patch.object(bluez, "paired_devices", return_value=paired):
            found = bluez.find_nothing_device("AA:BB:CC:DD:EE:FF")
        self.assertIsNotNone(found)
        self.assertEqual(found["address"], "AA:BB:CC:DD:EE:FF")

    def test_scan_for_device_exits_early_when_connected(self):
        with (
            patch.object(bluez, "start_discovery") as start,
            patch.object(bluez, "stop_discovery") as stop,
            patch.object(bluez, "is_connected", return_value=True),
            patch.object(bluez, "device_properties", return_value={}),
            patch.object(bluez, "_ctl", return_value="") as ctl,
            patch.object(bluez.time, "sleep") as sleep,
        ):
            self.assertTrue(bluez.scan_for_device("AA:BB:CC:DD:EE:FF", dwell=6.0))
        start.assert_called_once()
        stop.assert_called_once()
        sleep.assert_not_called()
        ctl.assert_not_called()

    def test_scan_for_device_keeps_window_until_advertisement(self):
        # Absent buds (no RSSI) keep the dwell running; discovery must stay on.
        props = [{"Connected": False, "RSSI": None}, {"Connected": False, "RSSI": -60}]
        with (
            patch.object(bluez, "start_discovery"),
            patch.object(bluez, "stop_discovery") as stop,
            patch.object(bluez, "is_connected", return_value=False),
            patch.object(bluez, "device_properties", side_effect=props),
            patch.object(bluez, "_ctl", return_value="") as ctl,
            patch.object(bluez.time, "sleep") as sleep,
        ):
            self.assertTrue(bluez.scan_for_device("AA:BB:CC:DD:EE:FF", dwell=6.0))
        sleep.assert_called_once_with(0.8)
        stop.assert_called_once()
        ctl.assert_not_called()

    def test_trust_and_connect_auto_pairs_unpaired_device(self):
        with (
            patch.object(bluez, "power_on"),
            patch.object(bluez, "_is_paired", return_value=False),
            patch.object(bluez, "pair_device") as pair,
            patch.object(bluez, "_ctl", return_value=""),
            patch.object(bluez, "is_connected", return_value=True),
            patch.object(bluez, "has_audio_sink", return_value=True),
        ):
            bluez.trust_and_connect("AA:BB:CC:DD:EE:FF", scan=False)
        pair.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    def test_trust_and_connect_surfaces_invisible_device(self):
        # Unpaired and not visible (device_properties is None without D-Bus):
        # pair_device raises and the error must reach the caller.
        with (
            patch.object(bluez, "power_on"),
            patch.object(bluez, "_is_paired", return_value=False),
            patch.object(bluez, "_ctl", return_value=""),
            patch.object(bluez, "is_connected", return_value=False),
        ):
            with self.assertRaises(RuntimeError):
                bluez.trust_and_connect("AA:BB:CC:DD:EE:FF", timeout=1, scan=False, max_rounds=1)

    def test_power_off_skips_when_already_off(self):
        with patch.object(bluez, "_ctl", return_value="Powered: no") as ctl:
            bluez.power_off()
        ctl.assert_called_once_with("show")

    def test_power_off_when_on(self):
        with patch.object(bluez, "_ctl", side_effect=["Powered: yes", ""]):
            bluez.power_off()

    def test_parses_ntapp_rfcomm_channel_from_sdp(self):
        self.assertEqual(bluez._rfcomm_channel_from_sdp(self.SDP_CHANNEL_16), 16)

    def test_ignores_channel_from_unrelated_sdp_record(self):
        xml = self.SDP_CHANNEL_16.replace(
            "aeac4a03-dff5-498f-843a-34487cf133eb",
            "0000110b-0000-1000-8000-00805f9b34fb",
        )
        self.assertIsNone(bluez._rfcomm_channel_from_sdp(xml))

    def test_rfcomm_channel_falls_back_to_15(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()
        result = SimpleNamespace(stdout="<record></record>", stderr="", returncode=0)
        with patch.object(bluez.subprocess, "run", return_value=result):
            self.assertEqual(bluez.discover_rfcomm_channel("AA:BB:CC:DD:EE:FF"), 15)

    def test_rfcomm_channel_uses_sdp_channel_16(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()
        result = SimpleNamespace(stdout=self.SDP_CHANNEL_16, stderr="", returncode=0)
        with patch.object(bluez.subprocess, "run", return_value=result):
            self.assertEqual(bluez.discover_rfcomm_channel("AA:BB:CC:DD:EE:FF"), 16)

    def test_open_rfcomm_retries_connection_already_in_progress(self):
        first = MagicMock()
        first.connect.side_effect = OSError(errno.EALREADY, "Operation already in progress")
        second = MagicMock()
        with (
            patch.object(bluez, "discover_rfcomm_channel", return_value=15),
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", side_effect=[first, second]),
            patch.object(bluez.time, "sleep"),
        ):
            result = bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertIs(result, second)
        first.close.assert_called_once()
        second.connect.assert_called_once_with(("AA:BB:CC:DD:EE:FF", 15))


if __name__ == "__main__":
    unittest.main()
