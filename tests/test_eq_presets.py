import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from eara import eq_presets


class PresetTests(unittest.TestCase):
    def test_roundtrip_and_absent_preset(self):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {'XDG_CONFIG_HOME': directory}):
            self.assertIsNone(eq_presets.load_preset())
            gains = [0, 1, -2, 3, -4, 5, -6, 6]
            eq_presets.save_preset(gains)
            self.assertEqual(eq_presets.load_preset(), gains)

    def test_rejects_incompatible_frequency_mapping(self):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {'XDG_CONFIG_HOME': directory}):
            eq_presets.save_preset([0]*8)
            path = Path(directory)/'eara/eq-preset.json'
            data = json.loads(path.read_text())
            data['frequencies'][0] = 60
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                eq_presets.load_preset()

    def test_invalid_save_does_not_destroy_previous_preset(self):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {'XDG_CONFIG_HOME': directory}):
            eq_presets.save_preset([1]*8)
            for invalid in ([0]*7, [float('nan')]*8, [7]*8, [True]*8):
                with self.assertRaises(ValueError):
                    eq_presets.save_preset(invalid)
            self.assertEqual(eq_presets.load_preset(), [1]*8)
