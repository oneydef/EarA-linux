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
class EqualizerControlTests(unittest.TestCase):
    def test_reset_zeroes_bands_and_marks_changes_pending(self):
        scales = [MagicMock(), MagicMock()]
        for scale in scales:
            scale.get_value.return_value = 2.0
        graphic_box = MagicMock()
        graphic_box.get_mapped.return_value = False
        window = SimpleNamespace(
            eq_bands=scales,
            graphic_box=graphic_box,
            _eq_syncing=False,
            _eq_local=False,
            _set_eq_dirty=MagicMock(),
        )

        gui.EarAWindow._reset_eq(window)

        for scale in scales:
            scale.set_value.assert_called_once_with(0)
        self.assertFalse(window._eq_syncing)
        self.assertTrue(window._eq_local)
        window._set_eq_dirty.assert_called_once_with(True)

    def test_band_change_updates_value_and_dirty_state(self):
        value_label = MagicMock()
        window = SimpleNamespace(
            _eq_syncing=False,
            _eq_local=False,
            _set_eq_dirty=MagicMock(),
        )

        gui.EarAWindow._on_eq_band_changed(window, MagicMock(get_value=lambda: 2.5), value_label)

        value_label.set_text.assert_called_once_with("+2.5 dB")
        self.assertTrue(window._eq_local)
        window._set_eq_dirty.assert_called_once_with(True)

    def test_apply_sends_current_values_without_claiming_success_early(self):
        action = MagicMock()
        window = SimpleNamespace(
            eq_bands=[MagicMock(get_value=lambda: -1.0), MagicMock(get_value=lambda: 3.5)],
            _eq_local=False,
            _set_eq_dirty=MagicMock(),
            _run=MagicMock(),
            _do_custom_eq=action,
        )

        gui.EarAWindow._apply_eq(window)

        self.assertTrue(window._eq_local)
        window._set_eq_dirty.assert_not_called()
        window._run.call_args.args[0]()
        action.assert_called_once_with([-1.0, 3.5])

    def test_device_write_failure_keeps_pending_edits(self):
        device = MagicMock()
        device.set_graphic_eq.side_effect = RuntimeError("RFCOMM timed out")
        window = SimpleNamespace(_require=lambda: device, device=device, _set_eq_dirty=MagicMock())
        with patch.object(gui.GLib, "idle_add") as idle:
            with self.assertRaises(RuntimeError):
                gui.EarAWindow._do_custom_eq(window, [1.0]*8)
            idle.assert_not_called()
        window._set_eq_dirty.assert_not_called()

    def test_successful_device_write_clears_pending_edits_on_ui_thread(self):
        device = MagicMock()
        window = SimpleNamespace(_require=lambda: device, device=device, _set_eq_dirty=MagicMock())
        with patch.object(gui.GLib, "idle_add") as idle:
            gui.EarAWindow._do_custom_eq(window, [1.0]*8)
            window._set_eq_dirty.assert_not_called()
            idle.call_args.args[0]()
        window._set_eq_dirty.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()

@unittest.skipIf(gui is None, 'GTK unavailable')
class AutomaticEqTests(unittest.TestCase):
    def window(self):
        return SimpleNamespace(device=object(), _last={'protocol':True},
            _eq_apply_timer=9, _shutting_down=False, _busy=False, _eq_dirty=True,
            _apply_eq=MagicMock())

    def test_coalesces_motion_and_applies_latest_controls(self):
        w=self.window()
        with patch.object(gui.GLib,'source_remove') as remove, patch.object(gui.GLib,'timeout_add',return_value=10) as timer:
            gui.EarAWindow._queue_eq_apply(w)
            remove.assert_called_once_with(9)
            self.assertEqual(timer.call_args.args[0],300)
            self.assertFalse(timer.call_args.args[1]())
            w._apply_eq.assert_called_once_with()

    def test_does_not_send_to_new_device(self):
        w=self.window()
        with patch.object(gui.GLib,'source_remove'), patch.object(gui.GLib,'timeout_add') as timer:
            gui.EarAWindow._queue_eq_apply(w)
            w.device=object()
            self.assertFalse(timer.call_args.args[1]())
            w._apply_eq.assert_not_called()

    def test_disconnect_cancels_pending_write(self):
        w=self.window()
        with patch.object(gui.GLib,'source_remove'), patch.object(gui.GLib,'timeout_add') as timer:
            gui.EarAWindow._queue_eq_apply(w)
            w._last={'protocol':False}
            self.assertFalse(timer.call_args.args[1]())
            w._apply_eq.assert_not_called()

    def test_serializes_with_other_hardware_commands(self):
        w=self.window()
        with patch.object(gui.GLib,'source_remove'), patch.object(gui.GLib,'timeout_add') as timer:
            gui.EarAWindow._queue_eq_apply(w)
            callback=timer.call_args.args[1]
            w._busy=True
            self.assertTrue(callback())
            w._apply_eq.assert_not_called()
            w._busy=False
            self.assertFalse(callback())
            w._apply_eq.assert_called_once_with()
