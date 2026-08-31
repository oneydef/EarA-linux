import socket
import unittest
from unittest.mock import MagicMock, patch

from eara.models import model_from_name, model_from_serial
from eara.session import Device


class SessionTests(unittest.TestCase):
    def test_resolve_model_prefers_serial_when_name_unknown(self):
        named = model_from_name("Bluetooth Audio")
        serial_model = model_from_serial("63123456")
        picked = Device._resolve_model("63123456", named)
        self.assertEqual(picked.base, serial_model.base)

    def test_resolve_model_sh_serial_keeps_name_when_known(self):
        named = model_from_name("Nothing Ear (a)")
        picked = Device._resolve_model("SH63ABCDEF", named)
        self.assertEqual(picked.base, "B162")

    def test_set_custom_eq_requires_response(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear (a)")
        with patch.object(device, "_session") as session_ctx:
            session_ctx.return_value.__enter__ = MagicMock(return_value=device)
            session_ctx.return_value.__exit__ = MagicMock(return_value=False)
            device._sock = MagicMock(spec=socket.socket)
            device._sock.recv.side_effect = socket.timeout()
            with patch.object(device, "_send", return_value=9):
                with self.assertRaises(RuntimeError):
                    device.set_custom_eq(0.0, 0.0, 0.0)

    def test_ring_both_uses_distinct_side_byte(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear (a)")
        with patch.object(device, "_session") as session_ctx:
            session_ctx.return_value.__enter__ = MagicMock(return_value=device)
            session_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with patch.object(device, "_request", return_value=b"\x00") as req:
                device.ring("both")
                req.assert_called_with(0x02, 0xF0, bytes([0x01, 0x01]))

    def test_request_tracks_sequence(self):
        device = Device("AA:BB:CC:DD:EE:FF", "Nothing Ear (a)")
        device._sock = MagicMock(spec=socket.socket)
        device._sock.recv.side_effect = socket.timeout()
        with patch.object(device, "_send", return_value=42) as send:
            with patch.object(device, "_recv_for", return_value=b"ok") as recv:
                out = device._request(0x07, require=False)
        send.assert_called_once()
        recv.assert_called_once()
        self.assertEqual(recv.call_args.kwargs.get("seq"), 42)
        self.assertEqual(out, b"ok")


if __name__ == "__main__":
    unittest.main()
