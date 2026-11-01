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
class NavigationTests(unittest.TestCase):
    def _window(self, visible="device"):
        buttons = {key: MagicMock() for key in ("device", "sound", "gestures", "tools")}
        return SimpleNamespace(
            _tab_buttons=buttons,
            stack=MagicMock(get_visible_child_name=MagicMock(return_value=visible)),
            _show_tab=MagicMock(),
        )

    def test_connected_enables_feature_sections(self):
        window = self._window()

        gui.EarAWindow._set_navigation_connected(window, True)

        for key in ("sound", "gestures", "tools"):
            window._tab_buttons[key].set_sensitive.assert_called_once_with(True)
        window._show_tab.assert_not_called()

    def test_disconnect_returns_to_device_and_disables_sections(self):
        window = self._window(visible="sound")

        gui.EarAWindow._set_navigation_connected(window, False)

        for key in ("sound", "gestures", "tools"):
            window._tab_buttons[key].set_sensitive.assert_called_once_with(False)
        window._show_tab.assert_called_once_with("device")


if __name__ == "__main__":
    unittest.main()
