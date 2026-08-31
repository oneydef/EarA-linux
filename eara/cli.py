"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys

from eara import __version__, audio
from eara.protocol import ANC_MODES, EQ_PRESETS, GESTURE_ACTIONS, GESTURE_SIDES, GESTURE_TYPES, LISTENING_MODES
from eara.session import Device


def _device(args: argparse.Namespace) -> Device:
    return Device.discover(getattr(args, "device", "") or "")


def cmd_status(args: argparse.Namespace) -> int:
    try:
        ear = _device(args)
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 1
    status = ear.status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    print(f"{status['name']}  ({status['address']})")
    model = (status.get("model") or {}).get("name")
    if model:
        print(f"Model:     {model}")
    print(f"Bluetooth: {'connected' if status['bt_connected'] else 'no'}")
    print(f"Protocol:  {'ok' if status['protocol'] else 'no'}")
    if status.get("firmware"):
        print(f"Firmware:  {status['firmware']}")
    if status.get("serial"):
        print(f"Serial:    {status['serial']}")
    print(f"ANC:       {status.get('anc') or '—'}")
    print(f"EQ:        {status.get('eq') or '—'}")
    batt = status.get("battery") or {}
    for key in ("left", "right", "case"):
        item = batt.get(key)
        if isinstance(item, dict) and item.get("available"):
            ch = " charging" if item.get("charging") else ""
            print(f"Battery {key}: {item['level']}%{ch}")
    if status.get("latency") is not None:
        print(f"Latency:   {'on' if status['latency'] else 'off'}")
    if status.get("in_ear") is not None:
        print(f"In-ear:    {'on' if status['in_ear'] else 'off'}")
    audio_info = status.get("audio") or {}
    if audio_info.get("sink"):
        print(f"Sink:      {audio_info['sink']} ({audio_info.get('profile')})")
    if audio_info.get("source"):
        print(f"Mic:       {audio_info['source']}")
    if audio_info.get("codec"):
        print(f"Host codec:{audio_info['codec']}")
    if status.get("device_codec"):
        print(f"Buds codec:{status['device_codec']}")
    if status.get("listening"):
        print(f"Listening: {status['listening']}")
    if status.get("personalized_anc") is not None:
        print(f"Personal ANC: {'on' if status['personalized_anc'] else 'off'}")
    if status.get("error"):
        print(f"Error:     {status['error']}", file=sys.stderr)
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    ear = _device(args)
    result = ear.connect_audio(with_mic=args.mic)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)
    return 0 if result.get("ok") else 1


def cmd_reset(args: argparse.Namespace) -> int:
    result = _device(args).reset_connection()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)
    return 0 if result.get("ok") else 1


def cmd_disconnect(args: argparse.Namespace) -> int:
    _device(args).disconnect_audio()
    print("Disconnected")
    return 0


def cmd_anc(args: argparse.Namespace) -> int:
    _device(args).set_anc(args.mode)
    print(f"ANC → {args.mode}")
    return 0


def cmd_eq(args: argparse.Namespace) -> int:
    _device(args).set_eq(args.preset)
    print(f"EQ → {args.preset}")
    return 0


def cmd_custom_eq(args: argparse.Namespace) -> int:
    _device(args).set_custom_eq(args.bass, args.mid, args.treble)
    print(f"Custom EQ → bass={args.bass} mid={args.mid} treble={args.treble}")
    return 0


def cmd_graphic_eq(args: argparse.Namespace) -> int:
    _device(args).set_graphic_eq(list(args.gains))
    print("Graphic EQ → " + " ".join(str(g) for g in args.gains))
    return 0


def cmd_codec(args: argparse.Namespace) -> int:
    ear = _device(args)
    if args.name == "list":
        print(json.dumps({"host": audio.list_a2dp_codecs(ear.address), "active": audio.active_codec(ear.address)}, indent=2))
        return 0
    result = ear.set_codec(args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)
    return 0 if result.get("ok") else 1


def cmd_latency(args: argparse.Namespace) -> int:
    _device(args).set_latency(args.state == "on")
    print(f"Low latency → {args.state}")
    return 0


def cmd_ied(args: argparse.Namespace) -> int:
    _device(args).set_in_ear_detection(args.state == "on")
    print(f"In-ear detection → {args.state}")
    return 0


def cmd_bass(args: argparse.Namespace) -> int:
    _device(args).set_bass(args.state == "on", args.level)
    print(f"Bass enhance → {args.state} level={args.level}")
    return 0


def cmd_gesture(args: argparse.Namespace) -> int:
    _device(args).set_gesture(args.side, args.type, args.action)
    print(f"Gesture {args.side} {args.type} → {args.action}")
    return 0


def cmd_personal_anc(args: argparse.Namespace) -> int:
    _device(args).set_personalized_anc(args.state == "on")
    print(f"Personalized ANC → {args.state}")
    return 0


def cmd_listening(args: argparse.Namespace) -> int:
    _device(args).set_listening_mode(args.mode)
    print(f"Listening mode → {args.mode}")
    return 0


def cmd_ring(args: argparse.Namespace) -> int:
    _device(args).ring(args.which)
    print(f"Ring → {args.which}")
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    from eara.i18n import t
    from eara.protocol import format_ear_tip

    result = _device(args).ear_tip_test()
    print(
        format_ear_tip(
            result,
            left=t("left"),
            right=t("right"),
            good=t("fit_good"),
            poor=t("fit_poor"),
        )
    )
    return 0


def cmd_audio(args: argparse.Namespace) -> int:
    ear = _device(args)
    if not ear.connected:
        ear.connect_audio(with_mic=args.mode == "headset")
    result = (
        audio.ensure_music_audio(ear.address)
        if args.mode in ("music", "headset", "mic")
        else audio.ensure_hfp_audio(ear.address)
    )
    print(result)
    return 0 if result.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    from eara import bluez

    show = bluez._ctl("show")
    powered = "Powered: yes" in show
    print(f"Adapter powered: {'yes' if powered else 'NO'}")
    try:
        ear = _device(args)
        print(f"Device: {ear.name} ({ear.address})")
        print(f"Connected: {'yes' if ear.connected else 'no'}")
        info = bluez.device_info(ear.address)
        for key in ("Trusted", "ServicesResolved", "Paired"):
            for line in info.splitlines():
                if key in line:
                    print(line.strip())
    except LookupError as exc:
        print(exc)
    import subprocess

    cards = subprocess.check_output(["pactl", "list", "short", "cards"], text=True)
    sinks = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
    sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True)
    print("Pulse cards:\n" + (cards.strip() or "(empty)"))
    print("Pulse sinks:\n" + (sinks.strip() or "(empty)"))
    print("Pulse sources:\n" + (sources.strip() or "(empty)"))
    if not powered:
        print()
        print(bluez.recover_hint())
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eara",
        description="Unofficial Linux companion for compatible True Wireless earbuds",
    )
    p.add_argument("--device", default="", help="Bluetooth address or name")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version=f"EarA {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)
    c = sub.add_parser("connect")
    c.add_argument("--mic", action="store_true")
    c.set_defaults(func=cmd_connect)
    sub.add_parser("disconnect").set_defaults(func=cmd_disconnect)
    sub.add_parser("reset").set_defaults(func=cmd_reset)

    a = sub.add_parser("anc")
    a.add_argument("mode", choices=sorted(ANC_MODES))
    a.set_defaults(func=cmd_anc)

    e = sub.add_parser("eq")
    e.add_argument("preset", choices=sorted(EQ_PRESETS))
    e.set_defaults(func=cmd_eq)

    ce = sub.add_parser("custom-eq")
    ce.add_argument("bass", type=float)
    ce.add_argument("mid", type=float)
    ce.add_argument("treble", type=float)
    ce.set_defaults(func=cmd_custom_eq)

    ge = sub.add_parser("graphic-eq")
    ge.add_argument("gains", nargs=8, type=float, help="8 band gains in dB (32..4k Hz)")
    ge.set_defaults(func=cmd_graphic_eq)

    codec = sub.add_parser("codec")
    codec.add_argument("name", help="sbc, aac, lhdc, ldac, or list")
    codec.set_defaults(func=cmd_codec)

    l = sub.add_parser("latency")
    l.add_argument("state", choices=["on", "off"])
    l.set_defaults(func=cmd_latency)
    i = sub.add_parser("inear")
    i.add_argument("state", choices=["on", "off"])
    i.set_defaults(func=cmd_ied)
    b = sub.add_parser("bass")
    b.add_argument("state", choices=["on", "off"])
    b.add_argument("--level", type=float, default=1.0)
    b.set_defaults(func=cmd_bass)

    pa = sub.add_parser("personal-anc")
    pa.add_argument("state", choices=["on", "off"])
    pa.set_defaults(func=cmd_personal_anc)

    lm = sub.add_parser("listening")
    lm.add_argument("mode", choices=sorted(LISTENING_MODES))
    lm.set_defaults(func=cmd_listening)

    g = sub.add_parser("gesture")
    g.add_argument("side", choices=sorted(GESTURE_SIDES))
    g.add_argument("type", choices=sorted(GESTURE_TYPES))
    g.add_argument("action", choices=sorted(GESTURE_ACTIONS))
    g.set_defaults(func=cmd_gesture)

    r = sub.add_parser("ring")
    r.add_argument("which", nargs="?", default="both", choices=["left", "right", "both", "off"])
    r.set_defaults(func=cmd_ring)
    sub.add_parser("fit").set_defaults(func=cmd_fit)

    au = sub.add_parser("audio")
    au.add_argument("mode", choices=["music", "headset", "mic", "hfp"])
    au.set_defaults(func=cmd_audio)
    sub.add_parser("gui").set_defaults(func=lambda args: __import__("eara.gui", fromlist=["run"]).run())
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
