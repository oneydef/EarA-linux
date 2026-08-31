"""High-level Nothing / CMF companion session."""

from __future__ import annotations

import socket
import threading
import time
from typing import Optional

from eara import audio, bluez
from eara.models import MODELS_BY_BASE, Model, model_from_name, model_from_serial
from eara.protocol import (
    ANC_MODES,
    CMD_ADVANCED_EQ_GET,
    CMD_ADVANCED_EQ_SET,
    CMD_ANC_GET,
    CMD_ANC_SET,
    CMD_BATTERY,
    CMD_BASS_GET,
    CMD_BASS_SET,
    CMD_CODEC_GET,
    CMD_CUSTOM_EQ_GET,
    CMD_CUSTOM_EQ_SET,
    CMD_DEVICE_INFO,
    CMD_EAR_TIP,
    CMD_EAR_TIP_PREP,
    CMD_EAR_TIP_RESULT,
    CMD_EQ_GET,
    CMD_EQ_SET,
    CMD_FIRMWARE,
    CMD_GESTURE_GET,
    CMD_GESTURE_SET,
    CMD_IED_GET,
    CMD_IED_SET,
    CMD_LATENCY_GET,
    CMD_LATENCY_SET,
    CMD_LISTENING_GET,
    CMD_LISTENING_SET,
    CMD_PERSONAL_ANC_GET,
    CMD_PERSONAL_ANC_SET,
    CMD_RING,
    CMD_RING_LEGACY,
    DIR_GET,
    DIR_RESPONSE,
    DIR_ACK,
    DIR_SET,
    EQ_PRESETS,
    GESTURE_ACTIONS,
    GESTURE_SIDES,
    GESTURE_TYPES,
    LISTENING_MODES,
    FrameParser,
    build_custom_eq_payload,
    build_frame,
    clamp_eq_gain,
    graphic_to_three,
    merge_gestures,
    merge_battery_cache,
    parse_anc,
    parse_bass,
    parse_battery,
    parse_custom_eq,
    parse_device_codec,
    parse_ear_tip,
    parse_eq,
    parse_firmware,
    parse_gestures,
    parse_in_ear,
    parse_latency,
    parse_listening,
    three_to_graphic,
    parse_serial,
)


class Device:
    def __init__(self, address: str = "", name: str = "") -> None:
        self.address = address.upper()
        self.name = name or "Compatible earbuds"
        self.model: Model = model_from_name(self.name)
        self._sock: Optional[socket.socket] = None
        self._parser = FrameParser()
        self._seq = 1
        self._battery_cache: dict[str, dict[str, object]] = {}
        self._lock = threading.RLock()

    @classmethod
    def discover(cls, preferred: str = "") -> "Device":
        device = bluez.find_nothing_device(preferred)
        if not device:
            raise LookupError("No paired compatible audio device found")
        return cls(device["address"], device["name"])

    @staticmethod
    def _resolve_model(serial: str, named: Model) -> Model:
        """Pick catalog entry from serial prefix and Bluetooth name."""
        if serial.startswith(("SH", "BH")):
            # SH/BH serials: first digit pair often mis-identifies Ear (a) as Ear (1).
            return named if named.base != "unknown" else model_from_serial(serial)
        serial_model = model_from_serial(serial)
        if serial_model.base != "unknown":
            if named.base == "unknown" or serial_model.base == named.base:
                return serial_model
        return named if named.base != "unknown" else serial_model

    @property
    def connected(self) -> bool:
        return bool(self.address) and bluez.is_connected(self.address)

    def connect_audio(self, with_mic: bool = False, attempts: int = 5) -> dict[str, object]:
        if not self.address:
            raise RuntimeError("No Bluetooth address")
        fn = audio.ensure_call_audio if with_mic else audio.ensure_music_audio
        last: dict[str, object] = {"ok": False, "error": "Connect failed"}

        for attempt in range(attempts):
            self.close_control()
            try:
                bluez.trust_and_connect(
                    self.address,
                    timeout=45,
                    scan=True,
                    max_rounds=4 if attempt == 0 else 5,
                )
            except TimeoutError as exc:
                last = {"ok": False, "error": str(exc), "attempt": attempt + 1}
                bluez.dbus_disconnect(self.address)
                audio.reload_bluetooth_modules(force=True)
                time.sleep(1.5 + attempt)
                continue

            time.sleep(0.8)
            result = fn(self.address)
            if result.get("ok"):
                result["attempt"] = attempt + 1
                return result

            last = dict(result)
            last["attempt"] = attempt + 1
            audio.reload_bluetooth_modules(force=True)
            bluez.dbus_disconnect(self.address)
            time.sleep(1.2 + attempt * 0.6)

        err = str(last.get("error") or "Connect failed")
        return {
            "ok": False,
            "error": (
                f"{err} (tried {attempts} times). "
                "Take both buds out of the case, disable phone Bluetooth "
                "(dual connection), then Connect or Reset again."
            ),
            "attempt": attempts,
        }

    def reset_connection(self) -> dict[str, object]:
        if not self.address:
            raise RuntimeError("No Bluetooth address")
        self.close_control()
        bluez.reset_link(self.address)
        time.sleep(1.0)
        result = audio.ensure_music_audio(self.address)
        if not result.get("ok"):
            audio.reload_bluetooth_modules(force=True)
            time.sleep(1.0)
            result = audio.ensure_music_audio(self.address)
        return result

    def disconnect_audio(self) -> None:
        self.close_control()
        if self.address:
            bluez.disconnect(self.address)

    def shutdown(self) -> None:
        """Drop RFCOMM, disconnect earbuds, and power off the BT adapter."""
        self.close_control()
        if self.address:
            try:
                bluez.disconnect(self.address)
            except Exception:
                pass
        try:
            bluez.power_off()
        except Exception:
            pass

    def open_control(self, *, probe_device: bool = False) -> None:
        with self._lock:
            if self._sock is not None:
                if probe_device:
                    self._request(CMD_DEVICE_INFO, DIR_GET)
                return
            if not self.connected:
                for attempt in range(4):
                    try:
                        bluez.trust_and_connect(self.address, timeout=35, scan=True, max_rounds=3)
                        break
                    except TimeoutError:
                        if attempt >= 3:
                            raise
                        time.sleep(1.5 + attempt)
                time.sleep(0.5)
            try:
                self._sock = bluez.open_rfcomm(self.address)
            except OSError as exc:
                raise RuntimeError(bluez.permission_hint(exc)) from exc
            self._parser = FrameParser()
            if probe_device:
                self._request(CMD_DEVICE_INFO, DIR_GET)

    def close_control(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
            self._sock = None

    def _next_seq(self) -> int:
        self._seq = (self._seq % 250) + 1
        return self._seq

    def _flush_parser(self) -> None:
        self._parser.clear()

    def _send(self, command: int, direction: int, payload: bytes = b"", seq: Optional[int] = None) -> int:
        assert self._sock is not None
        wire_seq = self._next_seq() if seq is None else seq
        self._sock.sendall(build_frame(command, direction, payload, wire_seq))
        return wire_seq

    def _recv_for(self, command: int, timeout: float = 1.2, seq: Optional[int] = None) -> Optional[bytes]:
        assert self._sock is not None
        deadline = time.monotonic() + timeout
        wanted = command & 0xFF
        while time.monotonic() < deadline:
            for frame in self._parser.frames():
                if frame.command != wanted or frame.direction not in (DIR_RESPONSE, DIR_ACK):
                    continue
                if seq is not None and frame.seq != seq:
                    continue
                return frame.payload
            remaining = max(0.05, deadline - time.monotonic())
            self._sock.settimeout(min(0.25, remaining))
            try:
                chunk = self._sock.recv(512)
            except socket.timeout:
                continue
            except OSError:
                return None
            if not chunk:
                return None
            self._parser.feed(chunk)
        return None

    def _recv_until(self, match, timeout: float = 1.2) -> Optional[bytes]:
        assert self._sock is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for frame in self._parser.frames():
                picked = match(frame)
                if picked is not None:
                    return picked
            remaining = max(0.05, deadline - time.monotonic())
            self._sock.settimeout(min(0.25, remaining))
            try:
                chunk = self._sock.recv(512)
            except socket.timeout:
                continue
            except OSError:
                return None
            if not chunk:
                return None
            self._parser.feed(chunk)
        return None

    def _request(
        self,
        command: int,
        direction: int = DIR_GET,
        payload: bytes = b"",
        timeout: float = 1.2,
        *,
        require: bool = False,
    ) -> Optional[bytes]:
        with self._lock:
            self._flush_parser()
            seq = self._send(command, direction, payload)
            result = self._recv_for(command, timeout=timeout, seq=seq)
            if require and result is None:
                raise RuntimeError(f"Device did not respond to command 0x{command:02x}")
            return result

    def _session(self, *, probe_device: bool = False):
        class _Guard:
            def __init__(self, outer: Device, probe: bool) -> None:
                self.outer = outer
                self.probe = probe

            def __enter__(self) -> Device:
                self.outer.open_control(probe_device=self.probe)
                return self.outer

            def __exit__(self, *args) -> None:
                self.outer.close_control()

        return _Guard(self, probe_device)

    def status(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "address": self.address,
            "bt_connected": self.connected,
            "protocol": False,
            "model": self.model.as_dict(),
            "serial": None,
            "anc": None,
            "eq": None,
            "custom_eq": None,
            "advanced_eq": None,
            "bass": None,
            "battery": {},
            "latency": None,
            "in_ear": None,
            "firmware": None,
            "gestures": [],
            "listening": None,
            "personalized_anc": None,
            "audio": {
                "sink": audio.find_sink(self.address) if self.address else None,
                "source": audio.find_source(self.address) if self.address else None,
                "profile": audio.active_profile(self.address) if self.address else "",
                "codec": audio.active_codec(self.address) if self.address else "",
                "codecs": audio.list_a2dp_codecs(self.address) if self.address else [],
            },
            "graphic_eq": None,
            "device_codec": None,
            "error": "",
        }
        if not self.connected:
            return result
        try:
            self.open_control(probe_device=True)
        except RuntimeError as exc:
            result["error"] = str(exc)
            return result
        try:
            info = self._request(CMD_DEVICE_INFO)
            if info is not None:
                serial = parse_serial(info)
                result["serial"] = serial or None
                if serial:
                    named = model_from_name(self.name)
                    self.model = self._resolve_model(serial, named)
                    result["model"] = self.model.as_dict()
            batt = self._request(CMD_BATTERY)
            if batt is not None:
                result["protocol"] = True
                battery = parse_battery(batt)
                case = battery.get("case")
                if not isinstance(case, dict) or not case.get("available"):
                    time.sleep(0.7)
                    batt_retry = self._request(CMD_BATTERY, timeout=1.0)
                    if batt_retry is not None:
                        retry = parse_battery(batt_retry)
                        if isinstance(retry.get("case"), dict) and retry["case"].get("available"):
                            battery = retry
                        else:
                            for key in ("left", "right", "case"):
                                item = retry.get(key)
                                if isinstance(item, dict) and item.get("available"):
                                    battery[key] = item
                result["battery"], self._battery_cache = merge_battery_cache(
                    battery, self._battery_cache
                )
            if self.model.anc:
                anc = self._request(CMD_ANC_GET)
                if anc is not None:
                    result["anc"] = parse_anc(anc)
            if self.model.eq_presets:
                eq = self._request(CMD_EQ_GET)
                if eq is not None:
                    result["eq"] = parse_eq(eq)
            if self.model.custom_eq:
                ceq = self._request(CMD_CUSTOM_EQ_GET)
                if ceq is not None:
                    result["custom_eq"] = parse_custom_eq(ceq)
                    ceq_vals = result["custom_eq"]
                    if isinstance(ceq_vals, list) and len(ceq_vals) >= 3:
                        result["graphic_eq"] = three_to_graphic(ceq_vals[0], ceq_vals[1], ceq_vals[2])
            codec = self._request(CMD_CODEC_GET, timeout=0.45)
            if codec is not None:
                result["device_codec"] = parse_device_codec(codec)
            if self.model.advanced_eq:
                adv = self._request(CMD_ADVANCED_EQ_GET)
                if adv is not None and adv:
                    result["advanced_eq"] = bool(adv[0])
            if self.model.bass_enhance:
                bass = self._request(CMD_BASS_GET)
                if bass is not None:
                    result["bass"] = parse_bass(bass)
            if self.model.in_ear:
                ied = self._request(CMD_IED_GET)
                if ied is not None:
                    result["in_ear"] = parse_in_ear(ied)
            if self.model.low_latency:
                latency = self._request(CMD_LATENCY_GET)
                if latency is not None:
                    result["latency"] = parse_latency(latency)
            if self.model.personalized_anc:
                panc = self._request(CMD_PERSONAL_ANC_GET)
                if panc is not None and panc:
                    result["personalized_anc"] = bool(panc[0])
            if self.model.listening_mode:
                listening = self._request(CMD_LISTENING_GET)
                if listening is not None:
                    result["listening"] = parse_listening(listening)
            fw = self._request(CMD_FIRMWARE)
            if fw is not None:
                result["firmware"] = parse_firmware(fw)
            if self.model.gestures:
                g = self._request(CMD_GESTURE_GET)
                if g is not None:
                    result["gestures"] = merge_gestures(parse_gestures(g))
                else:
                    result["gestures"] = merge_gestures({"left": {}, "right": {}})
        finally:
            self.close_control()
        return result

    def set_anc(self, mode: str) -> None:
        if mode not in ANC_MODES:
            raise ValueError(f"Unknown ANC mode: {mode}")
        with self._session():
            payload = bytes([1, ANC_MODES[mode], 0])
            self._request(CMD_ANC_SET, DIR_SET, payload, require=True)
            time.sleep(0.2)

    def set_eq(self, preset: str) -> None:
        if preset not in EQ_PRESETS:
            raise ValueError(f"Unknown EQ preset: {preset}")
        with self._session():
            self._request(CMD_EQ_SET, DIR_SET, bytes([EQ_PRESETS[preset], 0]), require=True)
            time.sleep(0.2)

    def set_custom_eq(self, bass: float, mid: float, treble: float) -> None:
        bass = clamp_eq_gain(bass)
        mid = clamp_eq_gain(mid)
        treble = clamp_eq_gain(treble)
        with self._session():
            payload = build_custom_eq_payload(bass, mid, treble)
            self._request(CMD_CUSTOM_EQ_SET, DIR_SET, payload, require=True)
            time.sleep(0.2)

    def set_graphic_eq(self, gains: list[float]) -> None:
        clamped = [clamp_eq_gain(g) for g in gains]
        bass, mid, treble = graphic_to_three(clamped)
        with self._session():
            self._request(CMD_ADVANCED_EQ_SET, DIR_SET, bytes([1, 0]), require=True)
            self._request(
                CMD_CUSTOM_EQ_SET,
                DIR_SET,
                build_custom_eq_payload(bass, mid, treble),
                require=True,
            )
            time.sleep(0.2)

    def set_codec(self, name: str) -> dict[str, object]:
        from eara.protocol import CODEC_FROM_NAME

        host = audio.set_host_codec(self.address, name)
        code = CODEC_FROM_NAME.get(name.lower().replace("-", "_"))
        if code is not None:
            try:
                with self._session():
                    self._request(CMD_CODEC_GET, DIR_SET, bytes([code]), require=True)
            except (RuntimeError, OSError, socket.error) as exc:
                host = dict(host)
                host["device_codec_error"] = str(exc)
        return host

    def set_advanced_eq(self, enabled: bool) -> None:
        with self._session():
            self._request(CMD_ADVANCED_EQ_SET, DIR_SET, bytes([1 if enabled else 0, 0]), require=True)

    def set_bass(self, enabled: bool, level: float = 1.0) -> None:
        with self._session():
            wire_level = int(max(0, min(5, level)) * 2)
            self._request(CMD_BASS_SET, DIR_SET, bytes([1 if enabled else 0, wire_level]), require=True)

    def set_latency(self, enabled: bool) -> None:
        with self._session():
            self._request(CMD_LATENCY_SET, DIR_SET, bytes([1 if enabled else 2, 0]), require=True)
            time.sleep(0.2)

    def set_in_ear_detection(self, enabled: bool) -> None:
        with self._session():
            self._request(CMD_IED_SET, DIR_SET, bytes([1, 1, 1 if enabled else 0]), require=True)

    def set_personalized_anc(self, enabled: bool) -> None:
        with self._session():
            self._request(CMD_PERSONAL_ANC_SET, DIR_SET, bytes([1 if enabled else 0]), require=True)

    def set_listening_mode(self, mode: str) -> None:
        if mode not in LISTENING_MODES:
            raise ValueError(f"Unknown listening mode: {mode}")
        with self._session():
            self._request(
                CMD_LISTENING_SET,
                DIR_SET,
                bytes([LISTENING_MODES[mode], 0]),
                require=True,
            )

    def set_gesture(self, side: str, gtype: str, action: str) -> None:
        if side not in GESTURE_SIDES or gtype not in GESTURE_TYPES or action not in GESTURE_ACTIONS:
            raise ValueError("Invalid gesture (side|type|action)")
        with self._session():
            payload = bytes(
                [
                    0x01,
                    GESTURE_SIDES[side],
                    0x01,
                    GESTURE_TYPES[gtype],
                    GESTURE_ACTIONS[action],
                ]
            )
            self._request(CMD_GESTURE_SET, DIR_SET, payload, require=True)

    def ear_tip_test(self) -> dict[str, str]:
        if not self.model.ear_tip_fit:
            raise RuntimeError("fit_unsupported")
        with self._session():
            self._request(CMD_EAR_TIP_PREP, DIR_GET, b"", timeout=0.8)
            self._send(CMD_EAR_TIP, DIR_SET, bytes([0x01]))
            payload = self._recv_until(
                lambda frame: (
                    frame.payload[:2]
                    if frame.command == CMD_EAR_TIP_RESULT
                    and frame.direction in (DIR_RESPONSE, DIR_ACK)
                    and len(frame.payload) >= 2
                    else None
                ),
                timeout=25.0,
            )
            if payload is None:
                raise RuntimeError("fit_timeout")
            return parse_ear_tip(payload)

    def ring(self, which: str = "both") -> None:
        # Modern ring: side 0x01 = both, 0x02 = left, 0x03 = right.
        mapping = {
            "off": (0x03, 0x00),
            "left": (0x02, 0x01),
            "right": (0x03, 0x01),
            "both": (0x01, 0x01),
        }
        mapping_legacy = {"off": 0, "left": 1, "right": 2, "both": 3}
        if which not in mapping:
            raise ValueError("which must be left|right|both|off")
        side, ring = mapping[which]
        with self._session():
            if self._request(CMD_RING, DIR_SET, bytes([side, ring])) is None:
                self._request(
                    CMD_RING_LEGACY,
                    DIR_SET,
                    bytes([1, mapping_legacy[which]]),
                    require=True,
                )


# Back-compat alias used by the first Ear (a) prototype.
EarA = Device
