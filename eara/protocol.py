"""Nothing X RFCOMM protocol used by Ear (a).

Frames go over Bluetooth Classic RFCOMM channel 15
(UUID aeac4a03-dff5-498f-843a-34487cf133eb).

Layout (little-endian):
  0x55 | ctrl u16=0x0160 | cmd_lo | dir | len u16 | seq | payload | crc16-arc
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator, Optional

SOF = 0x55
CTRL_WITH_CRC = 0x0160
RFCOMM_CHANNEL = 15
NT_LINK_UUID = "aeac4a03-dff5-498f-843a-34487cf133eb"
FAST_PAIR_UUID = "df21fe2c-2515-4fdb-8886-f12c4d67927c"

CMD_DEVICE_INFO = 0x06
CMD_BATTERY = 0x07
CMD_IED_GET = 0x0E
CMD_IED_SET = 0x04
CMD_GESTURE_GET = 0x18
CMD_GESTURE_SET = 0x03
CMD_ANC_SET = 0x0F
CMD_EQ_SET = 0x10
CMD_ANC_GET = 0x1E
CMD_EQ_GET = 0x1F
CMD_RING = 0x02  # SET dir; ear-web uses 0xF002
CMD_RING_LEGACY = 0x44
CMD_EAR_TIP = 0x14
CMD_EAR_TIP_RESULT = 0x0D
CMD_EAR_TIP_PREP = 0x0A
CMD_LATENCY_SET = 0x40
CMD_LATENCY_GET = 0x41
CMD_FIRMWARE = 0x42
CMD_CUSTOM_EQ_GET = 0x44
CMD_CUSTOM_EQ_SET = 0x41  # 0xF041 in some dumps; ear-web 61505=0xF041
CMD_ADVANCED_EQ_GET = 0x4C
CMD_ADVANCED_EQ_SET = 0x4F
CMD_BASS_GET = 0x4E
CMD_BASS_SET = 0x51
CMD_LISTENING_GET = 0x50
CMD_LISTENING_SET = 0x1D
CMD_PERSONAL_ANC_GET = 0x20
CMD_PERSONAL_ANC_SET = 0x11
CMD_CODEC_GET = 0x29

DIR_GET = 0xC0
DIR_SET = 0xF0
DIR_RESPONSE = 0x40
DIR_ACK = 0x70

ANC_MODES = {
    "high": 1,
    "mid": 2,
    "low": 3,
    "adaptive": 4,
    "off": 5,
    "transparency": 7,
}

ANC_FROM_WIRE = {v: k for k, v in ANC_MODES.items()}

EQ_PRESETS = {
    "balanced": 0,
    "more_bass": 1,
    "more_treble": 2,
    "voice": 3,
    "custom": 4,
}

EQ_FROM_WIRE = {v: k for k, v in EQ_PRESETS.items()}

# Gesture action bytes (same encoding as Nothing X / ear-web).
GESTURE_ACTIONS = {
    "no-action": 0x01,
    "skip-back": 0x08,
    "skip-forward": 0x09,
    "voice-assistant": 0x0B,
    "volume-up": 0x12,
    "volume-down": 0x13,
    "noise-control": 0x16,
    "noise-control-off-anc": 0x14,
    "noise-control-trans-off": 0x15,
    "noise-control-cycle": 0x0A,
}

GESTURE_TYPES = {
    "double-pinch": 0x02,
    "triple-pinch": 0x03,
    "pinch-hold": 0x07,
    "double-pinch-hold": 0x09,
}

GESTURE_SIDES = {"left": 0x02, "right": 0x03}

ACTION_FROM_WIRE = {value: key for key, value in GESTURE_ACTIONS.items()}

# GET 0x18 response layout (Ear 2 / Ear (a) / Ear 3 family).
GESTURE_READ_OFFSETS: dict[tuple[str, str], int] = {
    ("left", "double-pinch"): 4,
    ("left", "triple-pinch"): 12,
    ("left", "pinch-hold"): 20,
    ("left", "double-pinch-hold"): 28,
    ("right", "double-pinch"): 8,
    ("right", "triple-pinch"): 16,
    ("right", "pinch-hold"): 24,
    ("right", "double-pinch-hold"): 32,
}

# Factory defaults (Nothing X / Ear (2) family — Ear (a) matches).
DEFAULT_GESTURES: dict[str, dict[str, str]] = {
    "left": {
        "double-pinch": "skip-forward",
        "triple-pinch": "skip-back",
        "pinch-hold": "noise-control-cycle",
        "double-pinch-hold": "voice-assistant",
    },
    "right": {
        "double-pinch": "skip-forward",
        "triple-pinch": "skip-back",
        "pinch-hold": "voice-assistant",
        "double-pinch-hold": "noise-control-trans-off",
    },
}


def crc16_arc(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def build_frame(command: int, direction: int, payload: bytes = b"", seq: int = 1) -> bytes:
    wire = (command & 0xFF) | ((direction & 0xFF) << 8)
    body = struct.pack("<BHHH", SOF, CTRL_WITH_CRC, wire, len(payload))
    body += bytes([seq & 0xFF]) + payload
    return body + struct.pack("<H", crc16_arc(body))


@dataclass
class Frame:
    command: int
    direction: int
    seq: int
    payload: bytes
    raw: bytes


MAX_FRAME_BUFFER = 8192


class FrameParser:
    def __init__(self) -> None:
        self._buf = bytearray()

    def clear(self) -> None:
        self._buf.clear()

    def feed(self, data: bytes) -> None:
        self._buf.extend(data)
        if len(self._buf) > MAX_FRAME_BUFFER:
            # Drop oldest bytes — corrupted stream or hostile payload.
            del self._buf[:-MAX_FRAME_BUFFER]

    def frames(self) -> Iterator[Frame]:
        while True:
            try:
                start = self._buf.index(SOF)
            except ValueError:
                self._buf.clear()
                return
            if start:
                del self._buf[:start]
            if len(self._buf) < 8:
                return
            _sof, ctrl, command, length = struct.unpack_from("<BHHH", self._buf)
            crc_size = 2 if ctrl & 0x20 else 0
            total = 8 + length + crc_size
            if len(self._buf) < total:
                return
            raw = bytes(self._buf[:total])
            del self._buf[:total]
            payload = raw[8 : 8 + length]
            if crc_size and crc16_arc(raw[:-2]) != struct.unpack_from("<H", raw, total - 2)[0]:
                continue
            yield Frame(
                command=command & 0xFF,
                direction=(command >> 8) & 0xFF,
                seq=raw[7],
                payload=payload,
                raw=raw,
            )


def parse_battery(payload: bytes) -> dict[str, dict[str, object]]:
    """Parse GET battery payload: count, then (component, value) pairs."""
    out: dict[str, dict[str, object]] = {}
    if not payload:
        return out
    count = payload[0]
    names = {2: "left", 3: "right", 4: "case", 6: "headset"}

    def add(name: str, raw: int) -> None:
        level = raw & 0x7F
        if level > 100:
            return
        out[name] = {
            "level": level,
            "charging": bool(raw & 0x80),
            "available": True,
            "stale": False,
        }

    for i in range(count):
        offset = 1 + i * 2
        if offset + 1 >= len(payload):
            break
        component, raw = payload[offset], payload[offset + 1]
        if component == 0x01:
            add("left", raw)
            add("right", raw)
            continue
        name = names.get(component)
        if name:
            add(name, raw)
    return out


def merge_battery_cache(
    battery: dict[str, dict[str, object]],
    cache: dict[str, dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    """Keep last case reading — Nothing reports case only while the lid is open."""
    merged = dict(battery)
    new_cache = dict(cache)
    for key in ("left", "right", "case"):
        item = merged.get(key)
        if isinstance(item, dict) and item.get("available"):
            new_cache[key] = {
                "level": item.get("level", 0),
                "charging": bool(item.get("charging")),
                "available": True,
            }
    case = merged.get("case")
    if not isinstance(case, dict) or not case.get("available"):
        cached = new_cache.get("case")
        if cached:
            merged["case"] = {**cached, "available": True, "stale": True}
    elif isinstance(merged.get("case"), dict):
        merged["case"]["stale"] = False
    return merged, new_cache


def parse_anc(payload: bytes) -> Optional[str]:
    for offset in range(0, max(0, len(payload) - 1), 3):
        kind, value = payload[offset], payload[offset + 1]
        if kind == 1:
            return ANC_FROM_WIRE.get(value, "unknown")
    if len(payload) >= 2:
        return ANC_FROM_WIRE.get(payload[1], "unknown")
    return None


def parse_firmware(payload: bytes) -> str:
    text = payload.decode("ascii", errors="ignore").strip("\x00").strip()
    return text


def parse_serial(payload: bytes) -> str:
    """Device-info payload is CSV lines: device,type,value (type 4 = serial)."""
    text = payload.decode("ascii", errors="ignore")
    serial = ""
    for line in text.splitlines():
        parts = line.strip().split(",")
        if len(parts) == 3 and parts[1] == "4" and parts[2]:
            serial = parts[2].strip()
            break
    return serial


def parse_eq(payload: bytes) -> Optional[str]:
    if not payload:
        return None
    return EQ_FROM_WIRE.get(payload[0], f"unknown-{payload[0]}")


def parse_in_ear(payload: bytes) -> Optional[bool]:
    if len(payload) >= 3:
        return bool(payload[2])
    if payload:
        return bool(payload[-1])
    return None


def parse_latency(payload: bytes) -> Optional[bool]:
    if not payload:
        return None
    return payload[0] == 1


def parse_bass(payload: bytes) -> dict[str, object]:
    if len(payload) < 2:
        return {"enabled": False, "level": 0}
    return {"enabled": bool(payload[0]), "level": payload[1] / 2.0}


def parse_gestures(payload: bytes) -> dict[str, dict[str, str]]:
    """Decode gesture GET payload into side → type → action name."""
    out: dict[str, dict[str, str]] = {"left": {}, "right": {}}
    if len(payload) >= 33:
        for (side, gtype), offset in GESTURE_READ_OFFSETS.items():
            wire = payload[offset]
            action = ACTION_FROM_WIRE.get(wire)
            if action:
                out[side][gtype] = action
        if out["left"] or out["right"]:
            return out
    if not payload:
        return out
    count = payload[0]
    side_from_device = {0x01: "left", 0x02: "left", 0x03: "right"}
    type_from_wire = {value: key for key, value in GESTURE_TYPES.items()}
    for i in range(count):
        off = 1 + i * 4
        if off + 3 >= len(payload):
            break
        device = payload[off]
        gtype_wire = payload[off + 2]
        action_wire = payload[off + 3]
        side = side_from_device.get(device)
        gtype = type_from_wire.get(gtype_wire)
        action = ACTION_FROM_WIRE.get(action_wire)
        if side and gtype and action:
            out[side][gtype] = action
    return out


def merge_gestures(
    parsed: dict[str, dict[str, str]],
    defaults: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    base = defaults or DEFAULT_GESTURES
    merged = {side: dict(base.get(side, {})) for side in ("left", "right")}
    for side in ("left", "right"):
        for gtype, action in (parsed.get(side) or {}).items():
            if action and not str(action).startswith("unknown"):
                merged[side][gtype] = action
    for side in ("left", "right"):
        for gtype in GESTURE_TYPES:
            merged[side].setdefault(gtype, base.get(side, {}).get(gtype, "no-action"))
    return merged


def parse_ear_tip(payload: bytes) -> dict[str, str]:
    """Map L/R seal bytes: 0 = good seal, anything else = poor."""

    def side(value: int) -> str:
        return "good" if value == 0 else "poor"

    if len(payload) < 2:
        raise ValueError("ear tip result too short")
    return {"left": side(payload[0]), "right": side(payload[1])}


def format_ear_tip(result: dict[str, str], *, left: str, right: str, good: str, poor: str) -> str:
    labels = {"good": good, "poor": poor}

    def one(side_key: str, title: str) -> str:
        value = result.get(side_key, "unknown")
        return f"{title}: {labels.get(value, value)}"

    return f"{one('left', left)}, {one('right', right)}"


def _swap32(buf: bytearray) -> None:
    buf[0], buf[3] = buf[3], buf[0]
    buf[1], buf[2] = buf[2], buf[1]


def encode_eq_float(value: float, total: bool = False) -> bytes:
    packed = bytearray(struct.pack(">f", value))
    if value != 0.0 and packed[0] == 0 and packed[1] == 0 and packed[2] == 0:
        packed[3] = (packed[3] | 0x80) & 0xFF
    _swap32(packed)
    if total and value >= 0:
        return bytes([0x00, 0x00, 0x00, 0x80])
    return bytes(packed)


def decode_eq_float(raw: bytes) -> float:
    array = bytearray(raw[:4])
    _swap32(array)
    if array[0] == 0 and array[1] == 0 and array[2] == 0 and array[3] & 0x80:
        array[3] &= 0x7F
        return -struct.unpack(">f", bytes(array))[0]
    return struct.unpack(">f", bytes(array))[0]


def build_custom_eq_payload(bass: float, mid: float, treble: float) -> bytes:
    """3-band custom EQ as used by ear-web (bass/mid/treble in dB-ish floats)."""
    level = [mid, treble, bass]
    highest = max(level) / -1 if level else 0.0
    buf = bytearray(
        [
            0x03, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x75,
            0x44, 0xC3, 0xF5, 0x28, 0x3F, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC0, 0x5A,
            0x45, 0x00, 0x00, 0x80, 0x3F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0C,
            0x43, 0xCD, 0xCC, 0x4C, 0x3F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00,
        ]
    )
    encoded = encode_eq_float(highest, total=True)
    buf[1:5] = encoded
    for k, val in enumerate(level):
        encoded = encode_eq_float(val, total=False)
        start = 6 + k * 13
        buf[start : start + 4] = encoded
    return bytes(buf)


def parse_custom_eq(payload: bytes) -> list[float]:
    if len(payload) < 6 + 2 * 13 + 4:
        return [0.0, 0.0, 0.0]
    values = []
    for i in range(3):
        start = 6 + i * 13
        values.append(decode_eq_float(payload[start : start + 4]))
    # ear-web returns [treble?, bass, mid] then remaps to [bass, mid, treble]
    if len(values) == 3:
        return [values[2], values[0], values[1]]
    return values


GRAPHIC_HZ = (32, 64, 125, 250, 500, 1000, 2000, 4000)
_GRAPHIC_GROUPS = ((0, 1, 2), (3, 4, 5), (6, 7))
DEVICE_CODECS = {0: "sbc", 1: "lhdc", 2: "ldac", 3: "hires"}
CODEC_FROM_NAME = {v: k for k, v in DEVICE_CODECS.items()}


def graphic_to_three(gains: list[float]) -> tuple[float, float, float]:
    vals = list(gains) + [0.0] * 8
    def mean(idxs: tuple[int, ...]) -> float:
        return sum(vals[i] for i in idxs) / len(idxs)
    return mean(_GRAPHIC_GROUPS[0]), mean(_GRAPHIC_GROUPS[1]), mean(_GRAPHIC_GROUPS[2])


def three_to_graphic(bass: float, mid: float, treble: float) -> list[float]:
    out = [0.0] * 8
    for i in _GRAPHIC_GROUPS[0]:
        out[i] = bass
    for i in _GRAPHIC_GROUPS[1]:
        out[i] = mid
    for i in _GRAPHIC_GROUPS[2]:
        out[i] = treble
    return out


def parse_device_codec(payload: bytes) -> str:
    if not payload:
        return "unknown"
    return DEVICE_CODECS.get(payload[0], f"code-{payload[0]}")


LISTENING_MODES = {"normal": 0, "entertainment": 1, "work": 2}


def parse_listening(payload: bytes) -> Optional[str]:
    if not payload:
        return None
    wire = payload[0]
    for name, code in LISTENING_MODES.items():
        if code == wire:
            return name
    return f"mode-{wire}"


def clamp_eq_gain(value: float, lo: float = -12.0, hi: float = 12.0) -> float:
    return max(lo, min(hi, float(value)))


def parse_fast_pair_battery(payload: bytes) -> dict[str, dict[str, object]]:
    """Google Fast Pair message-stream battery (group 3, code 3)."""
    names = ("left", "right", "case")
    out: dict[str, dict[str, object]] = {}
    for i, name in enumerate(names):
        if i >= len(payload):
            break
        raw = payload[i]
        if (raw & 0x7F) == 0x7F:
            continue
        out[name] = {
            "level": raw & 0x7F,
            "charging": bool(raw & 0x80),
            "available": True,
        }
    return out
