import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from eara.health import inspect_services


class HealthTests(unittest.TestCase):
    def test_reports_success_only_for_actual_service_responses(self):
        responses = [SimpleNamespace(returncode=0, stdout='Controller 12:34\n Powered: yes'),
                     SimpleNamespace(returncode=0, stdout='Server Name: PulseAudio (on PipeWire)')]
        with patch('eara.health.subprocess.run', side_effect=responses) as run:
            self.assertEqual(inspect_services(), {'bluetooth': True, 'audio': True})
            self.assertEqual([c.args[0] for c in run.call_args_list], [['bluetoothctl','show'], ['pactl','info']])

    def test_unavailable_and_timed_out_are_not_ready(self):
        with patch('eara.health.subprocess.run', side_effect=[FileNotFoundError(), subprocess.TimeoutExpired('pactl',6)]):
            self.assertEqual(inspect_services(), {'bluetooth': False, 'audio': False})

    def test_powered_off_adapter_is_not_ready(self):
        responses = [SimpleNamespace(returncode=0, stdout='Controller 12:34\n Powered: no'),
                     SimpleNamespace(returncode=0, stdout='Server Name: PipeWire')]
        with patch('eara.health.subprocess.run', side_effect=responses):
            self.assertEqual(inspect_services(), {'bluetooth': False, 'audio': True})
