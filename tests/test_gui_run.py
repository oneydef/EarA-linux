import tempfile
import unittest
from pathlib import Path
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
            patch.object(gui.GLib, "idle_add", side_effect=lambda callback, **kw: callback()),
            patch.object(gui.traceback, "print_exc") as print_exc,
        ):
            gui.EarAWindow._run(window, fail, soft_timeout=0)

        self.assertFalse(window._busy)
        print_exc.assert_called_once_with()
        window._set_busy.assert_any_call(False)
        window._show.assert_called_once_with("KeyError: 'unexpected'")
        window._paint.assert_called_once_with()

    def test_local_action_does_not_dim_or_repaint_whole_page(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                switch = MagicMock()
                switch.get_can_target.return_value = True
                switch.get_focusable.return_value = True
                repaint = MagicMock()
                window = SimpleNamespace(
                    _busy=False, _busy_generation=0,
                    _set_busy=MagicMock(), _paint=MagicMock(), _show=MagicMock(),
                )
                calls = []
                def action():
                    self.assertTrue(window._busy)
                    calls.append("write")
                    # A reentrant callback must not issue another command.
                    gui.EarAWindow._run(window, lambda: calls.append("duplicate"))
                    if fails:
                        raise RuntimeError("write failed")
                with (
                    patch.object(gui.threading, "Thread", ImmediateThread),
                    patch.object(gui.GLib, "idle_add", side_effect=lambda cb, **kw: cb()),
                ):
                    gui.EarAWindow._run(window, action, soft_timeout=0,
                                       local_widgets=[switch], repaint=repaint)
                self.assertEqual(calls, ["write"])
                self.assertFalse(window._busy)
                window._set_busy.assert_not_called()
                window._paint.assert_not_called()
                repaint.assert_called_once_with()
                switch.set_sensitive.assert_not_called()
                self.assertEqual(switch.set_focusable.call_args_list,
                                 [unittest.mock.call(False), unittest.mock.call(True)])
                self.assertEqual(switch.set_can_target.call_args_list,
                                 [unittest.mock.call(False), unittest.mock.call(True)])
                self.assertEqual(window._show.call_count, int(fails))


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class GtkLogFilterTests(unittest.TestCase):
    CORNER_MESSAGE = (
        "_gtk_css_corner_value_get_y: assertion "
        "'corner->class == &GTK_CSS_VALUE_CORNER' failed"
    )

    def test_corner_value_critical_is_swallowed(self):
        with patch.object(gui.GLib, "log_default_handler") as forward:
            gui._gtk_log_handler("Gtk", 16, self.CORNER_MESSAGE, None)
        forward.assert_not_called()

    def test_any_other_critical_is_forwarded(self):
        message = "gtk_widget_hide: assertion 'GTK_IS_WIDGET (widget)' failed"
        with patch.object(gui.GLib, "log_default_handler") as forward:
            gui._gtk_log_handler("Gtk", 16, message, None)
        forward.assert_called_once_with("Gtk", 16, message, None)

    def test_runner_installs_the_filter(self):
        with patch.object(gui.GLib, "log_set_handler") as register, \
             patch.object(gui, "EarAApp") as app:
            gui.run()
        register.assert_called_once()
        args = register.call_args[0]
        self.assertEqual(args[0], "Gtk")
        self.assertEqual(args[1], gui.GLib.LogLevelFlags.LEVEL_CRITICAL)
        app.return_value.run.assert_called_once_with(None)


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class ButtonIconTests(unittest.TestCase):
    def test_horizontal_fallback_icon_without_pixel_size_does_not_crash(self):
        button = gui.Gtk.Button()
        with patch.object(gui, "_asset_path", return_value=None):
            gui._icon_button(button, "off", "Off", horizontal=True)
        icon = button.get_child().get_first_child()
        self.assertIsInstance(icon, gui.Gtk.DrawingArea)
        self.assertEqual(icon.get_next_sibling().get_label(), "Off")

    def test_fallback_icon_without_pixel_size_does_not_crash(self):
        icon = gui.Gtk.DrawingArea()
        button = MagicMock()
        with patch.object(gui, "_line_icon", return_value=icon):
            gui._button_with_icon(button, "reset", "Reset")
        self.assertTrue(icon.has_css_class("eara-button-icon"))
        button.set_child.assert_called_once()


@unittest.skipIf(gui is None, "GTK 4 / libadwaita not available")
class AssetPathTests(unittest.TestCase):
    def test_finds_assets_in_the_installed_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset = Path(tmp) / "share/eara/packaging/ui/icons/probe-symbolic.svg"
            asset.parent.mkdir(parents=True)
            asset.write_text("<svg/>", encoding="utf-8")
            with patch.object(gui.sysconfig, "get_path", return_value=tmp):
                self.assertEqual(gui._asset_path("ui/icons/probe-symbolic.svg"), asset)

    def test_missing_data_directory_does_not_crash(self):
        with patch.object(gui.sysconfig, "get_path", return_value=None):
            self.assertIsNone(gui._asset_path("ui/icons/does-not-exist.svg"))

    def test_fonts_are_installed_from_the_resolved_asset_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Inter-Regular.ttf"
            source.write_bytes(b"font")
            home = Path(tmp) / "home"
            home.mkdir()
            with (
                patch.object(gui.Path, "home", return_value=home),
                patch.object(gui, "_asset_path", return_value=source) as resolve,
                patch("subprocess.run") as run,
            ):
                gui._ensure_fonts()
            installed = home / ".local/share/fonts/eara/Inter-Regular.ttf"
            self.assertEqual(installed.read_bytes(), b"font")
            resolve.assert_any_call("fonts/Inter-Regular.ttf")
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
