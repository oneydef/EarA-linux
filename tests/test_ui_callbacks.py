"""UI synchronization must never send commands while no device is selected."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

try:
    from eara.gui import EarAWindow
except (ImportError, ValueError):
    EarAWindow = None


@unittest.skipIf(EarAWindow is None, 'GTK unavailable')
class CallbackTests(unittest.TestCase):
    def test_populating_listening_without_device_does_not_start_command(self):
        window = SimpleNamespace(_busy=False, _ignore_listening=False, device=None, _run=MagicMock())
        EarAWindow._on_listening_changed(window)
        window._run.assert_not_called()

    def test_syncing_anc_strength_does_not_send_command(self):
        window = SimpleNamespace(_busy=False, _ignore_toggle=True, device=object(), _run=MagicMock())
        EarAWindow._on_anc_strength_changed(window)
        window._run.assert_not_called()

    def test_custom_preset_focuses_editor_without_sending_unsupported_preset(self):
        window = SimpleNamespace(eq_buttons={}, eq_bands=[MagicMock()], _set_chip_active=MagicMock(), _run=MagicMock())
        EarAWindow._select_eq_preset(window, 'custom')
        window.eq_bands[0].grab_focus.assert_called_once()
        window._run.assert_not_called()

    def test_anc_selection_refreshes_the_real_status(self):
        device = MagicMock()
        device.status.return_value = {"anc": "low", "protocol": True}
        window = SimpleNamespace(_require=lambda: device, _last={})
        EarAWindow._do_anc(window, 'low')
        device.set_anc.assert_called_once_with('low')
        self.assertEqual(window._last, {"anc": "low", "protocol": True})

    def test_failed_anc_write_does_not_publish_a_fake_state(self):
        device = MagicMock()
        device.set_anc.side_effect = RuntimeError('not connected')
        window = SimpleNamespace(_require=lambda: device, _last={"anc": "high"})
        with self.assertRaises(RuntimeError):
            EarAWindow._do_anc(window, 'low')
        self.assertEqual(window._last, {"anc": "high"})
        device.status.assert_not_called()
