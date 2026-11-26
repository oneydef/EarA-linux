"""Ear (3) fw 1.0.1.69 regression coverage from issue #29's readback."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from eara import bluez
from eara.models import model_from_name, model_from_serial
from eara.protocol import FrameParser, CMD_ADVANCED_EQ_SET, CMD_CUSTOM_EQ_SET, parse_custom_eq
from eara.session import Device


class Ear3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads((Path(__file__).parent / 'fixtures/ear3-readback.json').read_text())
        parser = FrameParser()
        for raw in fixture['frames']:
            parser.feed(bytes.fromhex(raw))
        frames = list(parser.frames())
        assert len(frames) == len(fixture['frames']), 'All captured frames must pass CRC validation'
        cls.responses = {frame.command: frame.payload for frame in frames}

    def test_model_name_wins_over_colliding_serial(self):
        for name in ('Nothing Ear (3)', 'Nothing Ear(3)'):
            model = Device._resolve_model('SH10000000000000', model_from_name(name))
            self.assertEqual(model.name, 'Nothing Ear (3)')
            self.assertEqual(model.family, 'ear3')
            self.assertTrue(model.bass_enhance)
            self.assertFalse(model.personalized_anc)
            self.assertFalse(model.listening_mode)

    def test_ambiguous_serial_does_not_claim_ear1(self):
        for serial in ('SH10000000000000', 'BH10000000000000'):
            self.assertEqual(model_from_serial(serial).base, 'unknown')
            self.assertEqual(Device._resolve_model(serial, model_from_name('Headphones')).base, 'unknown')
        self.assertEqual(model_from_serial('1000000000').base, 'B181')
        self.assertEqual(model_from_name('Nothing Ear').base, 'B171')

    def test_status_reads_captured_values_and_skips_unanswered_commands(self):
        responses = {**self.responses, 0x06: b'2,4,SH10000000000000\n'}
        device = Device('AA:BB:CC:DD:EE:FF', 'Nothing Ear (3)')
        with (
            patch.object(Device, 'connected', new_callable=PropertyMock, return_value=True),
            patch.object(device, 'host_audio_state', return_value={}),
            patch.object(device, 'open_control'),
            patch.object(device, 'close_control'),
            patch('eara.session.time.sleep'),
            patch.object(device, '_request', side_effect=lambda command, **kw: responses.get(command)) as request,
        ):
            status = device.status()
        self.assertTrue(status['protocol'])
        self.assertEqual(status['model']['name'], 'Nothing Ear (3)')
        self.assertEqual(status['firmware'], '1.0.1.69')
        self.assertEqual(status['anc'], 'high')
        self.assertEqual(status['eq'], 'balanced')
        self.assertEqual(status['battery']['left']['level'], 80)
        self.assertEqual(status['battery']['right']['level'], 95)
        self.assertEqual(status['device_codec'], 'sbc')
        self.assertTrue(status['advanced_eq'])
        self.assertTrue(status['in_ear'])
        self.assertTrue(status['latency'])
        self.assertEqual(status['bass'], {'enabled': True, 'level': 3.0})
        self.assertEqual(status['gestures']['left']['double-pinch'], 'volume-up')
        self.assertEqual(status['gestures']['right']['double-pinch'], 'skip-forward')
        expected = [2, 2, 2, 4 / 3, 4 / 3, 4 / 3, 1, 1]
        for actual, value in zip(status['graphic_eq'], expected):
            self.assertAlmostEqual(actual, value, places=6)
        commands = [call.args[0] for call in request.call_args_list]
        self.assertNotIn(0x20, commands)
        self.assertNotIn(0x50, commands)
        self.assertEqual(self.responses[0x4c], b'\x01')
        self.assertEqual(len(self.responses[0x44]), 109)

    def test_graphic_eq_uses_verified_enable_and_custom_payload_flow(self):
        device = Device('AA:BB:CC:DD:EE:FF', 'Nothing Ear (3)')
        with patch.object(device, '_session'), patch('eara.session.time.sleep'), patch.object(device, '_request', return_value=b'\x00') as request:
            device.set_graphic_eq([2, 2, 2, 1, 1, 2, 1, 1])
        self.assertEqual([c.args[0] for c in request.call_args_list], [CMD_ADVANCED_EQ_SET, CMD_CUSTOM_EQ_SET])
        self.assertEqual(request.call_args_list[0].args[2], b'\x01\x00')
        values = parse_custom_eq(request.call_args_list[1].args[2])
        for actual, value in zip(values, [2, 4 / 3, 1]):
            self.assertAlmostEqual(actual, value, places=6)
        self.assertTrue(all(c.kwargs['require'] for c in request.call_args_list))

    def test_no_ntapp_sdp_uses_channel_15_without_discarding_socket(self):
        result = SimpleNamespace(stdout='<record><uuid value="0x111e"/></record>', returncode=0)
        channel = MagicMock()
        with (
            patch.dict(bluez._RFCOMM_CHANNEL_CACHE, {}, clear=True),
            patch.object(bluez.subprocess, 'run', return_value=result),
            patch.object(bluez.socket, 'AF_BLUETOOTH', 31, create=True),
            patch.object(bluez.socket, 'BTPROTO_RFCOMM', 3, create=True),
            patch.object(bluez.socket, 'socket', return_value=channel) as factory,
        ):
            connected = bluez.open_rfcomm('AA:BB:CC:DD:EE:FF')
        self.assertIs(connected, channel)
        channel.connect.assert_called_once_with(('AA:BB:CC:DD:EE:FF', 15))
        factory.assert_called_once()
        channel.close.assert_not_called()
