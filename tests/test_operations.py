import threading
import sys
import unittest
from unittest.mock import MagicMock, patch

from eara import audio, bluez, operations
from eara.session import Device


class OperationTests(unittest.TestCase):
    def test_adapter_lookup_does_not_hide_cancellation(self):
        cancel = threading.Event()
        fake_dbus = MagicMock()
        def interrupted(*args, **kwargs):
            cancel.set()
            raise OSError('bus interrupted')
        fake_dbus.Interface.return_value.GetManagedObjects.side_effect = interrupted
        with patch.dict(sys.modules, {'dbus': fake_dbus}):
            with self.assertRaises(operations.Cancelled):
                with operations.scope(10, cancel):
                    bluez._device_path('AA')

    def test_final_failed_connect_does_not_wait_for_nonexistent_retry(self):
        transport, backend = MagicMock(), MagicMock()
        transport.is_connected.return_value = False
        transport.connect.side_effect = TimeoutError('transport unavailable')
        device = Device('AA', transport=transport, audio_backend=backend)
        with patch.object(operations, 'pause') as pause:
            result = device.connect_audio(attempts=1)
        self.assertFalse(result['ok'])
        self.assertIn('transport unavailable', result['error'])
        self.assertNotIn('disable phone Bluetooth', result['error'])
        transport.abort_connection.assert_called_once_with('AA')
        pause.assert_not_called()

    def test_invalid_attempt_count_does_not_touch_transport(self):
        transport, backend = MagicMock(), MagicMock()
        device = Device('AA', transport=transport, audio_backend=backend)
        with self.assertRaises(ValueError):
            device.connect_audio(attempts=0)
        transport.is_connected.assert_not_called()
        transport.connect.assert_not_called()

    def test_nested_budget_cannot_extend_deadline(self):
        now = [100.0]
        with patch.object(operations.time, 'monotonic', side_effect=lambda: now[0]):
            with operations.scope(10):
                now[0] = 108
                with operations.scope(90):
                    self.assertEqual(operations.timeout(6), 2)
            self.assertEqual(operations.timeout(6), 6)

    def test_cancelled_operation_does_not_start_platform_commands(self):
        for call in (lambda: bluez._ctl('connect', 'AA'), lambda: audio._pactl('info')):
            with self.subTest(call=call), patch('subprocess.run') as run:
                cancel = threading.Event()
                with self.assertRaises(operations.Cancelled):
                    with operations.scope(10, cancel):
                        cancel.set()
                        call()
                run.assert_not_called()

    def test_platform_commands_receive_remaining_budget(self):
        now = [100.0]
        with patch.object(operations.time, 'monotonic', side_effect=lambda: now[0]), \
             patch('subprocess.run', return_value=MagicMock(returncode=0, stdout='', stderr='')) as run:
            with operations.scope(10):
                now[0] = 108.5
                bluez._ctl('show')
                audio._pactl('info')
            self.assertEqual([c.kwargs['timeout'] for c in run.call_args_list], [1.5, 1.5])

    def test_connect_does_not_retry_or_reset_after_budget_expires(self):
        now = [100.0]
        transport = MagicMock()
        transport.is_connected.return_value = False
        def slow_connect(*args, **kwargs):
            self.assertEqual(kwargs['timeout'], 2)
            now[0] += 2
            raise TimeoutError('timed out')
        transport.connect.side_effect = slow_connect
        backend = MagicMock()
        device = Device('AA:BB:CC:DD:EE:FF', transport=transport, audio_backend=backend)
        with patch.object(operations.time, 'monotonic', side_effect=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                with operations.scope(2):
                    device.connect_audio()
        transport.connect.assert_called_once()
        transport.abort_connection.assert_not_called()
        backend.reload.assert_not_called()

    def test_cancel_interrupts_backoff(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(operations.Cancelled):
            with operations.scope(10, cancel):
                operations.pause(5)

    def test_cleanup_allowed_after_cancel_then_cancellation_restored(self):
        cancel = threading.Event()
        with self.assertRaises(operations.Cancelled):
            with operations.scope(10, cancel):
                cancel.set()
                with operations.cleanup():
                    self.assertEqual(operations.timeout(3), 3)
                operations.check()
