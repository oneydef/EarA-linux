import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from eara import audio


class AudioTests(unittest.TestCase):
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
