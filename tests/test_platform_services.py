import io
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from eara import cli, health
from eara.platforms.linux_services import LinuxPlatformServices

try:
    from eara import gui
except (ImportError, ValueError):
    gui = None


class ServicesTests(unittest.TestCase):
    def test_pairing_delegates_without_implicit_connect_or_power_change(self):
        services = LinuxPlatformServices()
        with patch('eara.bluez.is_paired_dbus', return_value=False) as paired, \
             patch('eara.bluez.pair_device') as pair, \
             patch('eara.bluez.trust_and_connect') as connect, \
             patch('eara.bluez.power_off') as power:
            self.assertFalse(services.is_paired('AA'))
            services.pair('AA')
            paired.assert_called_once_with('AA')
            pair.assert_called_once_with('AA')
            connect.assert_not_called()
            power.assert_not_called()

    def test_device_details_filter_exact_keys(self):
        with patch('eara.bluez.device_info', return_value='Name: Paired buds\n  Paired: yes\n Trusted: no\nServicesResolved: yes'):
            self.assertEqual(LinuxPlatformServices().device_details('AA'),
                             ['Paired: yes', 'Trusted: no', 'ServicesResolved: yes'])

    @unittest.skipIf(gui is None, 'GTK unavailable')
    def test_gui_pair_failure_never_starts_connect(self):
        device = MagicMock(connected=False)
        services = MagicMock()
        services.is_paired.return_value = False
        services.pair.side_effect = RuntimeError('pair failed')
        window = SimpleNamespace(_require=lambda: device, _services=services,
                                 _show=MagicMock(), device=device)
        with patch.object(gui.EarAWindow, '_post', side_effect=lambda w, cb: cb()):
            with self.assertRaisesRegex(RuntimeError, 'pair failed'):
                gui.EarAWindow._do_connect(window)
        services.pair.assert_called_once_with(device.address)
        device.connect_audio.assert_not_called()

    def test_health_uses_injected_provider_even_if_falsey(self):
        provider = MagicMock()
        provider.__bool__.return_value = False
        provider.inspect_services.return_value = {'bluetooth': None, 'audio': False}
        with patch.object(health, 'default_services', side_effect=AssertionError('unexpected default')):
            self.assertEqual(health.inspect_services(provider), {'bluetooth': None, 'audio': False})

    def test_discovery_preserves_flags_and_progress(self):
        devices = [{'address': 'AA', 'name': 'Buds', 'paired': True, 'compatible': True, 'rssi': -40}]
        progress = MagicMock()
        with patch('eara.bluez.scan_nothing_devices', return_value=devices) as scan, \
             patch('eara.bluez.paired_devices', return_value=devices):
            services = LinuxPlatformServices()
            self.assertEqual(services.scan_devices(7, progress), devices)
            self.assertEqual(services.paired_devices(), devices)
            scan.assert_called_once_with(7, progress=progress)

    def test_doctor_uses_same_health_result_as_gui(self):
        with patch.object(health, 'inspect_services', return_value={'bluetooth': True, 'audio': False}) as inspect, \
             patch.object(cli, '_device', side_effect=LookupError('no device')), \
             patch('subprocess.check_output', return_value=''), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(['doctor']), 1)
        inspect.assert_called_once()
        self.assertIsInstance(inspect.call_args.args[0], LinuxPlatformServices)
        self.assertIn('Audio service: unavailable', output.getvalue())

    @unittest.skipIf(gui is None, 'GTK unavailable')
    def test_gui_health_failure_unlocks_diagnostics_and_drops_close_result(self):
        for closed in (False, True):
            with self.subTest(closed=closed):
                window = SimpleNamespace(_services=MagicMock(), _shutting_down=False,
                                         btn_diagnostics=MagicMock(), _update_help_health=MagicMock())
                window._services.inspect_services.side_effect = RuntimeError('adapter failed')
                callbacks = []
                class ImmediateThread:
                    def __init__(self, target, daemon): self.target = target
                    def start(self): self.target()
                with patch.object(gui.threading, 'Thread', ImmediateThread), \
                     patch.object(gui.GLib, 'idle_add', side_effect=callbacks.append), \
                     patch.object(gui.traceback, 'print_exc'):
                    gui.EarAWindow._probe_services(window)
                window._shutting_down = closed
                callbacks[0]()
                self.assertFalse(window._health_checking)
                if closed:
                    window._update_help_health.assert_not_called()
                    window.btn_diagnostics.set_sensitive.assert_called_once_with(False)
                else:
                    self.assertEqual(window._health, {'bluetooth': None, 'audio': None})
                    window.btn_diagnostics.set_sensitive.assert_called_with(True)
                    window._update_help_health.assert_called_once()
