"""BlueZ helpers: pair/connect A2DP and open the Nothing control channel."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from typing import Optional

from eara.protocol import RFCOMM_CHANNEL

ADDRESS_RE = __import__("re").compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")


def _ctl(*args: str, timeout: float = 8) -> str:
    try:
        result = subprocess.run(
            ["bluetoothctl", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or "") + (result.stderr or "")


def paired_devices() -> list[dict[str, str]]:
    devices = []
    for line in _ctl("devices").splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3 and parts[0] == "Device" and ADDRESS_RE.match(parts[1]):
            devices.append({"address": parts[1].upper(), "name": parts[2].strip()})
    return devices


def looks_like_nothing(name: str) -> bool:
    value = name.lower()
    return any(
        k in value
        for k in (
            "nothing ear",
            "nothing cmf",
            "cmf buds",
            "cmf neck",
            "ear (a)",
            "ear(a)",
            "ear (1)",
            "ear (2)",
            "ear (open)",
            "ear (stick)",
        )
    )


def find_nothing_device(preferred: str = "") -> Optional[dict[str, str]]:
    devices = paired_devices()
    if preferred:
        wanted = preferred.lower()
        for device in devices:
            if device["address"].lower() == wanted or device["name"].lower() == wanted:
                return device
        if ADDRESS_RE.match(preferred):
            # Only accept a bare MAC when it is actually paired.
            upper = preferred.upper()
            for device in devices:
                if device["address"] == upper:
                    return device
            return None
    ranked = [d for d in devices if looks_like_nothing(d["name"])]
    connected = [d for d in ranked if is_connected(d["address"])]
    return (connected or ranked)[0] if ranked else None


def find_ear_a(preferred: str = "") -> Optional[dict[str, str]]:
    """Deprecated alias."""
    return find_nothing_device(preferred)


def device_info(address: str) -> str:
    return _ctl("info", address)


def is_connected(address: str) -> bool:
    return __import__("re").search(r"^\s*Connected:\s*yes\s*$", device_info(address), __import__("re").M) is not None


def power_on() -> None:
    if "Powered: yes" in _ctl("show"):
        return
    out = _ctl("power", "on")
    if "Powered: yes" not in _ctl("show"):
        raise RuntimeError(recover_hint() + (f"\n({out.strip()})" if out.strip() else ""))


def power_off() -> None:
    if "Powered: no" in _ctl("show"):
        return
    _ctl("power", "off")


def _device_path(address: str) -> str:
    mac = "dev_" + address.replace(":", "_")
    try:
        import dbus

        bus = dbus.SystemBus()
        manager = dbus.Interface(
            bus.get_object("org.bluez", "/"),
            "org.freedesktop.DBus.ObjectManager",
        )
        for path, ifaces in manager.GetManagedObjects().items():
            if str(path).endswith(mac) and "org.bluez.Device1" in ifaces:
                return str(path)
    except Exception:
        pass
    return "/org/bluez/hci0/dev_" + address.replace(":", "_")


def dbus_connect(address: str) -> None:
    try:
        import dbus
    except ImportError as exc:
        raise RuntimeError("python3-dbus is required") from exc
    bus = dbus.SystemBus()
    dev = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1")
    props = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.freedesktop.DBus.Properties")
    props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
    if not bool(props.Get("org.bluez.Device1", "Connected")):
        dev.Connect()
    try:
        dev.ConnectProfile("0000110b-0000-1000-8000-00805f9b34fb")  # A2DP
    except Exception:
        pass


def dbus_connect_profile(address: str, uuid: str) -> None:
    try:
        import dbus
    except ImportError as exc:
        raise RuntimeError("python3-dbus is required") from exc
    bus = dbus.SystemBus()
    dev = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1")
    dev.ConnectProfile(uuid)


def dbus_disconnect(address: str) -> None:
    try:
        import dbus
    except ImportError:
        _ctl("disconnect", address)
        return
    try:
        bus = dbus.SystemBus()
        dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1").Disconnect()
    except Exception:
        _ctl("disconnect", address)


def has_audio_sink(address: str) -> bool:
    from eara.audio import find_sink

    return bool(find_sink(address))


def scan_for_device(address: str, dwell: float = 6.0) -> bool:
    """Run discovery so sleeping buds show up again."""
    wanted = address.upper()
    _ctl("scan", "on")
    deadline = time.monotonic() + dwell
    seen = False
    while time.monotonic() < deadline:
        if is_connected(wanted):
            seen = True
            break
        for line in _ctl("devices").splitlines():
            if wanted in line.upper():
                seen = True
                break
        if seen:
            break
        time.sleep(0.8)
    _ctl("scan", "off")
    return seen or is_connected(wanted)


def _is_paired(address: str) -> bool:
    upper = address.upper()
    return any(d["address"] == upper for d in paired_devices())


def trust_and_connect(
    address: str,
    timeout: float = 50,
    *,
    scan: bool = True,
    max_rounds: int = 5,
) -> None:
    """Connect A2DP; mark Trusted only for paired devices (RFCOMM auto-connect)."""
    if not _is_paired(address):
        raise RuntimeError(f"{address} is not paired — pair in system Bluetooth first")
    power_on()
    _ctl("trust", address)
    if is_connected(address) and has_audio_sink(address):
        return

    last_err = ""
    per_round = max(12.0, timeout / max_rounds)

    for round_num in range(max_rounds):
        if scan:
            scan_for_device(address, dwell=5.0 if round_num == 0 else 7.0)

        if is_connected(address):
            if has_audio_sink(address):
                return
            dbus_disconnect(address)
            time.sleep(1.5)

        round_deadline = time.monotonic() + per_round
        while time.monotonic() < round_deadline:
            try:
                dbus_connect(address)
            except Exception as exc:
                last_err = str(exc)
                out = _ctl("connect", address, timeout=15)
                if out.strip():
                    last_err = out.strip()
            time.sleep(1.2)
            if is_connected(address):
                settle_deadline = time.monotonic() + 16
                while time.monotonic() < settle_deadline:
                    if has_audio_sink(address):
                        return
                    info = device_info(address)
                    if "ServicesResolved: yes" in info:
                        from eara.audio import ensure_bluez_card

                        ensure_bluez_card(address)
                        if has_audio_sink(address):
                            return
                    time.sleep(0.45)
                if has_audio_sink(address):
                    return
            time.sleep(0.8)

        if round_num + 1 < max_rounds:
            try:
                dbus_disconnect(address)
            except Exception:
                pass
            from eara.audio import reload_bluetooth_modules

            reload_bluetooth_modules(force=True)
            time.sleep(1.2 + round_num * 0.5)

    raise TimeoutError(
        f"Bluetooth connect timed out for {address} after {max_rounds} attempts: {last_err}"
    )


def reset_link(address: str) -> None:
    """Drop RFCOMM/A2DP and reconnect from scratch."""
    dbus_disconnect(address)
    time.sleep(2.0)
    from eara.audio import reload_bluetooth_modules

    reload_bluetooth_modules(force=True)
    trust_and_connect(address, timeout=50, max_rounds=5)


def recover_hint() -> str:
    return (
        "Bluetooth adapter is stuck. Run:\n"
        "  sudo systemctl restart bluetooth\n"
        "  systemctl --user restart pulseaudio || systemctl --user restart pipewire-pulse\n"
        "  bluetoothctl power on\n"
        "then: eara connect"
    )


def disconnect(address: str) -> None:
    dbus_disconnect(address)


def open_rfcomm(address: str, timeout: float = 8) -> socket.socket:
    last: Optional[OSError] = None
    for attempt in range(8):
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(timeout)
        try:
            sock.connect((address, RFCOMM_CHANNEL))
            return sock
        except OSError as exc:
            last = exc
            try:
                sock.close()
            except OSError:
                pass
            if exc.errno in (16, 11, 115, 110):  # EBUSY, EAGAIN, ETIMEDOUT
                if attempt in (2, 5):
                    scan_for_device(address, dwell=4.0)
                time.sleep(0.7 + attempt * 0.35)
                continue
            raise
    assert last is not None
    raise last


def permission_hint(exc: OSError) -> str:
    if exc.errno == 13:
        user = os.environ.get("USER", "you")
        return (
            "RFCOMM permission denied. Add your user to the bluetooth group:\n"
            f"  sudo usermod -aG bluetooth {user}\n"
            "then log out and back in."
        )
    if exc.errno == 16:
        return "Control channel busy (PulseAudio). Retry in a second."
    if exc.errno in (111, 112):
        return "Earbuds asleep or out of range. Take them out of the case."
    return str(exc)
