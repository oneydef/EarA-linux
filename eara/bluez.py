"""BlueZ helpers: pair/connect A2DP and open the Nothing control channel."""

from __future__ import annotations
from eara import operations

import errno
import os
import re
import socket
import subprocess
import time
from typing import Optional

from eara.protocol import NT_LINK_UUID, RFCOMM_CHANNEL

ADDRESS_RE = __import__("re").compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")
_RFCOMM_CHANNEL_CACHE: dict[str, int] = {}


def _normalized_uuid(value: str) -> str:
    return re.sub(r"[^0-9a-f]", "", value.lower().removeprefix("0x"))


def _rfcomm_channel_from_sdp(xml: str, service_uuid: str = NT_LINK_UUID) -> Optional[int]:
    """Return the RFCOMM channel for one service from ``sdptool --xml`` output."""
    target = _normalized_uuid(service_uuid)
    records = re.findall(r"<record\b.*?</record>", xml, flags=re.I | re.S)
    for record in records or [xml]:
        values = re.findall(r"<uuid\b[^>]*\bvalue=[\"']([^\"']+)", record, flags=re.I)
        if target not in {_normalized_uuid(value) for value in values}:
            continue
        match = re.search(
            r"<uuid\b[^>]*\bvalue=[\"'](?:0x)?0*3[\"'][^>]*/?>"
            r".{0,500}?<uint8\b[^>]*\bvalue=[\"']([^\"']+)",
            record,
            flags=re.I | re.S,
        )
        if not match:
            continue
        try:
            channel = int(match.group(1), 0)
        except ValueError:
            continue
        if 1 <= channel <= 30:
            return channel
    return None


def discover_rfcomm_channel(address: str) -> int:
    """Discover the NTAPP RFCOMM channel, falling back for older earbuds."""
    cache_key = address.upper()
    if cache_key in _RFCOMM_CHANNEL_CACHE:
        return _RFCOMM_CHANNEL_CACHE[cache_key]
    try:
        result = subprocess.run(
            ["sdptool", "browse", "--xml", address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=operations.timeout(8),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        operations.check()
        return RFCOMM_CHANNEL
    channel = _rfcomm_channel_from_sdp(result.stdout or "")
    if channel is not None:
        _RFCOMM_CHANNEL_CACHE[cache_key] = channel
        return channel
    # Do not cache a fallback caused by a sleeping device or transient SDP error.
    return RFCOMM_CHANNEL


def _ctl(*args: str, timeout: float = 8) -> str:
    try:
        result = subprocess.run(
            ["bluetoothctl", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=operations.timeout(timeout),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        operations.check()
        return ""
    return (result.stdout or "") + (result.stderr or "")


def _paired_devices_dbus() -> Optional[list[dict[str, str]]]:
    objects = _dbus_objects()
    if objects is None:
        return None
    devices = []
    for path, interfaces in objects.items():
        props = interfaces.get("org.bluez.Device1", {})
        address = str(props.get("Address", "")).upper()
        if not props.get("Paired") or not ADDRESS_RE.fullmatch(address):
            continue
        name = str(props.get("Alias") or props.get("Name") or address)
        compatible = NT_LINK_UUID.lower() in {str(u).lower() for u in props.get("UUIDs", [])}
        devices.append({"address": address, "name": name, "compatible": compatible})
    return devices


def paired_devices() -> list[dict[str, str]]:
    found = _paired_devices_dbus()
    if found is not None:
        return found
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


def _dbus_objects() -> Optional[dict]:
    """All BlueZ managed objects, or None when D-Bus is unavailable."""
    try:
        import dbus
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        return dict(manager.GetManagedObjects(timeout=operations.timeout(5)))
    except Exception:
        return None


def _adapter_path() -> Optional[str]:
    objects = _dbus_objects()
    if objects:
        for path, ifaces in objects.items():
            if "org.bluez.Adapter1" in ifaces:
                return str(path)
    return None


def start_discovery() -> None:
    import dbus
    path = _adapter_path()
    if not path:
        raise RuntimeError("No Bluetooth adapter")
    bus = dbus.SystemBus()
    adapter = dbus.Interface(bus.get_object("org.bluez", path), "org.bluez.Adapter1")
    try:
        adapter.StartDiscovery(timeout=operations.timeout(5))
    except dbus.exceptions.DBusException as exc:
        # Already discovering is fine; anything else surfaces to the caller.
        name = exc.get_dbus_name()
        if name not in ("org.bluez.Error.InProgress", "org.bluez.Error.Failed"):
            raise


def stop_discovery() -> None:
    import dbus
    path = _adapter_path()
    if not path:
        return
    try:
        bus = dbus.SystemBus()
        adapter = dbus.Interface(bus.get_object("org.bluez", path), "org.bluez.Adapter1")
        adapter.StopDiscovery(timeout=5)
    except Exception:
        pass


def device_properties(address: str) -> Optional[dict]:
    objects = _dbus_objects() or {}
    for path, ifaces in objects.items():
        props = ifaces.get("org.bluez.Device1")
        if props and str(props.get("Address", "")).upper() == address.upper():
            return {str(k): props[k] for k in props}
    return None


def is_paired_dbus(address: str) -> bool:
    props = device_properties(address) or {}
    return bool(props.get("Paired", False))


def collect_nothing_candidates(objects: dict, *, include_unpaired: bool = True) -> list[dict[str, object]]:
    """Filter one ObjectManager snapshot into connectable Nothing-family rows.

    Pure helper so the matching rules are unit-testable without hardware.
    """
    found: list[dict[str, object]] = []
    for path, ifaces in objects.items():
        props = ifaces.get("org.bluez.Device1")
        if not props:
            continue
        name = str(props.get("Alias") or props.get("Name") or "").strip()
        paired = bool(props.get("Paired", False))
        if not name or name.upper() == path.rsplit("_", 1)[-1].replace("_", ":"):
            continue  # anonymous entries are useless as options
        if not looks_like_nothing(name):
            continue  # options list is Nothing-family only, like the phone app
        if not paired and not include_unpaired:
            continue
        if not paired and props.get("RSSI") is None:
            # A stale object without RSSI is not advertising right now: pairing
            # it would just time out. Only live advertisements are offered.
            continue
        address = str(props.get("Address") or path.rsplit("_", 1)[-1].replace("_", ":")).upper()
        rssi = int(rssi) if (rssi := props.get("RSSI")) is not None else None
        found.append({"address": address, "name": name, "paired": paired, "rssi": rssi})
    # One row per model name: earbuds in pairing mode can advertise per-bud.
    by_name: dict[str, dict[str, object]] = {}
    for cand in found:
        best = by_name.get(cand["name"])
        if best is None or (cand["paired"], cand["rssi"] or -999) > (best["paired"], best["rssi"] or -999):
            by_name[cand["name"]] = cand
    found = list(by_name.values())
    found.sort(key=lambda d: (not d["paired"], -(d["rssi"] or -999), d["name"]))
    return found


def scan_nothing_devices(seconds: float = 9.0, progress=None) -> list[dict[str, object]]:
    """Run real Bluetooth discovery and return Nothing-family candidates.

    Paired devices are always included even if discovery misses them; unpaired
    earbuds in pairing mode appear via RSSI while scanning.
    """
    known = {d["address"]: d for d in paired_devices() if looks_like_nothing(d["name"])}
    try:
        start_discovery()
    except Exception:
        pass
    try:
        deadline = time.monotonic() + max(2.0, seconds)
        reported = -1
        while time.monotonic() < deadline:
            objects = _dbus_objects()
            if objects:
                for cand in collect_nothing_candidates(objects):
                    prev = known.get(cand["address"])
                    if prev is None or (cand["paired"], cand["rssi"] or -999) > (prev.get("paired"), prev.get("rssi") or -999):
                        known[cand["address"]] = cand
                # Refresh paired entries that discovery may have dropped.
                for d in paired_devices():
                    if looks_like_nothing(d["name"]):
                        entry = known.setdefault(d["address"], {**d, "paired": True, "rssi": None})
                        entry["paired"] = True
            visible = len({d["name"] for d in known.values()})
            if callable(progress) and visible != reported:
                reported = visible
                try:
                    progress(visible)
                except Exception:
                    pass
            operations.pause(0.7)
    finally:
        with operations.cleanup():
            stop_discovery()
    by_name: dict[str, dict[str, object]] = {}
    for cand in known.values():
        best = by_name.get(cand["name"])
        rank = (bool(cand.get("paired")), cand.get("rssi") or -999)
        if best is None or rank > (bool(best.get("paired")), best.get("rssi") or -999):
            by_name[cand["name"]] = cand
    return sorted(by_name.values(), key=lambda d: (not d.get("paired"), -(d.get("rssi") or -999), d["name"]))


class _AgentSession:
    """Register a NoInputNoOutput agent via bluetoothctl for the pairing window.

    Desktop environments normally provide the pairing agent; when none is
    running, BlueZ rejects the earbuds' passkey confirmation with
    "Operation not permitted" and pairing silently never sticks.
    """

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "_AgentSession":
        operations.check()
        try:
            self.proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            assert self.proc.stdin is not None
            self.proc.stdin.write("agent NoInputNoOutput\n")
            self.proc.stdin.write("default-agent\n")
            self.proc.stdin.flush()
            operations.pause(0.6)
        except (OSError, AssertionError):
            self.close()
            self.proc = None
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        if self.proc is not None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write("quit\n")
                    self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
            self.proc = None

    def __exit__(self, *exc) -> None:
        self.close()


def pair_device(address: str, timeout: float = 25.0) -> None:
    """Pair an unpaired device and verify the pairing flag actually stuck.

    Earbuds commonly cancel the pairing handshake (br-connection-canceled) or
    keep a half-open ACL from an earlier attempt, so a stale link is dropped
    first and the Paired property is verified instead of trusted blindly.
    """
    import dbus
    props = device_properties(address)
    if props is None:
        raise RuntimeError(f"{address} is not visible — scan again")
    if props.get("Paired"):
        return
    try:
        dbus_disconnect(address)  # a stale unpaired ACL blocks Pair()
        operations.pause(1.0)
    except Exception:
        pass
    error = ""
    with _AgentSession():
        try:
            bus = dbus.SystemBus()
            dev = bus.get_object("org.bluez", f"/org/bluez/hci0/dev_{address.upper().replace(':', '_')}")
            dev.Pair(dbus_interface="org.bluez.Device1", timeout=operations.timeout(timeout))
        except Exception as exc:
            operations.check()
            error = str(exc)
            out = _ctl("pair", address, timeout=timeout)
            if out.strip():
                error = out.strip().splitlines()[-1]
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if is_paired_dbus(address):
                try:
                    bus = dbus.SystemBus()
                    dev = bus.get_object("org.bluez", f"/org/bluez/hci0/dev_{address.upper().replace(':', '_')}")
                    dbus.Interface(dev, "org.freedesktop.DBus.Properties").Set(
                        "org.bluez.Device1", "Trusted", dbus.Boolean(True, variant_level=1), timeout=operations.timeout(5))
                except Exception:
                    _ctl("trust", address)
                # Hold check: buds can accept Pair() and then drop it seconds
                # later when they snap back to the phone.
                operations.pause(2.5)
                if is_paired_dbus(address):
                    return
                raise RuntimeError(
                    f"{address} accepted pairing and then dropped it — the earbuds went back to your phone."
                    " Keep them IN THE CASE with the lid open and turn off the phone's Bluetooth for a minute."
                )
            operations.pause(0.5)
    raise RuntimeError(
        f"Pairing {address} did not complete"
        + (f" ({error})" if error else "")
        + ". Keep the earbuds IN THE CASE with the lid open and hold the case button ~2 s until the LED flashes"
          " (pairing mode); disconnect them from the phone first."
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
    ranked = [d for d in devices if looks_like_nothing(d["name"]) or d.get("compatible")]
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
        for path, ifaces in manager.GetManagedObjects(timeout=operations.timeout(5)).items():
            if str(path).endswith(mac) and "org.bluez.Device1" in ifaces:
                return str(path)
    except Exception:
        operations.check()
    return "/org/bluez/hci0/dev_" + address.replace(":", "_")


def dbus_connect(address: str) -> None:
    try:
        import dbus
    except ImportError as exc:
        raise RuntimeError("python3-dbus is required") from exc
    bus = dbus.SystemBus()
    dev = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1")
    props = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.freedesktop.DBus.Properties")
    props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True, variant_level=1), timeout=operations.timeout(5))
    # Connected can mean RFCOMM only. Connect also negotiates missing audio
    # profiles on an existing ACL link. Do not immediately issue another
    # ConnectProfile while BlueZ is still publishing the audio transport.
    dev.Connect(timeout=operations.timeout(10))


def dbus_connect_profile(address: str, uuid: str) -> None:
    try:
        import dbus
    except ImportError as exc:
        raise RuntimeError("python3-dbus is required") from exc
    bus = dbus.SystemBus()
    dev = dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1")
    dev.ConnectProfile(uuid, timeout=operations.timeout(8))


def dbus_disconnect(address: str) -> None:
    try:
        import dbus
    except ImportError:
        _ctl("disconnect", address)
        return
    try:
        bus = dbus.SystemBus()
        dbus.Interface(bus.get_object("org.bluez", _device_path(address)), "org.bluez.Device1").Disconnect(timeout=operations.timeout(5))
    except Exception:
        _ctl("disconnect", address)


def has_audio_sink(address: str) -> bool:
    from eara.audio import find_sink

    return bool(find_sink(address))


def scan_for_device(address: str, dwell: float = 6.0) -> bool:
    """Run discovery so sleeping buds show up again.

    Discovery goes through D-Bus: a one-shot `bluetoothctl scan on` never
    exits by itself, so it used to block for the whole subprocess timeout
    with no polling window at all. Paired-but-absent buds advertise no RSSI,
    so the dwell still serves as a live window for BlueZ auto-connect.
    """
    wanted = address.upper()
    deadline = time.monotonic() + dwell
    seen = False
    discovery = True
    try:
        start_discovery()
    except Exception:
        discovery = False
        _ctl("scan", "on")
    try:
        while time.monotonic() < deadline:
            if is_connected(wanted):
                seen = True
                break
            props = device_properties(wanted) or {}
            if props.get("Connected") or props.get("RSSI") is not None:
                seen = True  # buds are alive: BlueZ can auto-connect or we can page
                break
            operations.pause(0.8)
    finally:
        if discovery:
            with operations.cleanup():
                stop_discovery()
        else:
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
    with operations.scope(timeout):
        _trust_and_connect(address, timeout, scan=scan, max_rounds=max_rounds)


def _trust_and_connect(address: str, timeout: float, *, scan: bool, max_rounds: int) -> None:
    power_on()
    if not _is_paired(address):
        # The buds can remember this host while the host-side link key is gone
        # (factory reset, storage wipe, phone re-pair). They then self-initiate
        # pairing that dies with "no agent available" unless an agent confirms
        # the passkey, so pair here instead of bouncing the user to bluetoothctl.
        if scan and not is_connected(address):
            scan_for_device(address, dwell=5.0)
        pair_device(address)
    _ctl("trust", address)
    if is_connected(address) and has_audio_sink(address):
        return

    last_err = ""
    per_round = max(10.0, timeout / max_rounds)

    for round_num in range(max_rounds):
        # Round 0 pages the buds directly — Connect() does not need discovery,
        # and the scan window cost 3.5 s on every attempt. Discovery stays as
        # a recovery tool for the rounds after a failed page.
        if scan and round_num > 0:
            scan_for_device(address, dwell=5.0)

        if is_connected(address) and has_audio_sink(address):
            return

        round_deadline = time.monotonic() + per_round
        while time.monotonic() < round_deadline:
            linked = False
            try:
                dbus_connect(address)  # synchronous: returns only with the link up
                linked = True
            except Exception as exc:
                operations.check()
                last_err = str(exc)
                out = _ctl("connect", address, timeout=12)
                if out.strip():
                    last_err = out.strip()
            if not linked:
                operations.pause(0.8)
            if linked or is_connected(address):
                settle_deadline = time.monotonic() + 12
                while time.monotonic() < settle_deadline:
                    if has_audio_sink(address):
                        return
                    operations.pause(0.4)
                if has_audio_sink(address):
                    return
            operations.pause(0.5)

        if round_num + 1 < max_rounds:
            try:
                dbus_disconnect(address)
            except Exception:
                pass
            from eara.audio import reload_bluetooth_modules

            reload_bluetooth_modules(force=True)
            operations.pause(1.0 + round_num * 0.4)

    raise TimeoutError(
        f"Bluetooth connect timed out for {address} after {max_rounds} attempts: {last_err}"
    )


def reset_link(address: str) -> None:
    """Drop RFCOMM/A2DP and reconnect from scratch."""
    dbus_disconnect(address)
    operations.pause(2.0)
    from eara.audio import reload_bluetooth_modules

    reload_bluetooth_modules(force=True)
    trust_and_connect(address, timeout=50, max_rounds=5)


def recover_hint() -> str:
    return (
        "Bluetooth adapter could not be powered on. "
        "Check Bluetooth and airplane-mode settings, then run eara doctor. "
        "If the adapter remains unavailable, inspect the Bluetooth service "
        "and kernel logs before restarting services."
    )


def disconnect(address: str) -> None:
    dbus_disconnect(address)


def open_rfcomm(address: str, timeout: float = 8) -> socket.socket:
    last: Optional[OSError] = None
    channel = discover_rfcomm_channel(address)
    for attempt in range(8):
        operations.check()
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        try:
            sock.settimeout(operations.timeout(timeout))
            sock.connect((address, channel))
            return sock
        except operations.Cancelled:
            sock.close()
            raise
        except OSError as exc:
            last = exc
            try:
                sock.close()
            except OSError:
                pass
            if exc.errno in (
                errno.EBUSY,
                errno.EAGAIN,
                errno.EINPROGRESS,
                errno.EALREADY,
                errno.ETIMEDOUT,
            ):
                if attempt in (2, 5):
                    scan_for_device(address, dwell=4.0)
                operations.pause(0.7 + attempt * 0.35)
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
    if exc.errno in (errno.EBUSY, errno.EALREADY):
        return "Control channel busy. Close other earbud-control apps and retry."
    if exc.errno in (111, 112):
        return "Earbuds asleep or out of range. Take them out of the case."
    return str(exc)
