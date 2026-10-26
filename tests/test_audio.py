import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from eara import audio


class AudioTests(unittest.TestCase):
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
