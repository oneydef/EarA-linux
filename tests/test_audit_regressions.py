"""Failure paths identified by the 0.7 audit; no hardware or user config I/O."""
import io
import subprocess
import threading
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from eara import audio, cli
from eara.protocol import CMD_BATTERY, CMD_CODEC_GET, DIR_SET
from eara.session import Device

try:
    from eara import gui
except (ImportError, ValueError):
    gui = None


class BackendFailureTests(unittest.TestCase):
    def test_audio_failure_preserves_protocol_status(self):
        for error in (RuntimeError('audio unavailable'), subprocess.TimeoutExpired('pactl', 6)):
            with self.subTest(error=error):
                transport, backend = MagicMock(), MagicMock()
                transport.is_connected.return_value = True
                backend.state.side_effect = error
                device = Device('AA:BB:CC:DD:EE:FF', transport=transport, audio_backend=backend)
                with patch.object(device, 'open_control'), patch.object(device, 'close_control'), \
                     patch.object(device, '_request', side_effect=lambda cmd, **kw: b'\x01' if cmd == CMD_BATTERY else None), \
                     patch('eara.session.parse_battery', return_value={'case': {'available': True, 'level': 80}}):
                    status = device.status()
                self.assertTrue(status['protocol'])
                self.assertEqual(status['battery']['case']['level'], 80)
                self.assertEqual(status['audio']['error'], str(error))

    def test_codec_host_failure_never_opens_control_channel(self):
        backend = MagicMock()
        backend.set_codec.return_value = {'ok': False, 'error': 'unsupported'}
        device = Device('AA:BB:CC:DD:EE:FF', transport=MagicMock(), audio_backend=backend)
        with patch.object(device, '_session') as session, patch.object(device, '_request') as request:
            self.assertFalse(device.set_codec('ldac')['ok'])
        session.assert_not_called()
        request.assert_not_called()

    def test_codec_host_success_still_updates_earbuds(self):
        backend = MagicMock()
        backend.set_codec.return_value = {'ok': True}
        device = Device('AA:BB:CC:DD:EE:FF', transport=MagicMock(), audio_backend=backend)
        with patch.object(device, '_session'), patch.object(device, '_request') as request:
            self.assertTrue(device.set_codec('ldac')['ok'])
        request.assert_called_once_with(CMD_CODEC_GET, DIR_SET, b'\x02', require=True)

    def test_audio_routes_never_reconfigure_global_policy(self):
        for route in (audio.ensure_music_audio, audio.ensure_call_audio):
            for ready in (False, True):
                with self.subTest(route=route.__name__, ready=ready), \
                     patch.object(audio, 'keep_a2dp_in_calls') as policy, \
                     patch.object(audio, 'ensure_bluez_card', return_value=ready), \
                     patch.object(audio, 'set_profile', return_value=True), \
                     patch.object(audio, 'wait_for_sink', return_value='test-sink'), \
                     patch.object(audio, 'set_default_sink'), \
                     patch.object(audio, 'move_streams_to_default'), \
                     patch.object(audio, 'active_profile', return_value='a2dp_sink'), \
                     patch.object(audio, 'find_source', return_value=None):
                    self.assertEqual(route('AA:BB:CC:DD:EE:FF')['ok'], ready)
                    policy.assert_not_called()

    def test_doctor_reports_partial_results_after_process_errors(self):
        for error in (subprocess.CalledProcessError(1, 'pactl'),
                      subprocess.TimeoutExpired('pactl', 6), FileNotFoundError('pactl')):
            output = io.StringIO()
            with self.subTest(error=error), patch.object(cli, '_device', side_effect=LookupError('none')), \
                 patch('eara.bluez._ctl', return_value='Powered: yes'), \
                 patch('eara.health.inspect_services', return_value={'bluetooth': True, 'audio': True}), \
                 patch('subprocess.check_output', side_effect=[error, 'sink-ready', 'source-ready']) as run, \
                 redirect_stdout(output):
                self.assertEqual(cli.main(['doctor']), 1)
            self.assertIn('unavailable', output.getvalue())
            self.assertIn('sink-ready', output.getvalue())
            self.assertIn('source-ready', output.getvalue())
            self.assertTrue(all(call.kwargs['timeout'] == 6 for call in run.call_args_list))


@unittest.skipIf(gui is None, 'GTK unavailable')
class GuiFailureTests(unittest.TestCase):
    def test_worker_uses_captured_device_without_widgets(self):
        first, second = object(), object()
        queued = []
        window = SimpleNamespace(_busy=False, device=first, _device_list=[{}],
                                 _selected_device=lambda: first, _paint=MagicMock(),
                                 _show=MagicMock())
        window._set_busy = lambda value: setattr(window, '_busy', value)
        thread = MagicMock()
        seen = []
        with patch.object(gui.threading, 'Thread', side_effect=lambda **kw: queued.append(kw['target']) or thread):
            gui.EarAWindow._run(window, lambda: seen.append(gui.EarAWindow._require(window)), soft_timeout=0)
        window.device = second
        window._selected_device = MagicMock(side_effect=AssertionError('GTK in worker'))
        callbacks = []
        with patch.object(gui.GLib, 'idle_add', side_effect=lambda cb, **kw: callbacks.append(cb)):
            worker = threading.Thread(target=queued[0])
            worker.start()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen, [first])
        window._selected_device.assert_not_called()
        callbacks[0]()

    def test_listening_commits_only_after_successful_write(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                device = MagicMock()
                window = SimpleNamespace(_last={'listening': 'off', 'battery': {'left': 50}},
                                         _require=lambda: device)
                if fails:
                    device.set_listening_mode.side_effect = RuntimeError('no ack')
                    with self.assertRaises(RuntimeError):
                        gui.EarAWindow._do_listening(window, 'entertainment')
                else:
                    gui.EarAWindow._do_listening(window, 'entertainment')
                self.assertEqual(window._last['listening'], 'off' if fails else 'entertainment')
                self.assertEqual(window._last['battery'], {'left': 50})
