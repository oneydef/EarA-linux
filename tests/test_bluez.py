import errno
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from eara import bluez


class BluezTests(unittest.TestCase):
    def test_refused_control_channel_is_not_reported_as_sleeping(self):
        hint = bluez.permission_hint(OSError(errno.ECONNREFUSED, "Connection refused"))
        self.assertIn("control connection refused", hint)
        self.assertIn("unsupported or temporarily unavailable", hint)
        self.assertNotIn("asleep", hint)

    def test_unreachable_device_retains_wake_up_hint(self):
        self.assertIn("asleep", bluez.permission_hint(OSError(errno.EHOSTDOWN, "Host down")))

    def setUp(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()

    def tearDown(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()

    def test_power_failure_preserves_error_without_prescribing_service_restarts(self):
        with patch.object(bluez, '_ctl', side_effect=[
            'Powered: no', 'Failed to set power on: org.bluez.Error.Busy', 'Powered: no'
        ]):
            with self.assertRaisesRegex(RuntimeError, 'org.bluez.Error.Busy') as error:
                bluez.power_on()
        self.assertNotIn('systemctl restart', str(error.exception))
        self.assertIn('eara doctor', str(error.exception))

    def test_connect_timeout_stops_fallback_after_dbus_failure(self):
        now = [0.0]
        def fail():
            now[0] = 3.0
            raise OSError('connect failed')
        with patch.object(bluez.operations.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(bluez, 'power_on'), patch.object(bluez, '_is_paired', return_value=True), \
             patch.object(bluez, 'is_connected', return_value=False), \
             patch.object(bluez, '_ctl') as ctl, \
             patch.object(bluez, 'dbus_connect', side_effect=lambda address: fail()):
            with self.assertRaises(TimeoutError):
                bluez.trust_and_connect('AA', timeout=2, scan=False, max_rounds=1)
        ctl.assert_called_once_with('trust', 'AA')

    def test_trusted_property_is_sent_as_dbus_variant(self):
        try:
            import dbus
        except ImportError:
            self.skipTest('python3-dbus unavailable')
        device, properties = MagicMock(), MagicMock()
        properties.Get.return_value = False
        with patch.object(dbus, 'SystemBus'), \
             patch.object(dbus, 'Interface', side_effect=[device, properties]), \
             patch.object(bluez, '_device_path', return_value='/test/device'):
            bluez.dbus_connect('AA')
        value = properties.Set.call_args.args[2]
        self.assertEqual(value.variant_level, 1)
        self.assertTrue(value)
        device.Connect.assert_called_once()

    def test_pending_bluez_connect_waits_for_audio_without_cli_duplicate(self):
        for name in ('org.bluez.Error.InProgress', 'org.bluez.Error.AlreadyConnected'):
            with self.subTest(name=name):
                now = [0.0]
                error = RuntimeError(name)
                error.get_dbus_name = lambda: name
                def pause(seconds):
                    now[0] += seconds
                with patch.object(bluez.time, 'monotonic', side_effect=lambda: now[0]), \
                     patch.object(bluez.operations, 'pause', side_effect=pause), \
                     patch.object(bluez, 'power_on'), \
                     patch.object(bluez, '_is_paired', return_value=True), \
                     patch.object(bluez, 'is_connected', return_value=False), \
                     patch.object(bluez, 'has_audio_sink', side_effect=lambda address: now[0] >= 3), \
                     patch.object(bluez, '_ctl') as ctl, \
                     patch.object(bluez, 'dbus_connect', side_effect=error) as connect, \
                     patch.object(bluez, 'dbus_disconnect') as disconnect:
                    bluez.trust_and_connect('AA', timeout=28, scan=False, max_rounds=1)
                ctl.assert_called_once_with('trust', 'AA')
                connect.assert_called_once_with('AA')
                disconnect.assert_not_called()
                self.assertLess(now[0], 4)

    def test_pending_connect_without_audio_still_times_out(self):
        now = [0.0]
        error = RuntimeError('pending')
        error.get_dbus_name = lambda: 'org.bluez.Error.InProgress'
        def pause(seconds):
            now[0] += seconds
            bluez.operations.check()
        with patch.object(bluez.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(bluez.operations, 'pause', side_effect=pause), \
             patch.object(bluez, 'power_on'), \
             patch.object(bluez, '_is_paired', return_value=True), \
             patch.object(bluez, 'is_connected', return_value=False), \
             patch.object(bluez, 'has_audio_sink', return_value=False), \
             patch.object(bluez, '_ctl') as ctl, \
             patch.object(bluez, 'dbus_connect', side_effect=error):
            with self.assertRaises(TimeoutError):
                bluez.trust_and_connect('AA', timeout=2, scan=False, max_rounds=1)
        ctl.assert_called_once_with('trust', 'AA')
        self.assertLess(now[0], 2.5)

    def test_connected_control_link_requests_audio_without_disconnect(self):
        now = [0.0]
        def pause(seconds):
            now[0] += seconds
        with patch.object(bluez.operations.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(bluez.operations, 'pause', side_effect=pause), \
             patch.object(bluez, 'power_on'), patch.object(bluez, '_is_paired', return_value=True), \
             patch.object(bluez, '_ctl'), patch.object(bluez, 'is_connected', return_value=True), \
             patch.object(bluez, 'has_audio_sink', side_effect=lambda address: now[0] >= 3), \
             patch.object(bluez, 'dbus_connect') as connect, \
             patch.object(bluez, 'dbus_disconnect') as disconnect:
            bluez.trust_and_connect('AA', timeout=28, scan=False, max_rounds=1)
        connect.assert_called_once_with('AA')
        disconnect.assert_not_called()
        self.assertLess(now[0], 4)

    def test_dbus_connect_negotiates_profiles_on_existing_control_link(self):
        try:
            import dbus
        except ImportError:
            self.skipTest('python3-dbus unavailable')
        device, properties = MagicMock(), MagicMock()
        properties.Get.return_value = True
        with patch.object(dbus, 'SystemBus'), \
             patch.object(dbus, 'Interface', side_effect=[device, properties]), \
             patch.object(bluez, '_device_path', return_value='/test/device'):
            bluez.dbus_connect('AA')
        device.Connect.assert_called_once()
        device.ConnectProfile.assert_not_called()

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
            patch.object(bluez, "pair_device", side_effect=RuntimeError("Device is not visible")),
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
            patch.object(bluez.operations, "pause"),
        ):
            result = bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertIs(result, second)
        first.close.assert_called_once()
        second.connect.assert_called_once_with(("AA:BB:CC:DD:EE:FF", 15))

    def test_open_rfcomm_probes_alternate_channel_when_refused(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()
        refused = MagicMock()
        refused.connect.side_effect = OSError(errno.ECONNREFUSED, "Connection refused")
        accepted = MagicMock()
        with (
            patch.object(bluez, "discover_rfcomm_channel", return_value=15),
            patch.object(bluez.operations, "pause"),
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", side_effect=[refused, accepted]),
        ):
            result = bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertIs(result, accepted)
        refused.close.assert_called_once()
        accepted.connect.assert_called_once_with(("AA:BB:CC:DD:EE:FF", 16))
        self.assertEqual(bluez._RFCOMM_CHANNEL_CACHE["AA:BB:CC:DD:EE:FF"], 16)

    def test_open_rfcomm_prefers_cached_channel(self):
        bluez._RFCOMM_CHANNEL_CACHE.clear()
        bluez._RFCOMM_CHANNEL_CACHE["AA:BB:CC:DD:EE:FF"] = 16
        accepted = MagicMock()
        with (
            patch.object(bluez, "discover_rfcomm_channel") as discover,
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", return_value=accepted),
        ):
            result = bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertIs(result, accepted)
        discover.assert_not_called()
        accepted.connect.assert_called_once_with(("AA:BB:CC:DD:EE:FF", 16))

    def test_open_rfcomm_recovers_when_the_cached_channel_stops_answering(self):
        bluez._RFCOMM_CHANNEL_CACHE["AA:BB:CC:DD:EE:FF"] = 15
        refused = MagicMock()
        refused.connect.side_effect = OSError(errno.ECONNREFUSED, "Connection refused")
        accepted = MagicMock()
        with (
            patch.object(bluez, "discover_rfcomm_channel") as discover,
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", side_effect=[refused, accepted]),
        ):
            result = bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertIs(result, accepted)
        discover.assert_not_called()
        accepted.connect.assert_called_once_with(("AA:BB:CC:DD:EE:FF", 16))
        self.assertEqual(bluez._RFCOMM_CHANNEL_CACHE["AA:BB:CC:DD:EE:FF"], 16)

    def test_open_rfcomm_reports_refusal_without_retry_backoff(self):
        sockets = [MagicMock(), MagicMock()]
        for sock in sockets:
            sock.connect.side_effect = OSError(errno.ECONNREFUSED, "Connection refused")
        with (
            patch.object(bluez, "discover_rfcomm_channel", return_value=15),
            patch.object(bluez.operations, "pause") as pause,
            patch.object(bluez, "scan_for_device") as scan,
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", side_effect=sockets),
        ):
            with self.assertRaises(OSError) as error:
                bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertEqual(error.exception.errno, errno.ECONNREFUSED)
        pause.assert_not_called()
        scan.assert_not_called()

    def test_open_rfcomm_does_not_probe_when_the_device_is_unreachable(self):
        unreachable = MagicMock()
        unreachable.connect.side_effect = OSError(errno.EHOSTDOWN, "Host is down")
        with (
            patch.object(bluez, "discover_rfcomm_channel", return_value=15),
            patch.object(bluez.operations, "pause"),
            patch.object(bluez.socket, "AF_BLUETOOTH", 31, create=True),
            patch.object(bluez.socket, "BTPROTO_RFCOMM", 3, create=True),
            patch.object(bluez.socket, "socket", return_value=unreachable) as factory,
        ):
            with self.assertRaises(OSError) as error:
                bluez.open_rfcomm("AA:BB:CC:DD:EE:FF")
        self.assertEqual(error.exception.errno, errno.EHOSTDOWN)
        self.assertEqual(factory.call_count, 1)


if __name__ == "__main__":
    unittest.main()
