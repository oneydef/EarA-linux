"""PulseAudio Bluetooth sink / profile helpers."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from eara import bluez


def _pactl(*args: str, timeout: float = 6) -> str:
    try:
        result = subprocess.run(
            ["pactl", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def card_name(address: str) -> str:
    return "bluez_card." + address.replace(":", "_")


def reload_bluetooth_modules(*, force: bool = False) -> None:
    """Nudge PulseAudio when a BlueZ device is connected but no card appears.

    Unloads/reloads Bluetooth discover modules — may briefly interrupt other BT
    devices. Pass force=True only after a failed connect/recovery attempt.
    """
    if not force:
        return
    for name in ("module-bluetooth-discover", "module-bluez5-discover"):
        subprocess.run(
            ["pactl", "unload-module", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    time.sleep(0.4)
    subprocess.run(
        ["pactl", "load-module", "module-bluetooth-discover"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(0.8)


def wait_for_card(address: str, timeout: float = 28) -> bool:
    card = card_name(address)
    deadline = time.monotonic() + timeout
    reloaded = False
    while time.monotonic() < deadline:
        if card in _pactl("list", "short", "cards"):
            return True
        # Midway nudge — BlueZ often needs rediscovery after a flaky connect.
        if not reloaded and time.monotonic() + timeout - deadline > 4:
            reload_bluetooth_modules(force=True)
            reloaded = True
        time.sleep(0.4)
    return False


def set_profile(address: str, profile: str) -> bool:
    """profile examples: a2dp_sink, headset_head_unit, off"""
    out = subprocess.run(
        ["pactl", "set-card-profile", card_name(address), profile],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=6,
        check=False,
    )
    return out.returncode == 0


def find_sink(address: str) -> Optional[str]:
    needle = address.replace(":", "_")
    for line in _pactl("list", "short", "sinks").splitlines():
        parts = line.split()
        if len(parts) >= 2 and needle in parts[1]:
            return parts[1]
    return None


def wait_for_sink(address: str, timeout: float = 18) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sink = find_sink(address)
        if sink:
            return sink
        time.sleep(0.35)
    return None


def find_source(address: str) -> Optional[str]:
    needle = address.replace(":", "_")
    for line in _pactl("list", "short", "sources").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[1]
        if needle not in name:
            continue
        if ".monitor" in name:
            continue
        return name
    return None


def wait_for_source(address: str, timeout: float = 12) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        source = find_source(address)
        if source:
            return source
        time.sleep(0.35)
    return None


def set_default_source(source: str) -> bool:
    return subprocess.run(
        ["pactl", "set-default-source", source],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def move_record_streams(source: str) -> None:
    for line in _pactl("list", "short", "source-outputs").splitlines():
        parts = line.split()
        if parts:
            subprocess.run(
                ["pactl", "move-source-output", parts[0], source],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def set_default_sink(sink: str) -> bool:
    return subprocess.run(
        ["pactl", "set-default-sink", sink],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def move_streams_to_default() -> None:
    default = ""
    for line in _pactl("info").splitlines():
        if line.startswith("Default Sink:"):
            default = line.split(":", 1)[1].strip()
            break
    if not default:
        return
    for line in _pactl("list", "short", "sink-inputs").splitlines():
        parts = line.split()
        if parts:
            subprocess.run(
                ["pactl", "move-sink-input", parts[0], default],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def active_profile(address: str) -> str:
    card = card_name(address)
    text = _pactl("list", "cards")
    blocks = re.split(r"(?=^Card #)", text, flags=re.M)
    for block in blocks:
        if f"Name: {card}" not in block and f"Name:\t{card}" not in block:
            # pactl uses "Name: bluez_card...."
            if card not in block:
                continue
        match = re.search(r"Active Profile:\s*(\S+)", block)
        if match:
            return match.group(1)
    return ""


def ensure_bluez_card(address: str) -> bool:
    """Wait for PulseAudio card; force-load module-bluez5-device if needed."""
    if wait_for_card(address, timeout=14):
        return True
    path = bluez._device_path(address)
    subprocess.run(
        ["pactl", "load-module", "module-bluez5-device", f"path={path}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return wait_for_card(address, timeout=12)


def ensure_music_audio(address: str) -> dict[str, object]:
    """Connect A2DP and make it the default output."""
    keep_a2dp_in_calls()
    if not ensure_bluez_card(address):
        return {
            "ok": False,
            "error": (
                "PulseAudio did not create a Bluetooth card. "
                "Disconnect the phone (dual connection can steal A2DP), "
                "take both earbuds out of the case, then try again."
            ),
        }
    for profile in ("a2dp_sink", "a2dp-sink", "a2dp_sink.sbc"):
        if set_profile(address, profile):
            break
    sink = wait_for_sink(address)
    if not sink:
        return {"ok": False, "error": "No A2DP sink after connect"}
    set_default_sink(sink)
    move_streams_to_default()
    return {
        "ok": True,
        "sink": sink,
        "profile": active_profile(address) or "a2dp_sink",
    }


def list_a2dp_codecs(address: str) -> list[dict[str, str]]:
    """Codecs advertised by PulseAudio / PipeWire for this card."""
    card = card_name(address)
    text = _pactl("list", "cards")
    blocks = re.split(r"(?=^Card #)", text, flags=re.M)
    block = next((b for b in blocks if card in b), "")
    found: list[dict[str, str]] = []
    in_profiles = False
    for line in block.splitlines():
        if line.strip() == "Profiles:":
            in_profiles = True
            continue
        if in_profiles and line.strip().startswith("Active Profile:"):
            break
        if not in_profiles:
            continue
        match = re.match(r"\s*([^:]+):", line)
        if not match:
            continue
        profile = match.group(1).strip()
        if "a2dp" not in profile.lower() and "sink" not in profile:
            continue
        key = "sbc"
        lower = (line + " " + profile).lower()
        for name in ("lhdc", "ldac", "aptx_hd", "aptx-hd", "aptx_ll", "aptx", "aac", "sbc_xq", "sbc"):
            token = name.replace("_", "-")
            if name in lower or token in lower:
                key = name.replace("-", "_")
                break
        if any(item["profile"] == profile for item in found):
            continue
        found.append({"key": key, "label": key.upper().replace("_", " "), "profile": profile})
    return found


def active_codec(address: str) -> str:
    text = _pactl("list", "sinks")
    needle = address.replace(":", "_")
    for block in re.split(r"(?=^Sink #)", text, flags=re.M):
        if needle not in block:
            continue
        match = re.search(r"bluetooth\.codec\s*=\s*\"?([^\s\"]+)", block)
        if match:
            return match.group(1)
        match = re.search(r"api\.bluez5\.codec\s*=\s*\"?([^\s\"]+)", block)
        if match:
            return match.group(1)
    return ""


def set_host_codec(address: str, wanted: str) -> dict[str, object]:
    wanted_l = wanted.lower().replace("-", "_")
    options = list_a2dp_codecs(address)
    selected = next((o for o in options if o["key"] == wanted_l or wanted_l in o["profile"].lower()), None)
    if selected is None:
        available = ", ".join(o["label"] for o in options) or "none"
        return {
            "ok": False,
            "error": (
                f"{wanted} is not advertised by this Bluetooth adapter "
                f"(available: {available}). LHDC needs a dongle/stack that lists it."
            ),
            "available": options,
        }
    if not set_profile(address, selected["profile"]):
        return {"ok": False, "error": f"Could not select {selected['profile']}"}
    sink = wait_for_sink(address)
    if sink:
        set_default_sink(sink)
        move_streams_to_default()
    return {"ok": True, "codec": selected["key"], "profile": selected["profile"], "sink": sink}


def _module_indexes(name: str) -> list[str]:
    indexes: list[str] = []
    for line in _pactl("list", "short", "modules").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name:
            indexes.append(parts[0])
    return indexes


def keep_a2dp_in_calls() -> None:
    """Stop Pulse from dropping A2DP to HFP when Discord opens the mic."""
    for idx in _module_indexes("module-bluetooth-policy"):
        subprocess.run(
            ["pactl", "unload-module", idx],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    subprocess.run(
        ["pactl", "load-module", "module-bluetooth-policy", "auto_switch=0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    _write_pulse_override()


def _write_pulse_override() -> None:
    path = Path.home() / ".config" / "pulse" / "default.pa"
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = "# eara: keep A2DP during calls (same protocol as music)"
    snippet = (
        f"{marker}\n"
        ".nofail\n"
        "unload-module module-bluetooth-policy\n"
        "load-module module-bluetooth-policy auto_switch=0\n"
    )
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        existing = ""
    if marker in existing:
        return
    if existing.strip():
        path.write_text(existing.rstrip() + "\n\n" + snippet, encoding="utf-8")
        return
    body = ".include /etc/pulse/default.pa\n" + snippet
    path.write_text(body, encoding="utf-8")


def ensure_call_audio(address: str) -> dict[str, object]:
    """Discord/calls use the same A2DP path as music (not HFP/mSBC)."""
    keep_a2dp_in_calls()
    result = ensure_music_audio(address)
    if result.get("ok"):
        result["source"] = find_source(address)
        result["hint"] = (
            "Calls use A2DP like music. Discord output is high quality. "
            "Classic Bluetooth cannot keep A2DP and the earbud mic at once; "
            "use the laptop mic, or `eara audio hfp` for the bud mic (lower quality)."
        )
    return result


def ensure_hfp_audio(address: str) -> dict[str, object]:
    """Optional: HFP/mSBC so the earbud microphone appears (tinny audio)."""
    if not ensure_bluez_card(address):
        return {"ok": False, "error": "PulseAudio still has no Bluetooth card"}
    try:
        bluez.dbus_connect_profile(address, "0000111e-0000-1000-8000-00805f9b34fb")
    except Exception:
        pass
    last_err = "Headset profile is not available"
    for profile in ("handsfree_head_unit", "headset_head_unit"):
        if not set_profile(address, profile):
            continue
        sink = wait_for_sink(address, timeout=8)
        source = wait_for_source(address, timeout=10)
        if sink:
            set_default_sink(sink)
            move_streams_to_default()
        if source:
            set_default_source(source)
            move_record_streams(source)
            return {
                "ok": True,
                "sink": sink,
                "source": source,
                "profile": profile,
            }
        last_err = f"Switched to {profile} but no microphone source appeared."
    return {"ok": False, "error": last_err}
