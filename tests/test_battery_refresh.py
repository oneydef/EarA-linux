import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from eara import gui
except (ImportError, ValueError):
    gui = None


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class BatteryRefreshTests(unittest.TestCase):
    def _window(self, **state):
        base = dict(_shutting_down=False, device=MagicMock(), _busy=False, _battery_refreshing=False)
        base.update(state)
        return SimpleNamespace(**base)

    def test_refresh_waits_while_busy(self):
        window = self._window(_busy=True)
        self.assertTrue(gui.EarAWindow._refresh_battery(window))
        window.device.battery.assert_not_called()
        self.assertFalse(window._battery_refreshing)

    def test_refresh_stops_after_close(self):
        window = self._window(_shutting_down=True)
        self.assertFalse(gui.EarAWindow._refresh_battery(window))

    def test_refresh_without_device_keeps_waiting(self):
        self.assertTrue(gui.EarAWindow._refresh_battery(self._window(device=None)))

    def test_new_reading_updates_battery_cells(self):
        device = MagicMock()
        window = self._window(device=device, _battery_refreshing=True, _last={}, _update_battery_cell=MagicMock())
        battery = {"left": {"level": 85, "available": True}, "case": {"level": 60, "available": True}}
        gui.EarAWindow._show_battery(window, device, battery)
        self.assertFalse(window._battery_refreshing)
        self.assertEqual(window._last["battery"], battery)
        window._update_battery_cell.assert_any_call("case", battery["case"])
        window._update_battery_cell.assert_any_call("right", None)

    def test_reading_for_other_earbuds_is_ignored(self):
        window = self._window(_battery_refreshing=True, _last={}, _update_battery_cell=MagicMock())
        gui.EarAWindow._show_battery(window, MagicMock(), {"case": {"level": 60, "available": True}})
        self.assertFalse(window._battery_refreshing)
        window._update_battery_cell.assert_not_called()


if __name__ == "__main__":
    unittest.main()
