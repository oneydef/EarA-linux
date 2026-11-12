import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from eara import audio


class AudioTests(unittest.TestCase):
    def test_music_rejection_does_not_accept_remaining_hfp_sink(self):
        with patch.object(audio, 'ensure_bluez_card', return_value=True), \
             patch.object(audio, 'set_profile', return_value=False), \
             patch.object(audio, 'wait_for_sink', return_value='old-hfp-sink') as sink, \
             patch.object(audio, 'set_default_sink') as default, \
             patch.object(audio, 'move_streams_to_default') as move:
            result = audio.ensure_music_audio('AA')
        self.assertFalse(result['ok'])
        self.assertIn('A2DP', result['error'])
        sink.assert_not_called()
        default.assert_not_called()
        move.assert_not_called()

    def test_music_default_failure_does_not_move_streams(self):
        with patch.object(audio, 'ensure_bluez_card', return_value=True), \
             patch.object(audio, 'set_profile', return_value=True), \
             patch.object(audio, 'wait_for_sink', return_value='a2dp-sink'), \
             patch.object(audio, 'set_default_sink', return_value=False), \
             patch.object(audio, 'move_streams_to_default') as move:
            self.assertFalse(audio.ensure_music_audio('AA')['ok'])
        move.assert_not_called()

    def test_music_fallback_profile_routes_successfully(self):
        with patch.object(audio, 'ensure_bluez_card', return_value=True), \
             patch.object(audio, 'set_profile', side_effect=[False, True]) as profile, \
             patch.object(audio, 'wait_for_sink', return_value='a2dp-sink'), \
             patch.object(audio, 'set_default_sink', return_value=True), \
             patch.object(audio, 'active_profile', return_value='a2dp-sink'), \
             patch.object(audio, 'move_streams_to_default') as move:
            result = audio.ensure_music_audio('AA')
        self.assertTrue(result['ok'])
        self.assertEqual(result['profile'], 'a2dp-sink')
        self.assertEqual(profile.call_count, 2)
        move.assert_called_once()

    def test_find_sink_accepts_pipewire_colon_mac(self):
        sinks = "42\tbluez_output.3C:B0:ED:D3:DC:40.1\tPipeWire\n"
        with patch.object(audio, "_pactl", return_value=sinks):
            self.assertEqual(
                audio.find_sink("3C:B0:ED:D3:DC:40"),
                "bluez_output.3C:B0:ED:D3:DC:40.1",
            )

    def test_find_sink_accepts_pulseaudio_underscore_mac(self):
        sinks = "42\tbluez_output.3C_B0_ED_D3_DC_40.a2dp-sink\tPipeWire\n"
        with patch.object(audio, "_pactl", return_value=sinks):
            self.assertEqual(
                audio.find_sink("3C:B0:ED:D3:DC:40"),
                "bluez_output.3C_B0_ED_D3_DC_40.a2dp-sink",
            )

    def test_active_codec_accepts_pipewire_colon_mac(self):
        sinks = (
            "Sink #718\n"
            "\tName: bluez_output.3C:B0:ED:D3:DC:40\n"
            "\tProperties:\n"
            "\t\tapi.bluez5.codec = \"aac\"\n"
        )
        with patch.object(audio, "_pactl", return_value=sinks):
            self.assertEqual(audio.active_codec("3C:B0:ED:D3:DC:40"), "aac")

    def test_reload_skipped_without_force(self):
        with patch("eara.audio.subprocess.run") as run:
            audio.reload_bluetooth_modules(force=False)
            run.assert_not_called()

    def test_pulse_override_appends_existing_config(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            pulse_dir = home / ".config" / "pulse"
            pulse_dir.mkdir(parents=True)
            target = pulse_dir / "default.pa"
            target.write_text("load-module module-null-sink\n", encoding="utf-8")
            with patch.object(audio.Path, "home", return_value=home):
                audio._write_pulse_override()
                text = target.read_text(encoding="utf-8")
            self.assertIn("module-null-sink", text)
            self.assertIn("eara: keep A2DP", text)


if __name__ == "__main__":
    unittest.main()
