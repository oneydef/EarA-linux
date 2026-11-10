"""Profile selection tests; all host and Bluetooth operations are substituted."""
from contextlib import ExitStack
import threading
import unittest
from unittest.mock import patch

from eara import audio, operations


class HfpProfilesTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.calls = {}
        for name, result in (
            ('ensure_bluez_card', True), ('set_profile', True),
            ('wait_for_sink', 'output'), ('wait_for_source', 'microphone'),
            ('set_default_sink', True), ('move_streams_to_default', None),
            ('set_default_source', True), ('move_record_streams', None),
        ):
            self.calls[name] = self.stack.enter_context(patch.object(audio, name, return_value=result))
        self.connect = self.stack.enter_context(patch.object(audio.bluez, 'dbus_connect_profile'))
        self.pause = self.stack.enter_context(patch.object(operations, 'pause'))

    def test_profile_becomes_ready_after_initial_rejection(self):
        self.calls['set_profile'].side_effect = [False] * 5 + [True]
        self.assertTrue(audio.ensure_hfp_audio('AA')['ok'])
        self.pause.assert_called_once_with(0.5)

    def test_permanent_rejection_has_bounded_retries(self):
        self.calls['set_profile'].return_value = False
        self.assertFalse(audio.ensure_hfp_audio('AA')['ok'])
        self.assertEqual(self.calls['set_profile'].call_count, 15)
        self.assertEqual(self.pause.call_count, 2)

    def test_cancellation_during_retry_stops_profile_changes(self):
        self.calls['set_profile'].return_value = False
        self.pause.side_effect = operations.Cancelled('cancelled')
        with self.assertRaises(operations.Cancelled):
            audio.ensure_hfp_audio('AA')
        self.assertEqual(self.calls['set_profile'].call_count, 5)

    def test_pipewire_and_legacy_profiles_in_preference_order(self):
        profiles = ['headset-head-unit-msbc', 'headset-head-unit', 'handsfree-head-unit',
                    'handsfree_head_unit', 'headset_head_unit']
        for index, supported in enumerate(profiles):
            with self.subTest(profile=supported):
                setter = self.calls['set_profile']
                setter.reset_mock()
                setter.side_effect = lambda address, profile: profile == supported
                result = audio.ensure_hfp_audio('AA:BB:CC:DD:EE:FF')
                self.assertTrue(result['ok'])
                self.assertEqual(result['profile'], supported)
                self.assertEqual([c.args[1] for c in setter.call_args_list], profiles[:index + 1])

    def test_rejected_profiles_do_not_change_default_routes(self):
        self.calls['set_profile'].return_value = False
        self.assertFalse(audio.ensure_hfp_audio('AA')['ok'])
        for name in ('wait_for_sink', 'wait_for_source', 'set_default_sink', 'set_default_source'):
            self.calls[name].assert_not_called()

    def test_missing_microphone_falls_back_to_next_profile(self):
        self.calls['wait_for_source'].side_effect = [None, 'microphone']
        result = audio.ensure_hfp_audio('AA')
        self.assertTrue(result['ok'])
        self.assertEqual(result['profile'], 'headset-head-unit')
        self.calls['set_default_sink'].assert_called_once()

    def test_missing_microphone_never_moves_output_streams(self):
        self.calls['wait_for_source'].return_value = None
        self.assertFalse(audio.ensure_hfp_audio('AA')['ok'])
        self.calls['set_default_sink'].assert_not_called()
        self.calls['move_streams_to_default'].assert_not_called()

    def test_failed_default_route_is_not_reported_as_success(self):
        for failed in ('set_default_source', 'set_default_sink'):
            with self.subTest(failed=failed):
                self.calls['set_default_source'].return_value = True
                self.calls['set_default_sink'].return_value = True
                self.calls[failed].return_value = False
                self.assertFalse(audio.ensure_hfp_audio('AA')['ok'])
                self.calls['move_record_streams'].assert_not_called()

    def test_cancellation_after_bluetooth_request_stops_profile_changes(self):
        cancelled = threading.Event()
        def cancel(*args):
            cancelled.set()
            raise OSError('link interrupted')
        self.connect.side_effect = cancel
        with self.assertRaises(operations.Cancelled):
            with operations.scope(10, cancelled):
                audio.ensure_hfp_audio('AA')
        self.calls['set_profile'].assert_not_called()

    def test_existing_operation_deadline_limits_fallback(self):
        now = [0.0]
        def reject(*args):
            now[0] = 2.0
            return False
        self.calls['set_profile'].side_effect = reject
        with patch.object(operations.time, 'monotonic', side_effect=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                with operations.scope(1):
                    audio.ensure_hfp_audio('AA')
        self.calls['set_profile'].assert_called_once()

    def test_calls_still_uses_a2dp_not_hfp(self):
        with patch.object(audio, 'ensure_music_audio', return_value={'ok': True, 'profile': 'a2dp_sink'}), \
             patch.object(audio, 'find_source', return_value=None), \
             patch.object(audio, 'ensure_hfp_audio') as hfp:
            self.assertEqual(audio.ensure_call_audio('AA')['profile'], 'a2dp_sink')
        hfp.assert_not_called()
