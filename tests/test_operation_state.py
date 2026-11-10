import threading
import unittest
from unittest.mock import MagicMock, patch

try:
    from eara import gui
except (ImportError, ValueError):
    gui = None


class Window:
    if gui is not None:
        _last = gui.EarAWindow._last

    def __init__(self):
        self.device = object()
        self._busy = False
        self._last = {'latency': False, 'battery': {'left': 50}}
        self._show = MagicMock()
        self._paint = MagicMock()

    def _set_busy(self, value):
        self._busy = value


@unittest.skipIf(gui is None, 'GTK unavailable')
class StateTests(unittest.TestCase):
    def test_queued_ui_callback_is_dropped_after_cancellation(self):
        window = Window()
        window._busy_generation = 2
        window._operation_context = threading.local()
        cancel = threading.Event()
        window._operation_context.cancel = cancel
        callback = MagicMock()
        queued = []
        with patch.object(gui.GLib, 'idle_add', side_effect=queued.append):
            gui.EarAWindow._post(window, callback)
        cancel.set()
        queued[0]()
        callback.assert_not_called()

    def test_only_current_success_is_committed_on_main_thread(self):
        for outcome in ('success', 'failure', 'cancelled', 'new_generation', 'other_device', 'closed'):
            with self.subTest(outcome=outcome):
                window = Window()
                callbacks, targets = [], []
                def action():
                    window._last['battery']['left'] = 75
                    window._last = {**window._last, 'latency': True}
                    if outcome == 'failure':
                        raise RuntimeError('no acknowledgement')
                    if outcome == 'cancelled':
                        window._operation_cancel.set()
                with patch.object(gui.threading, 'Thread', side_effect=lambda **kw: targets.append(kw['target']) or MagicMock()):
                    gui.EarAWindow._run(window, action, soft_timeout=0)
                with patch.object(gui.GLib, 'idle_add',
                                  side_effect=lambda callback, **kw: callbacks.append(callback)) as idle:
                    worker = threading.Thread(target=targets[0])
                    worker.start()
                    worker.join(timeout=3)
                self.assertFalse(worker.is_alive())
                self.assertEqual(idle.call_args.kwargs['priority'], gui.GLib.PRIORITY_DEFAULT)
                self.assertEqual(window._last, {'latency': False, 'battery': {'left': 50}})
                if outcome == 'new_generation':
                    window._busy_generation += 1
                if outcome == 'other_device':
                    window.device = object()
                if outcome == 'closed':
                    window._shutting_down = True
                callbacks[0]()
                self.assertEqual(window._last['latency'], outcome == 'success')
                self.assertEqual(window._last['battery']['left'], 75 if outcome == 'success' else 50)

    def test_quick_controls_do_not_poll_full_status(self):
        for which, key in [('bass', 'bass'), ('ied', 'in_ear'), ('lat', 'latency'),
                           ('adv', 'advanced_eq'), ('panc', 'personalized_anc')]:
            for fails in (False, True):
                with self.subTest(which=which, fails=fails):
                    window = Window()
                    device = MagicMock()
                    window._require = lambda: device
                    if fails:
                        for method in ('set_bass', 'set_in_ear_detection', 'set_latency',
                                       'set_advanced_eq', 'set_personalized_anc'):
                            getattr(device, method).side_effect = RuntimeError('no ack')
                        with self.assertRaises(RuntimeError):
                            gui.EarAWindow._toggle(window, which, True, 3)
                        self.assertEqual(window._last, {'latency': False, 'battery': {'left': 50}})
                    else:
                        gui.EarAWindow._toggle(window, which, True, 3)
                        self.assertEqual(window._last[key], {'enabled': True, 'level': 3} if which == 'bass' else True)
                    device.status.assert_not_called()
