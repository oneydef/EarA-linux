"""Deterministic byte-stream contracts; no Bluetooth or audio services needed."""
import socket
import struct
import threading
import unittest
from collections import deque

from eara import operations
from eara.protocol import (
    CMD_BATTERY, DIR_GET, DIR_RESPONSE, FrameParser, MAX_FRAME_BUFFER,
    build_frame,
)
from eara.session import Device


class ScriptedChannel:
    def __init__(self, chunks):
        self.chunks = deque(chunks)
        self.sent = []
        self.closed = False

    def settimeout(self, value):
        assert value > 0

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, size):
        item = self.chunks.popleft() if self.chunks else b""
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        self.closed = True


class StreamTransport:
    def __init__(self, channel):
        self.channel = channel

    def is_connected(self, address):
        return True

    def open_channel(self, address):
        return self.channel


class ProtocolStreamTests(unittest.TestCase):
    def test_every_split_and_bytewise_delivery(self):
        wire = build_frame(CMD_BATTERY, DIR_RESPONSE, b"\x02\x02\x28\x03\x50", seq=1)
        deliveries = [[wire[:i], wire[i:]] for i in range(1, len(wire))]
        deliveries.append([bytes([byte]) for byte in wire])
        for chunks in deliveries:
            with self.subTest(chunks=len(chunks), first=len(chunks[0])):
                channel = ScriptedChannel(chunks)
                device = Device("AA:BB:CC:DD:EE:FF", transport=StreamTransport(channel))
                device._seq = 0
                with device._session():
                    self.assertEqual(device._request(CMD_BATTERY, require=True), b"\x02\x02\x28\x03\x50")
                self.assertTrue(channel.closed)
                self.assertEqual(len(channel.sent), 1)

    def test_late_sequence_wrong_command_and_direction_are_ignored(self):
        wire = b"".join([
            build_frame(CMD_BATTERY, DIR_RESPONSE, b"old", seq=250),
            build_frame(0x42, DIR_RESPONSE, b"firmware", seq=1),
            build_frame(CMD_BATTERY, DIR_GET, b"echo", seq=1),
            build_frame(CMD_BATTERY, DIR_RESPONSE, b"current", seq=1),
        ])
        channel = ScriptedChannel([socket.timeout(), wire])
        device = Device("AA:BB:CC:DD:EE:FF", transport=StreamTransport(channel))
        device._seq = 0
        with device._session():
            self.assertEqual(device._request(CMD_BATTERY, require=True), b"current")

    def test_eof_and_socket_error_fail_required_request_and_close(self):
        for end in (b"", OSError("link lost")):
            with self.subTest(end=end):
                channel = ScriptedChannel([end])
                device = Device("AA:BB:CC:DD:EE:FF", transport=StreamTransport(channel))
                with self.assertRaisesRegex(RuntimeError, "did not respond"):
                    with device._session():
                        device._request(CMD_BATTERY, require=True)
                self.assertTrue(channel.closed)
                self.assertIsNone(device._sock)

    def test_corrupt_crc_then_valid_frame(self):
        bad = bytearray(build_frame(CMD_BATTERY, DIR_RESPONSE, b"bad"))
        bad[-1] ^= 0x01
        parser = FrameParser()
        parser.feed(b"noise" + bad + build_frame(CMD_BATTERY, DIR_RESPONSE, b"good"))
        self.assertEqual([f.payload for f in parser.frames()], [b"good"])

    def test_impossible_length_does_not_block_following_frame(self):
        for length in (MAX_FRAME_BUFFER, 65535):
            with self.subTest(length=length):
                parser = FrameParser()
                parser.feed(struct.pack("<BHHHB", 0x55, 0x0160, 0x4007, length, 1))
                parser.feed(build_frame(CMD_BATTERY, DIR_RESPONSE, b"good"))
                self.assertEqual([f.payload for f in parser.frames()], [b"good"])

    def test_largest_supported_frame_still_parses(self):
        payload = b"x" * (MAX_FRAME_BUFFER - 10)
        wire = build_frame(CMD_BATTERY, DIR_RESPONSE, payload)
        parser = FrameParser()
        parser.feed(wire[:8])
        self.assertEqual(list(parser.frames()), [])
        parser.feed(wire[8:])
        self.assertEqual([f.payload for f in parser.frames()], [payload])

    def test_cancellation_during_receive_discards_reply_and_closes_channel(self):
        cancelled = threading.Event()

        class CancellingChannel(ScriptedChannel):
            def recv(self, size):
                cancelled.set()
                return build_frame(CMD_BATTERY, DIR_RESPONSE, b"late", seq=2)

        channel = CancellingChannel([])
        device = Device("AA:BB:CC:DD:EE:FF", transport=StreamTransport(channel))
        with self.assertRaises(operations.Cancelled):
            with operations.scope(5, cancelled):
                with device._session():
                    device._request(CMD_BATTERY, require=True)
                    self.fail("Cancelled request returned success")
        self.assertTrue(channel.closed)
        self.assertIsNone(device._sock)

    def test_cancellation_does_not_deliver_buffered_response(self):
        channel = ScriptedChannel([])
        device = Device("AA:BB:CC:DD:EE:FF", transport=StreamTransport(channel))
        cancelled = threading.Event()
        for receive in (
            lambda: device._recv_for(CMD_BATTERY, seq=1),
            lambda: device._recv_until(lambda frame: frame.payload),
        ):
            cancelled.clear()
            with self.subTest(receive=receive):
                with self.assertRaises(operations.Cancelled):
                    with operations.scope(5, cancelled):
                        with device._session():
                            device._parser.feed(build_frame(CMD_BATTERY, DIR_RESPONSE, b"stale"))
                            cancelled.set()
                            receive()
                            self.fail("Cancelled operation returned a buffered response")
                self.assertIsNone(device._sock)
