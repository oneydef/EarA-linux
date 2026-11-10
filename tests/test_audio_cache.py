import threading
import unittest
from unittest.mock import MagicMock, patch

from eara.platforms.base import HostAudioState
from eara.platforms.cache import AudioStateCache
from eara.session import Device
from eara import operations


class AudioCacheTests(unittest.TestCase):
    def test_unavailable_snapshot_is_retried(self):
        backend = MagicMock()
        backend.state.side_effect = [HostAudioState(available=False), HostAudioState(profile='a2dp')]
        cache = AudioStateCache()
        self.assertFalse(cache.get(backend, 'AA')['available'])
        self.assertEqual(cache.get(backend, 'AA')['profile'], 'a2dp')
        self.assertEqual(backend.state.call_count, 2)

    def test_cancelled_read_does_not_fill_cache(self):
        backend = MagicMock()
        cancel = threading.Event()
        def cancelled_read(address):
            cancel.set()
            return HostAudioState(profile='old')
        backend.state.side_effect = cancelled_read
        cache = AudioStateCache()
        with self.assertRaises(operations.Cancelled):
            with operations.scope(5, cancel):
                cache.get(backend, 'AA')
        backend.state.side_effect = None
        backend.state.return_value = HostAudioState(profile='new')
        self.assertEqual(cache.get(backend, 'AA')['profile'], 'new')
        self.assertEqual(backend.state.call_count, 2)

    def make_device(self):
        backend = MagicMock()
        backend.state.return_value = HostAudioState(profile='a2dp', codecs=[{'key': 'aac'}])
        backend.ensure_music.return_value = {'ok': True}
        backend.ensure_calls.return_value = {'ok': True}
        backend.set_codec.return_value = {'ok': False}
        transport = MagicMock()
        transport.is_connected.return_value = True
        transport.has_audio_sink.return_value = True
        return Device('AA:BB:CC:DD:EE:FF', transport=transport, audio_backend=backend), backend

    def test_reuse_expiry_and_explicit_refresh(self):
        device, backend = self.make_device()
        now = [100.0]
        with patch('eara.platforms.cache.time.monotonic', side_effect=lambda: now[0]):
            first = device.host_audio_state()
            first['codecs'][0]['key'] = 'changed'
            self.assertEqual(device.host_audio_state()['codecs'][0]['key'], 'aac')
            self.assertEqual(backend.state.call_count, 1)
            now[0] += 3
            device.host_audio_state()
            self.assertEqual(backend.state.call_count, 2)
            device.host_audio_state(refresh=True)
            self.assertEqual(backend.state.call_count, 3)

    def test_audio_mutations_invalidate_even_when_unsuccessful(self):
        for method, args in [('route_audio', ('music',)), ('set_codec', ('ldac',)),
                             ('connect_audio', ()), ('reset_connection', ()),
                             ('disconnect_audio', ()), ('shutdown', ())]:
            with self.subTest(method=method), patch('eara.session.time.sleep'):
                device, backend = self.make_device()
                device.host_audio_state()
                getattr(device, method)(*args)
                device.host_audio_state()
                self.assertEqual(backend.state.call_count, 2)

    def test_status_can_force_fresh_host_state(self):
        device, backend = self.make_device()
        device.transport.is_connected.return_value = False
        device.status()
        device.status()
        self.assertEqual(backend.state.call_count, 1)
        device.status(refresh_audio=True)
        self.assertEqual(backend.state.call_count, 2)

    def test_exception_invalidates_and_failed_reads_are_not_cached(self):
        device, backend = self.make_device()
        device.host_audio_state()
        backend.ensure_music.side_effect = RuntimeError('route failed')
        with self.assertRaises(RuntimeError):
            device.route_audio()
        backend.state.side_effect = [RuntimeError('offline'), HostAudioState(profile='new')]
        self.assertFalse(device.host_audio_state()['available'])
        self.assertEqual(device.host_audio_state()['profile'], 'new')
        self.assertEqual(backend.state.call_count, 3)

    def test_other_device_or_backend_cannot_reuse_snapshot(self):
        device, backend = self.make_device()
        device.host_audio_state()
        device.address = '11:22:33:44:55:66'
        device.host_audio_state()
        self.assertEqual(backend.state.call_count, 2)
        other = MagicMock()
        other.state.return_value = HostAudioState(profile='other')
        device.audio_backend = other
        self.assertEqual(device.host_audio_state()['profile'], 'other')

    def test_inflight_read_cannot_refill_invalidated_cache(self):
        cache = AudioStateCache()
        started, release = threading.Event(), threading.Event()
        backend = MagicMock()
        def delayed(address):
            started.set()
            if not release.wait(3):
                raise RuntimeError('test synchronization timed out')
            return HostAudioState(profile='old')
        backend.state.side_effect = delayed
        worker = threading.Thread(target=lambda: cache.get(backend, 'AA'))
        worker.start()
        try:
            self.assertTrue(started.wait(3))
            cache.invalidate()
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        backend.state.side_effect = None
        backend.state.return_value = HostAudioState(profile='new')
        self.assertEqual(cache.get(backend, 'AA')['profile'], 'new')
        self.assertEqual(backend.state.call_count, 2)
