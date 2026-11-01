import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from eara.eq_presets import display_gains, PRESET_PREVIEWS
from eara.gui import EarAWindow

class FactoryEqTests(unittest.TestCase):
    def test_factory_mode_does_not_display_stale_custom_bands(self):
        for name, expected in PRESET_PREVIEWS.items():
            values, preview = display_gains({'eq': name, 'graphic_eq':[5]*8})
            self.assertEqual(values,list(expected))
            self.assertTrue(preview)

    def test_custom_uses_actual_device_values(self):
        self.assertEqual(display_gains({'eq':'custom','graphic_eq':[2]*8}),([2]*8,False))

    def test_unconfirmed_preset_does_not_publish_success(self):
        ear=MagicMock();ear.status.return_value={'eq':'balanced'}
        w=SimpleNamespace(_require=lambda:ear,_last={'eq':'custom'})
        with patch('eara.gui.GLib.idle_add') as idle:
            with self.assertRaises(RuntimeError):EarAWindow._do_eq_preset(w,'more_bass')
            idle.assert_not_called()
        self.assertEqual(w._last,{'eq':'custom'})

    def test_acknowledged_preset_uses_native_command_only(self):
        ear=MagicMock();ear.status.return_value={'eq':'more_bass','graphic_eq':[0]*8}
        w=SimpleNamespace(_require=lambda:ear,_last={},_eq_local=True,_set_eq_dirty=MagicMock())
        with patch('eara.gui.GLib.idle_add',side_effect=lambda fn:fn()):
            EarAWindow._do_eq_preset(w,'more_bass')
        ear.set_eq.assert_called_once_with('more_bass')
        ear.set_graphic_eq.assert_not_called()
        self.assertFalse(w._eq_local)
