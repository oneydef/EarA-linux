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


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class NavigationTests(unittest.TestCase):
    def test_navigation_does_not_override_system_theme(self):
        for page in ("device", "sound", "gestures", "tools"):
            for connected in (False, True):
                with self.subTest(page=page, connected=connected):
                    window = SimpleNamespace(
                        stack=MagicMock(get_visible_child_name=MagicMock(return_value=page)),
                        _last={"protocol": connected, "bt_connected": connected},
                        buttons=MagicMock(), add_css_class=MagicMock(), remove_css_class=MagicMock(),
                        _nav_icons={"device": MagicMock()},
                    )
                    with patch.object(gui.Adw.StyleManager, "get_default") as manager:
                        gui.EarAWindow._sync_reference_layout(window)
                    manager.return_value.set_color_scheme.assert_not_called()

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
