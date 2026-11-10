from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from eara import platforms
from eara.platforms.base import HostAudioState, UnavailableAudioBackend
from eara.session import Device


class AdapterResolutionTests(unittest.TestCase):
    def test_falsey_adapters_are_preserved_for_construction_and_discovery(self):
        transport, backend = MagicMock(), MagicMock()
        transport.__bool__.return_value = False
        backend.__bool__.return_value = False
        transport.discover.return_value = {'address': 'AA', 'name': 'Buds'}
        with patch.object(platforms, 'default_backends', side_effect=AssertionError('unexpected defaults')):
            for device in (Device('AA', transport=transport, audio_backend=backend),
                           Device.discover(transport=transport, audio_backend=backend)):
                self.assertIs(device.transport, transport)
                self.assertIs(device.audio_backend, backend)

    def test_transport_only_is_control_only_without_reconnect_attempts(self):
        transport = MagicMock()
        with patch.object(platforms, 'default_backends', side_effect=AssertionError('Linux default imported')):
            device = Device('AA', transport=transport)
            self.assertIsInstance(device.audio_backend, UnavailableAudioBackend)
            self.assertFalse(device.host_audio_state()['available'])
            self.assertFalse(device.connect_audio()['ok'])
            transport.connect.assert_not_called()
            self.assertFalse(device.set_codec('ldac')['ok'])
            transport.open_channel.assert_not_called()

    def test_unsupported_os_has_explicit_default_error(self):
        with patch.object(platforms.sys, 'platform', 'darwin'):
            with self.assertRaisesRegex(RuntimeError, 'No default EarA adapters for darwin'):
                platforms.default_backends()

    def test_host_state_does_not_share_mutable_codec_rows(self):
        state = HostAudioState(codecs=[{'key': 'aac'}])
        state.as_dict()['codecs'][0]['key'] = 'ldac'
        self.assertEqual(state.codecs[0]['key'], 'aac')

    def test_control_only_core_imports_without_linux_or_gtk(self):
        code = '''
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('eara.audio', 'eara.bluez', 'eara.platforms.linux', 'gi', 'dbus'):
            raise AssertionError('Platform import: ' + fullname)
sys.meta_path.insert(0, Block())
sys.platform = 'darwin'
from eara.session import Device
class Transport:
    def discover(self, preferred=''):
        return {'address': 'aa:bb:cc:dd:ee:ff', 'name': 'Buds'}
    def is_connected(self, address):
        return False
device = Device.discover(transport=Transport())
assert device.address == 'AA:BB:CC:DD:EE:FF'
assert device.status()['audio']['available'] is False
assert device.route_audio()['ok'] is False
assert device.connect_audio()['ok'] is False
from argparse import Namespace
from unittest.mock import patch
from eara import cli
from eara.platforms.base import DiagnosticSection
class Services:
    def __bool__(self):
        return False
    def inspect_services(self):
        return {'bluetooth': True, 'audio': True}
    def device_details(self, address):
        return ['Paired: yes']
    def audio_diagnostics(self):
        return [DiagnosticSection('Native audio', 'ready', True)]
with patch.object(cli, '_device', return_value=device):
    assert cli.cmd_doctor(Namespace(), services=Services()) == 0
'''
        result = subprocess.run([sys.executable, '-B', '-c', code],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
