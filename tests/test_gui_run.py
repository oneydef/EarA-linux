import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from eara import gui
except (ImportError, ValueError):
    gui = None


class ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class BackgroundActionTests(unittest.TestCase):
    def test_unexpected_exception_unlocks_controls(self):
        window = SimpleNamespace(
            _busy=False,
            _busy_generation=0,
            _show=MagicMock(),
            _paint=MagicMock(),
        )

        def set_busy(value):
            window._busy = value

        window._set_busy = MagicMock(side_effect=set_busy)

        def fail():
            raise KeyError("unexpected")

        with (
            patch.object(gui.threading, "Thread", ImmediateThread),
            patch.object(gui.GLib, "idle_add", side_effect=lambda callback: callback()),
            patch.object(gui.traceback, "print_exc") as print_exc,
        ):
            gui.EarAWindow._run(window, fail, soft_timeout=0)

        self.assertFalse(window._busy)
        print_exc.assert_called_once_with()
        window._set_busy.assert_any_call(False)
        window._show.assert_called_once_with("KeyError: 'unexpected'")
        window._paint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
