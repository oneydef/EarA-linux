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
class SelectedDeviceTests(unittest.TestCase):
    def _window(self, current, selected_address):
        return SimpleNamespace(
            device=current,
            _device_list=[{"address": selected_address, "name": "CMF Buds 2"}],
            device_drop=MagicMock(get_selected=MagicMock(return_value=0)),
        )

    def test_same_earbuds_keep_their_device(self):
        current = gui.Device("3C:B0:ED:F4:B6:C3", "CMF Buds 2")
        current._battery_cache = {"case": {"level": 60, "charging": False, "available": True}}
        picked = gui.EarAWindow._selected_device(self._window(current, "3C:B0:ED:F4:B6:C3"))
        self.assertIs(picked, current)

    def test_other_earbuds_get_a_new_device(self):
        current = gui.Device("3C:B0:ED:F4:B6:C3", "CMF Buds 2")
        picked = gui.EarAWindow._selected_device(self._window(current, "AA:BB:CC:DD:EE:FF"))
        self.assertIsNot(picked, current)
        self.assertEqual(picked.address, "AA:BB:CC:DD:EE:FF")



if __name__ == "__main__":
    unittest.main()
