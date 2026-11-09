import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch
from xml.etree import ElementTree

from eara import bluez, i18n
from eara.protocol import CMD_ANC_GET, CMD_BATTERY
from eara.session import Device

try:
    from eara import indicator
except ImportError:
    indicator = None


@unittest.skipIf(indicator is None, "Gio not available")
class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.lang = patch.object(i18n, "LANG", "en")
        self.lang.start()
        self.addCleanup(self.lang.stop)

    def test_icon_has_separate_battery_gauges_without_text(self):
        status = dict(bt_connected=True, protocol=True, anc="adaptive", battery={
            "left": dict(level=90, available=True), "right": dict(level=50, available=True),
        })
        root = ElementTree.fromstring(indicator.panel_icon(status))
        self.assertEqual((root.get("width"), root.get("height")), ("40", "22"))
        self.assertEqual(root.findall(".//{*}text"), [])
        fills = [rect for rect in root.findall("{*}rect") if rect.get("stroke") is None]
        self.assertEqual([(rect.get("x"), rect.get("width")) for rect in fills], [("2", "6.3"), ("12", "3.5")])

    def test_missing_bud_is_not_reported_as_zero(self):
        status = dict(bt_connected=True, protocol=True, anc="off", battery={})
        missing = indicator.panel_icon(status)
        status["battery"]["left"] = dict(level=0, available=True)
        self.assertNotEqual(indicator.panel_icon(status), missing)

    def test_disconnect_or_failed_read_does_not_reuse_old_values(self):
        status = dict(bt_connected=False, protocol=True, anc="high", battery={
            "left": dict(level=90, available=True), "right": dict(level=90, available=True),
        })
        unknown = indicator.panel_icon({})
        self.assertEqual(indicator.panel_icon(status), unknown)
        status.update(bt_connected=True, protocol=False)
        self.assertEqual(indicator.panel_icon(status), unknown)

    def test_noise_modes_are_distinguishable_without_color(self):
        icons = {indicator.panel_icon(dict(bt_connected=True, protocol=True, anc=mode))
                 for mode in ("high", "transparency", "off", None)}
        self.assertEqual(len(icons), 4)

    def test_low_battery_uses_shorter_fill_and_warning_color(self):
        status = dict(bt_connected=True, protocol=True, battery={"left": dict(level=10, available=True)})
        root = ElementTree.fromstring(indicator.panel_icon(status))
        fills = [rect for rect in root.findall("{*}rect") if rect.get("fill") == "#ff7b63"]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].get("width"), "0.7")

    def test_icon_updates_are_bounded_and_unchanged_readings_do_not_write(self):
        with TemporaryDirectory() as directory:
            app = SimpleNamespace(_icon_dir=SimpleNamespace(name=directory), _icon_svg="",
                                  _icon_files=[], _properties={}, _bus=MagicMock())
            status = dict(bt_connected=True, protocol=True, battery={"left": dict(level=90, available=True)})
            indicator.IndicatorApp._update_icon(app, status)
            path = Path(app._properties["IconName"].unpack())
            app._bus.emit_signal.reset_mock()
            with patch.object(indicator, "NamedTemporaryFile") as temporary:
                indicator.IndicatorApp._update_icon(app, status)
            temporary.assert_not_called()
            app._bus.emit_signal.assert_not_called()
            self.assertTrue(path.exists())
            for level in (80, 70, 60):
                status["battery"]["left"]["level"] = level
                indicator.IndicatorApp._update_icon(app, status)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)
            self.assertFalse(path.exists())

    def test_case_cache_and_charging_are_explicit(self):
        self.assertEqual(indicator.battery_text(dict(level=60, available=True, stale=True)), "~60%")
        self.assertEqual(indicator.battery_text(dict(level=60, available=True, charging=True)), "60%+")
        self.assertEqual(indicator.battery_text(dict(level=60, available=False)), "—")

    def test_models_without_anc_do_not_show_a_noise_mode(self):
        status = dict(bt_connected=True, protocol=True, battery={}, model={"features": {"anc": False}})
        root = ElementTree.fromstring(indicator.panel_icon(status))
        self.assertEqual(root.get("width"), "20")

    def test_polling_does_not_overlap_a_command(self):
        app = SimpleNamespace(_stopping=False, _busy=True)
        with patch.object(indicator.threading, "Thread") as thread:
            self.assertTrue(indicator.IndicatorApp._refresh(app))
        thread.assert_not_called()

    def test_background_failure_is_reported_and_returns_to_main_loop(self):
        app = SimpleNamespace(_stopping=False, _busy=False, _anc_items={},
                              preferred="", device=None, _show=MagicMock())
        with patch.object(indicator.Device, "discover", side_effect=RuntimeError("Bluetooth unavailable")), \
             patch.object(indicator.threading, "Thread") as thread, \
             patch.object(indicator.GLib, "idle_add") as idle:
            indicator.IndicatorApp._refresh(app)
            thread.call_args.kwargs["target"]()
        idle.assert_called_once_with(app._show, {"error": "Bluetooth unavailable"})

    def test_noise_selection_during_poll_is_not_lost(self):
        app = SimpleNamespace(_stopping=False, _busy=True, _pending_mode=None)
        indicator.IndicatorApp._refresh(app, "transparency")
        self.assertEqual(app._pending_mode, "transparency")

    def test_disconnected_indicator_hides_and_reappears_on_connection(self):
        app = SimpleNamespace(
            _busy=False, _stopping=False, _pending_mode=None,
            _device_item=MagicMock(), _battery_items={side: MagicMock() for side in ("left", "right", "case")},
            _anc_items={}, _bus=MagicMock(),
            _update_icon=MagicMock(),
            _properties={
                "Status": indicator.GLib.Variant("s", "Active"),
                "ToolTip": indicator.GLib.Variant("(sa(iiay)ss)", ("", [], "EarA", "")),
            },
        )
        with patch.object(indicator, "load_lang"):
            indicator.IndicatorApp._show(app, {})
            self.assertEqual(app._properties["Status"].unpack(), "Passive")
            self.assertNotIn("XAyatanaLabel", app._properties)
            app._bus.emit_signal.reset_mock()
            indicator.IndicatorApp._show(app, {})
            app._bus.emit_signal.assert_not_called()
            indicator.IndicatorApp._show(app, dict(bt_connected=True))
            self.assertEqual(app._properties["Status"].unpack(), "Active")


class MonitorTests(unittest.TestCase):
    def test_monitor_reads_battery_and_anc_in_one_session(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear")
        with patch.object(Device, "connected", new_callable=PropertyMock, return_value=True), \
             patch.object(bluez, "open_rfcomm", return_value=MagicMock()) as rfcomm, \
             patch.object(bluez, "trust_and_connect") as connect, \
             patch.object(device, "_request", side_effect=[bytes.fromhex("02 02 5a 03 55"), bytes([1, 4, 0])]) as request:
            status = device.monitor()
        rfcomm.assert_called_once_with(device.address)
        connect.assert_not_called()
        self.assertEqual([call.args[0] for call in request.call_args_list], [CMD_BATTERY, CMD_ANC_GET])
        self.assertEqual(status["battery"]["left"]["level"], 90)
        self.assertEqual(status["anc"], "adaptive")
        self.assertIsNone(device._sock)

    def test_monitor_never_reconnects_disconnected_earbuds(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear")
        with patch.object(Device, "connected", new_callable=PropertyMock, return_value=False), \
             patch.object(bluez, "open_rfcomm") as rfcomm, \
             patch.object(bluez, "trust_and_connect") as connect:
            with self.assertRaises(RuntimeError):
                device.monitor()
        rfcomm.assert_not_called()
        connect.assert_not_called()

    def test_failed_read_releases_control_channel(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear")
        sock = MagicMock()
        with patch.object(Device, "connected", new_callable=PropertyMock, return_value=True), \
             patch.object(bluez, "open_rfcomm", return_value=sock), \
             patch.object(device, "_request", side_effect=RuntimeError("No response")):
            with self.assertRaises(RuntimeError):
                device.monitor()
        sock.close.assert_called_once()
        self.assertIsNone(device._sock)


if __name__ == "__main__":
    unittest.main()
