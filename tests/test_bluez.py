import unittest
from unittest.mock import patch

from eara import bluez


class BluezTests(unittest.TestCase):
    def test_find_nothing_rejects_unpaired_mac(self):
        with patch.object(bluez, "paired_devices", return_value=[]):
            self.assertIsNone(bluez.find_nothing_device("AA:BB:CC:DD:EE:FF"))

    def test_find_nothing_accepts_paired_mac(self):
        paired = [{"address": "AA:BB:CC:DD:EE:FF", "name": "Nothing Ear (a)"}]
        with patch.object(bluez, "paired_devices", return_value=paired):
            found = bluez.find_nothing_device("AA:BB:CC:DD:EE:FF")
        self.assertIsNotNone(found)
        self.assertEqual(found["address"], "AA:BB:CC:DD:EE:FF")

    def test_trust_and_connect_requires_pairing(self):
        with patch.object(bluez, "_is_paired", return_value=False):
            with self.assertRaises(RuntimeError):
                bluez.trust_and_connect("AA:BB:CC:DD:EE:FF", timeout=1, scan=False, max_rounds=1)

    def test_power_off_skips_when_already_off(self):
        with patch.object(bluez, "_ctl", return_value="Powered: no") as ctl:
            bluez.power_off()
        ctl.assert_called_once_with("show")

    def test_power_off_when_on(self):
        with patch.object(bluez, "_ctl", side_effect=["Powered: yes", ""]):
            bluez.power_off()


if __name__ == "__main__":
    unittest.main()
