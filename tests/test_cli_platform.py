import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from eara import cli


class CliPlatformTests(unittest.TestCase):
    def test_codec_list_uses_device_audio_boundary(self):
        device = MagicMock()
        device.host_audio_state.return_value = {
            "codec": "aac",
            "codecs": [{"key": "aac", "label": "AAC", "profile": "a2dp"}],
        }
        output = io.StringIO()

        with patch.object(cli, "_device", return_value=device), redirect_stdout(output):
            result = cli.cmd_codec(argparse.Namespace(name="list"))

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["active"], "aac")
        device.host_audio_state.assert_called_once_with()

    def test_audio_command_routes_through_device(self):
        device = MagicMock()
        device.connected = True
        device.route_audio.return_value = {"ok": True}

        with patch.object(cli, "_device", return_value=device), redirect_stdout(io.StringIO()):
            result = cli.cmd_audio(argparse.Namespace(mode="hfp"))

        self.assertEqual(result, 0)
        device.route_audio.assert_called_once_with("hfp")

    def test_audio_command_stops_after_failed_connect(self):
        device = MagicMock()
        device.connected = False
        device.connect_audio.return_value = {"ok": False, "error": "offline"}

        with patch.object(cli, "_device", return_value=device), redirect_stdout(io.StringIO()):
            result = cli.cmd_audio(argparse.Namespace(mode="music"))

        self.assertEqual(result, 1)
        device.route_audio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
