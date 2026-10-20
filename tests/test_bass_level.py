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
class BassLevelTests(unittest.TestCase):
    def test_bass_on_uses_slider_level(self):
        device = MagicMock()
        window = SimpleNamespace(_require=lambda: device)
        gui.EarAWindow._toggle(window, "bass", True, 3.0)
        device.set_bass.assert_called_once_with(True, 3.0)

    def test_slider_applies_its_level(self):
        window = SimpleNamespace(
            _shutting_down=False,
            _busy=False,
            _bass_level_timer=7,
            bass_level=MagicMock(get_value=MagicMock(return_value=4.0)),
            _run=MagicMock(),
            _toggle=MagicMock(),
        )
        self.assertFalse(gui.EarAWindow._apply_bass_level(window))
        window._run.call_args.args[0]()
        window._toggle.assert_called_once_with("bass", True, 4.0)
        self.assertEqual(window._bass_level_timer, 0)

    def test_slider_waits_while_busy(self):
        window = SimpleNamespace(_shutting_down=False, _busy=True, _bass_level_timer=7, _run=MagicMock())
        self.assertTrue(gui.EarAWindow._apply_bass_level(window))
        window._run.assert_not_called()

    def test_slider_does_nothing_after_close(self):
        window = SimpleNamespace(_shutting_down=True, _busy=False, _bass_level_timer=7, _run=MagicMock())
        self.assertFalse(gui.EarAWindow._apply_bass_level(window))
        window._run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
