"""Scan candidate filtering must be pure and mockable — no hardware in tests."""
import unittest
from unittest.mock import MagicMock, patch

from eara import bluez


def _obj(address, name, *, paired=False, rssi=None):
    path = "/org/bluez/hci0/dev_" + address.replace(":", "_")
    props = {"Address": address, "Alias": name, "Paired": paired}
    if rssi is not None:
        props["RSSI"] = rssi
    return (path, {"org.bluez.Device1": props})


class CollectCandidatesTests(unittest.TestCase):
    def test_paired_nothing_first_and_same_name_deduped(self):
        objects = dict([
            _obj("AA:00:00:00:00:01", "Nothing Ear (a)", paired=False, rssi=-70),
            _obj("AA:00:00:00:00:02", "Nothing Ear (a)", paired=True, rssi=-80),
            _obj("AA:00:00:00:00:03", "[TV] Samsung", paired=True),
        ])
        found = bluez.collect_nothing_candidates(objects)
        # One row per model name: the paired entry wins over a fresh advert.
        self.assertEqual([d["name"] for d in found], ["Nothing Ear (a)"])
        self.assertTrue(found[0]["paired"])
        self.assertEqual(found[0]["address"], "AA:00:00:00:00:02")

    def test_same_name_unpaired_keeps_best_rssi(self):
        objects = dict([
            _obj("AA:00:00:00:00:01", "Nothing Ear (a)", paired=False, rssi=-70),
            _obj("AA:00:00:00:00:02", "Nothing Ear (a)", paired=False, rssi=-45),
        ])
        found = bluez.collect_nothing_candidates(objects)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["address"], "AA:00:00:00:00:02")
        self.assertEqual(found[0]["rssi"], -45)

    def test_anonymous_and_foreign_devices_excluded(self):
        objects = dict([
            _obj("AA:00:00:00:00:04", "", paired=True),
            _obj("AA:00:00:00:00:05", "AA-00-00-00-00-05", paired=False, rssi=-40),
            _obj("AA:00:00:00:00:06", "PIXUS FORTE", paired=True),
        ])
        self.assertEqual(bluez.collect_nothing_candidates(objects), [])

    def test_unpaired_excluded_when_not_requested(self):
        objects = dict([_obj("AA:00:00:00:00:01", "Nothing Ear (2)", paired=False, rssi=-50)])
        self.assertEqual(
            bluez.collect_nothing_candidates(objects, include_unpaired=False), [])

    def test_scan_stops_discovery_and_merges_paired(self):
        with patch.object(bluez, "_adapter_path", return_value="/org/bluez/hci0"), \
             patch.object(bluez, "start_discovery") as start, \
             patch.object(bluez, "stop_discovery") as stop, \
             patch.object(bluez, "paired_devices",
                          return_value=[{"address": "AA:00:00:00:00:02", "name": "Nothing Ear (a)"}]), \
             patch.object(bluez, "_dbus_objects", return_value=dict([
                 _obj("AA:00:00:00:00:01", "Nothing Ear (a)", paired=False, rssi=-60),
             ])):
            with patch.object(bluez.time, "sleep", lambda *_: None):
                found = bluez.scan_nothing_devices(1.5, progress=MagicMock())
        start.assert_called_once()
        stop.assert_called_once()
        # The stale paired record and the live advertisement merge into one row.
        self.assertEqual([d["name"] for d in found], ["Nothing Ear (a)"])
        self.assertTrue(found[0]["paired"])


class PairedListTests(unittest.TestCase):
    def test_paired_devices_prefers_dbus_and_marks_flags(self):
        with patch.object(bluez, "_dbus_objects", return_value=dict([
            _obj("AA:00:00:00:00:01", "Nothing Ear (a)", paired=True),
            _obj("AA:00:00:00:00:09", "Random Mouse", paired=False),
        ])):
            devices = bluez.paired_devices()
        self.assertEqual([d["name"] for d in devices], ["Nothing Ear (a)"])

    def test_paired_devices_falls_back_to_bluetoothctl(self):
        with patch.object(bluez, "_dbus_objects", return_value=None), \
             patch.object(bluez, "_ctl", return_value="Device AA:00:00:00:00:01 Nothing Ear (a)\nBroken line"):
            devices = bluez.paired_devices()
        self.assertEqual(devices, [{"address": "AA:00:00:00:00:01", "name": "Nothing Ear (a)"}])

    def test_paired_devices_flags_compatible(self):
        with patch.object(bluez, "_dbus_objects", return_value=dict([
            _obj("AA:00:00:00:00:01", "Nothing Ear (a)", paired=True),
        ])):
            devices = bluez.paired_devices()
        self.assertEqual(len(devices), 1)
        self.assertIn("compatible", devices[0])


if __name__ == "__main__":
    unittest.main()
