"""GTK4 / Adwaita companion UI — Nothing-inspired black / white / red theme."""

from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from eara import __version__, bluez
from eara import SUPPORT_URL
from eara.i18n import load_lang, set_lang, t
from eara.protocol import (
    GESTURE_ACTIONS,
    GESTURE_TYPES,
    GRAPHIC_HZ,
    LISTENING_MODES,
    format_ear_tip,
    merge_gestures,
)
from eara.session import Device

_FONT_DOT_FALLBACK = "DotGothic16, VT323, monospace"
_FONT_UI_FALLBACK = "Inter, NType 82, Roboto, Cantarell, sans-serif"
_FONT_FILES = (
    "DotGothic16-Regular.ttf",
    "Inter-Regular.ttf",
)


def _pick_dot_font() -> str:
    import subprocess

    try:
        text = subprocess.run(
            ["fc-list", ":", "family"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        ).stdout.lower()
        for key, name in (
            ("ndot 55", "NDot 55"),
            ("ndot55", "NDot55"),
            ("ndot", "NDot"),
            ("dotgothic16", "DotGothic16"),
        ):
            if key in text:
                return name
    except OSError:
        pass
    return "DotGothic16"


def _pick_ui_font() -> str:
    import subprocess

    try:
        text = subprocess.run(
            ["fc-list", ":", "family"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        ).stdout.lower()
        for key, name in (
            ("inter", "Inter"),
            ("ntype 82", "NType 82"),
            ("ntype", "NType"),
            ("roboto", "Roboto"),
        ):
            if key in text:
                return name
    except OSError:
        pass
    return "Inter"


def _build_css() -> str:
    dot = _pick_dot_font()
    ui = _pick_ui_font()
    return f"""
window.eara-window {{
  background-color: #0a0a0a;
  color: #f2f2f2;
}}
.eara-stack {{
  background-color: #000000;
  background-image: radial-gradient(circle, #252525 0.65px, transparent 0.65px);
  background-size: 16px 16px;
  font-family: {ui}, {_FONT_UI_FALLBACK};
}}
.eara-hero {{
  background-color: #000000;
  border-bottom: 1px solid #222222;
  padding: 12px 18px 8px 18px;
}}
.eara-brand {{
  font-family: {dot}, {_FONT_DOT_FALLBACK};
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 6px;
  color: #ffffff;
  line-height: 1;
  margin-bottom: 0;
}}
.eara-tag {{
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #d71921;
  margin-top: 3px;
  line-height: 1.1;
}}
.eara-ui-text, .eara-status, .eara-battery, .eara-meta, .dim-label {{
  font-family: {ui}, {_FONT_UI_FALLBACK};
}}
.eara-status-card {{
  background: linear-gradient(180deg, #171717 0%, #101010 100%);
  border: 1px solid #2c2c2c;
  border-radius: 18px;
  padding: 14px 16px 12px 16px;
}}
window.eara-window.eara-focused .eara-status-card {{
  border-color: #454545;
}}
.eara-status-head {{
  margin-bottom: 4px;
}}
.eara-status-dot {{
  min-width: 11px;
  min-height: 11px;
  border-radius: 999px;
  margin-top: 7px;
  background-color: #666666;
}}
.eara-dot-ok {{
  background-color: #22c55e;
  box-shadow: 0 0 10px alpha(#22c55e, 0.55);
}}
.eara-dot-warn {{
  background-color: #f59e0b;
  box-shadow: 0 0 10px alpha(#f59e0b, 0.45);
}}
.eara-dot-off {{
  background-color: #d71921;
  box-shadow: 0 0 10px alpha(#d71921, 0.45);
}}
.eara-status-name {{
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.2px;
}}
.eara-status-badges {{
  margin-top: 2px;
}}
.eara-status-badge {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 4px 9px;
  border-radius: 999px;
  background-color: #222222;
  color: #999999;
  border: 1px solid #333333;
}}
.eara-status-badge-ok {{
  background-color: #132818;
  color: #86efac;
  border-color: #1f4d31;
}}
.eara-status-badge-warn {{
  background-color: #2a210f;
  color: #fcd34d;
  border-color: #4d3b14;
}}
.eara-status-badge-bad {{
  background-color: #301010;
  color: #fca5a5;
  border-color: #5a2020;
}}
.eara-status-meta {{
  color: #8f8f8f;
  font-size: 12px;
  margin-top: 2px;
  margin-bottom: 10px;
}}
.eara-status-batteries {{
  margin-top: 2px;
}}
.eara-status-batteries flowboxchild {{
  min-width: 96px;
}}
.eara-batt-cell {{
  min-width: 96px;
  background-color: #0d0d0d;
  border: 1px solid #262626;
  border-radius: 14px;
  padding: 10px 10px 8px 10px;
}}
.eara-batt-cell.eara-batt-off {{
  opacity: 0.72;
}}
.eara-batt-side {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #9a9a9a;
}}
.eara-batt-pct {{
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
}}
.eara-batt-sub {{
  font-size: 10px;
  font-weight: 600;
  color: #d71921;
  min-height: 14px;
}}
.eara-batt-sub-ok {{
  color: #86efac;
}}
progressbar.eara-batt-bar {{
  min-height: 5px;
}}
progressbar.eara-batt-bar trough {{
  min-height: 5px;
  border-radius: 999px;
  background-color: #252525;
  border: none;
}}
progressbar.eara-batt-bar progress {{
  background-color: #f2f2f2;
  border-radius: 999px;
}}
progressbar.eara-batt-bar.eara-batt-low progress {{
  background-color: #d71921;
}}
progressbar.eara-batt-bar.eara-batt-charge progress {{
  background-color: #22c55e;
}}
.eara-status-modes {{
  margin-top: 10px;
}}
.eara-mode-chip {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 5px 10px;
  border-radius: 999px;
  background-color: #121212;
  color: #bdbdbd;
  border: 1px solid #2f2f2f;
}}
.eara-status {{
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
}}
.eara-battery {{
  font-size: 14px;
  font-weight: 500;
  line-height: 1.45;
  color: #ececec;
  background-color: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 10px 12px;
}}
headerbar {{
  background-color: #000000;
  color: #ffffff;
  border-bottom: 1px solid #1f1f1f;
}}
button.eara-header-btn {{
  border-radius: 999px;
  min-height: 34px;
  padding: 0 18px;
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-weight: 600;
  background-color: #1a1a1a;
  color: #888888;
  border: 1px solid #333333;
  opacity: 0.75;
}}
button.eara-header-btn.eara-header-connect {{
  background-color: #5a1010;
  color: #cc8888;
  border-color: #5a2020;
}}
button.eara-header-btn.eara-header-reset {{
  background-color: #141414;
  color: #777777;
  border-color: #333333;
}}
window.eara-window.eara-focused button.eara-header-btn {{
  opacity: 1;
  border-color: #555555;
  color: #f0f0f0;
  background-color: #222222;
}}
window.eara-window.eara-focused button.eara-header-btn.eara-header-active {{
  background-color: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}}
window.eara-window.eara-focused button.eara-header-btn.eara-header-reset.eara-header-active {{
  color: #d71921;
}}
.eara-panel label {{
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-size: 11px;
  color: #aaaaaa;
}}
.eara-card listview label, .eara-card row label {{
  font-family: {ui}, {_FONT_UI_FALLBACK};
}}
.eara-card {{
  background-color: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 20px;
  padding: 16px;
}}
.eara-sound-cards flowboxchild {{
  min-width: 280px;
}}
.eara-sound-card {{
  min-width: 280px;
}}
.eara-eq-scroll {{
  min-height: 140px;
}}
.eara-card-title {{
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #999999;
}}
.eara-meta, .dim-label {{
  color: #b8b8b8;
  font-size: 13px;
}}
.eara-buttons {{
  background-color: #000000;
  border-bottom: 1px solid #1f1f1f;
  padding: 10px 16px;
}}
button.eara-tab {{
  border-radius: 999px;
  min-height: 34px;
  padding: 0 16px;
  background-color: transparent;
  color: #888888;
  border: 1px solid transparent;
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-size: 13px;
  font-weight: 600;
  opacity: 0.82;
}}
window.eara-window.eara-focused button.eara-tab {{
  opacity: 1;
  color: #cccccc;
}}
button.eara-tab:hover {{
  color: #ffffff;
  background-color: #161616;
  border-color: #2a2a2a;
}}
button.eara-tab.eara-tab-active {{
  background-color: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
  opacity: 1;
}}
window.eara-window.eara-focused button.eara-tab.eara-tab-active {{
  background-color: #ffffff;
  color: #000000;
}}
.eara-button-row {{
  padding: 4px 0;
}}
.eara-buttons-spacer {{
  min-width: 8px;
}}
windowcontrols button {{
  background: transparent;
  border: none;
  box-shadow: none;
  outline: none;
  padding: 0;
  margin: 0;
  min-width: 24px;
  min-height: 24px;
}}
windowcontrols button image {{
  background: transparent;
  border: none;
  box-shadow: none;
}}
headerbar button.flat {{
  background: transparent;
  border: none;
  box-shadow: none;
  outline: none;
  min-width: 24px;
  min-height: 24px;
  padding: 4px 8px;
  opacity: 0.7;
}}
window.eara-window.eara-focused headerbar button.flat {{
  opacity: 1;
}}
headerbar button.flat:hover {{
  background: alpha(currentColor, 0.08);
}}
.eara-content button:not(.flat):not(.eara-header-btn) {{
  border-radius: 999px;
  min-height: 34px;
  padding-left: 14px;
  padding-right: 14px;
  background-color: #1a1a1a;
  color: #c8c8c8;
  border: 1px solid #333333;
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-weight: 500;
  opacity: 0.78;
}}
window.eara-window.eara-focused .eara-content button:not(.flat):not(.eara-header-btn) {{
  opacity: 1;
  color: #f5f5f5;
  border-color: #444444;
  background-color: #1e1e1e;
}}
.eara-content button:not(.flat):not(.eara-header-btn):hover {{
  background-color: #282828;
  border-color: #555555;
}}
.eara-chip {{
  border-radius: 999px;
  background-color: #0a0a0a;
  color: #c0c0c0;
  border: 1px solid #2e2e2e;
  min-height: 36px;
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-weight: 500;
  opacity: 0.78;
}}
window.eara-window.eara-focused .eara-chip {{
  opacity: 1;
  color: #ffffff;
  border-color: #444444;
  background-color: #141414;
}}
.eara-chip-active {{
  background-color: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
  opacity: 1;
}}
window.eara-window.eara-focused .eara-chip-active {{
  background-color: #ffffff;
  color: #000000;
  border-color: #ffffff;
}}
.eara-chip-disconnect {{
  background-color: #1a1010;
  color: #fca5a5;
  border: 1px solid #5a2020;
}}
window.eara-window.eara-focused .eara-chip-disconnect {{
  color: #fecaca;
  border-color: #d71921;
  background-color: #301010;
  opacity: 1;
}}
.eara-chip-disconnect:hover {{
  background-color: #401010;
  border-color: #d71921;
}}
.eara-gesture-side {{
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #d71921;
  margin-top: 8px;
}}
.eara-gesture-type {{
  font-size: 13px;
  font-weight: 500;
  color: #dddddd;
  min-width: 120px;
}}
.eara-gesture-row {{
  padding: 4px 0;
}}
.eara-batt-cell.eara-batt-stale {{
  opacity: 0.62;
}}
.eara-batt-sub-muted {{
  color: #888888;
  font-size: 10px;
}}
.eara-about-window {{
  background-color: #0a0a0a;
  color: #f0f0f0;
}}
.eara-about-window .eara-about-card {{
  background-color: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 18px;
  padding: 18px;
}}
.eara-about-brand {{
  font-family: {dot}, {_FONT_DOT_FALLBACK};
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 5px;
  color: #ffffff;
}}
.eara-about-version {{
  font-size: 12px;
  color: #888888;
  margin-top: 4px;
}}
.eara-about-body {{
  font-size: 13px;
  line-height: 1.45;
  color: #cccccc;
}}
.eara-about-link {{
  color: #ffffff;
  font-weight: 600;
}}
.eara-about-coffee {{
  margin-top: 4px;
}}
button.eara-about-coffee {{
  background-color: #d71921;
  color: #ffffff;
  border-color: #d71921;
  font-weight: 700;
}}
button.eara-about-coffee:hover {{
  background-color: #ef2a32;
  border-color: #ef2a32;
}}
.eara-about-meta {{
  font-size: 11px;
  color: #777777;
}}
.eara-panel {{
  background-color: #111111;
  border: 1px solid #262626;
  border-radius: 16px;
  padding: 12px;
}}
.eara-content scale trough {{
  min-height: 6px;
  border-radius: 999px;
  background-color: #2a2a2a;
}}
.eara-content scale highlight {{
  background-color: #d71921;
  border-radius: 999px;
}}
.eara-toggles {{
  background-color: transparent;
}}
.eara-toggle-row {{
  padding: 11px 2px;
  border-bottom: 1px solid #242424;
}}
.eara-toggle-row:last-child {{
  border-bottom: none;
}}
.eara-toggle-label {{
  font-size: 14px;
  font-weight: 500;
  color: #e8e8e8;
}}
switch.eara-switch {{
  background-color: #141414;
  border: 1px solid #333333;
  border-radius: 999px;
  min-width: 50px;
  min-height: 28px;
  padding: 0;
  outline: none;
}}
switch.eara-switch:checked {{
  background-color: #d71921;
  border-color: #d71921;
}}
switch.eara-switch slider {{
  background-color: #555555;
  border: none;
  border-radius: 999px;
  min-width: 22px;
  min-height: 22px;
  margin: 2px;
}}
switch.eara-switch:checked slider {{
  background-color: #ffffff;
}}
window.eara-window.eara-focused switch.eara-switch {{
  border-color: #444444;
}}
window.eara-window.eara-focused switch.eara-switch:checked {{
  background-color: #ffffff;
  border-color: #ffffff;
}}
window.eara-window.eara-focused switch.eara-switch:checked slider {{
  background-color: #d71921;
}}
switch.eara-switch:focus {{
  outline: none;
  box-shadow: none;
}}
.eara-content dropdown {{
  border-radius: 12px;
  font-family: {ui}, {_FONT_UI_FALLBACK};
  font-size: 13px;
}}
"""


def _ui_text(label: Gtk.Label) -> Gtk.Label:
    label.add_css_class("eara-ui-text")
    return label


def _badge_label(text: str) -> Gtk.Label:
    label = _ui_text(Gtk.Label(label=text))
    label.add_css_class("eara-status-badge")
    return label


def _gesture_action_label(action: str) -> str:
    key = f"gesture_{action.replace('-', '_')}"
    text = t(key)
    return text if text != key else action.replace("-", " ").title()


def _mask_serial(value: str) -> str:
    text = (value or "").strip()
    if len(text) <= 6:
        return text
    return "…" + text[-6:]


def _open_uri(parent: Gtk.Window | None, uri: str) -> None:
    try:
        Gtk.show_uri(parent, uri, Gdk.CURRENT_TIME)
    except (TypeError, GLib.Error, OSError):
        import subprocess

        subprocess.Popen(["xdg-open", uri], start_new_session=True)  # noqa: S603


def _ensure_fonts() -> None:
    dest_dir = Path.home() / ".local/share/fonts/eara"
    dest_dir.mkdir(parents=True, exist_ok=True)
    installed = False
    for name in _FONT_FILES:
        dest = dest_dir / name
        if dest.is_file():
            continue
        for base in (Path(__file__).resolve().parents[1], Path("/usr/share/eara")):
            src = base / "packaging/fonts" / name
            if not src.is_file():
                continue
            try:
                dest.write_bytes(src.read_bytes())
                installed = True
            except OSError:
                pass
            break
    if installed:
        import subprocess

        subprocess.run(["fc-cache", "-f", str(dest_dir)], check=False, capture_output=True)


def _load_css() -> None:
    css = _build_css()
    provider = Gtk.CssProvider()
    provider.load_from_data(css, len(css))
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def _toggle_row(title: str) -> tuple[Gtk.Box, Gtk.Switch, Gtk.Label]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("eara-toggle-row")
    label = _ui_text(Gtk.Label(label=title, xalign=0, hexpand=True))
    label.add_css_class("eara-toggle-label")
    switch = Gtk.Switch()
    switch.add_css_class("eara-switch")
    switch.set_valign(Gtk.Align.CENTER)
    row.append(label)
    row.append(switch)
    return row, switch, label


class EarAWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.add_css_class("eara-window")
        self.set_default_size(520, 760)
        self.set_size_request(480, 640)
        self.device: Device | None = None
        self._busy = False
        self._last: dict = {}
        self._ignore_toggle = False
        self._ignore_listening = False
        self._eq_local = False
        self._codec_keys: list[str] = ["sbc"]
        self._listening_keys: list[str] = list(LISTENING_MODES.keys())
        self.toast = Adw.ToastOverlay()
        load_lang()
        _ensure_fonts()
        _load_css()
        try:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        except Exception:
            pass

        self._header_active = "connect"
        self._shutting_down = False
        self.connect("notify::is-active", self._on_active_changed)
        self.connect("close-request", self._on_close_request)
        self._update_focus_class()

        self.header = Adw.HeaderBar()
        self.btn_connect = Gtk.Button()
        self.btn_connect.add_css_class("eara-header-btn")
        self.btn_connect.add_css_class("eara-header-connect")
        self.btn_connect.add_css_class("eara-header-active")
        self.btn_connect.connect("clicked", self._on_connect_clicked)
        self.btn_reset = Gtk.Button()
        self.btn_reset.add_css_class("eara-header-btn")
        self.btn_reset.add_css_class("eara-header-reset")
        self.btn_reset.connect("clicked", self._on_reset_clicked)
        self.btn_refresh = Gtk.Button()
        self.btn_refresh.add_css_class("eara-tab")
        self.btn_refresh.connect("clicked", lambda *_: self._run(self._do_refresh))
        self.btn_about = Gtk.Button(label="?")
        self.btn_about.add_css_class("flat")
        self.btn_about.connect("clicked", lambda *_: self._about())
        self.header.pack_start(self.btn_connect)
        self.header.pack_start(self.btn_reset)
        self.header.pack_end(self.btn_about)

        self.stack = Adw.ViewStack()
        self.stack.add_css_class("eara-stack")
        self._tab_keys = ("device", "sound", "gestures", "tools")
        self._tab_buttons: dict[str, Gtk.Button] = {}

        # Hero strip
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hero.add_css_class("eara-hero")
        self.lbl_brand = Gtk.Label(label="E A R A", xalign=0)
        self.lbl_brand.add_css_class("eara-brand")
        self.lbl_tag = _ui_text(Gtk.Label(xalign=0))
        self.lbl_tag.add_css_class("eara-tag")
        hero.append(self.lbl_brand)
        hero.append(self.lbl_tag)

        self.page_device = self._page_device()
        self.page_sound = self._page_sound()
        self.page_gestures = self._page_gestures()
        self.page_tools = self._page_tools()
        self._stack_pages = [
            self.stack.add_titled(self.page_device, "device", t("tab_device")),
            self.stack.add_titled(self.page_sound, "sound", t("tab_sound")),
            self.stack.add_titled(self.page_gestures, "gestures", t("tab_gestures")),
            self.stack.add_titled(self.page_tools, "tools", t("tab_tools")),
        ]

        self.buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.buttons.add_css_class("eara-buttons")
        for key in self._tab_keys:
            btn = Gtk.Button()
            btn.add_css_class("eara-tab")
            btn.connect("clicked", lambda *_, k=key: self._show_tab(k))
            self._tab_buttons[key] = btn
            self.buttons.append(btn)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.buttons.append(spacer)
        self.buttons.append(self.btn_refresh)
        self._show_tab("device")

        self.toast.set_child(self.stack)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.header)
        outer.append(hero)
        outer.append(self.buttons)
        outer.append(self.toast)
        self.toast.set_vexpand(True)
        self.set_content(outer)
        self._apply_lang()
        GLib.idle_add(self._bootstrap)

    def _page_device(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("eara-content")
        box.set_margin_top(12)
        box.set_margin_bottom(16)
        box.set_margin_start(20)
        box.set_margin_end(20)

        lang_row = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.lbl_language = _ui_text(Gtk.Label())
        self.btn_en = Gtk.Button(label="EN")
        self.btn_uk = Gtk.Button(label="UA")
        self.btn_en.add_css_class("eara-chip")
        self.btn_uk.add_css_class("eara-chip")
        self.btn_en.connect("clicked", lambda *_: self._set_lang("en"))
        self.btn_uk.connect("clicked", lambda *_: self._set_lang("uk"))
        self._update_lang_buttons()
        lang_row.append(self.lbl_language)
        lang_row.append(self.btn_en)
        lang_row.append(self.btn_uk)
        box.append(lang_row)

        self.status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.status_card.add_css_class("eara-status-card")

        head = Gtk.Box(spacing=10)
        head.add_css_class("eara-status-head")
        self.status_dot = Gtk.Box()
        self.status_dot.add_css_class("eara-status-dot")
        self.status_dot.add_css_class("eara-dot-off")
        title_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_col.set_hexpand(True)
        self.status_name = _ui_text(Gtk.Label(xalign=0, wrap=True))
        self.status_name.add_css_class("eara-status-name")
        badges = Gtk.Box(spacing=6)
        badges.add_css_class("eara-status-badges")
        self.badge_bt = _badge_label("BT")
        self.badge_proto = _badge_label("RFCOMM")
        badges.append(self.badge_bt)
        badges.append(self.badge_proto)
        title_col.append(self.status_name)
        title_col.append(badges)
        head.append(self.status_dot)
        head.append(title_col)
        self.status_card.append(head)

        self.status_meta = _ui_text(Gtk.Label(wrap=True, xalign=0))
        self.status_meta.add_css_class("eara-status-meta")
        self.status_card.append(self.status_meta)

        batt_row = Gtk.FlowBox()
        batt_row.set_selection_mode(Gtk.SelectionMode.NONE)
        batt_row.set_max_children_per_line(3)
        batt_row.set_column_spacing(8)
        batt_row.set_row_spacing(8)
        batt_row.add_css_class("eara-status-batteries")
        self._batt_cells: dict[str, dict[str, Gtk.Widget]] = {}
        for key, short in (("left", "L"), ("right", "R"), ("case", "C")):
            batt_row.append(self._battery_cell(key, short))
        self.status_card.append(batt_row)

        modes = Gtk.Box(spacing=8)
        modes.add_css_class("eara-status-modes")
        self.chip_anc = _ui_text(Gtk.Label())
        self.chip_anc.add_css_class("eara-mode-chip")
        self.chip_eq = _ui_text(Gtk.Label())
        self.chip_eq.add_css_class("eara-mode-chip")
        modes.append(self.chip_anc)
        modes.append(self.chip_eq)
        self.status_card.append(modes)

        box.append(self.status_card)
        self._set_status_message(t("looking"), offline=True)

        pick_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_pick = _ui_text(Gtk.Label(xalign=0))
        self.device_drop = Gtk.DropDown.new_from_strings(["—"])
        self.device_drop.connect("notify::selected-item", self._on_device_changed)
        pick_row.append(self.lbl_pick)
        pick_row.append(self.device_drop)
        box.append(pick_row)

        self.audio_box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.audio_box.add_css_class("eara-button-row")
        self.btn_music = Gtk.Button()
        self.btn_calls = Gtk.Button()
        self.btn_disconnect = Gtk.Button()
        for b in (self.btn_music, self.btn_calls):
            b.add_css_class("eara-chip")
        self.btn_disconnect.add_css_class("eara-chip")
        self.btn_disconnect.add_css_class("eara-chip-disconnect")
        self.btn_music.connect("clicked", lambda *_: self._run(lambda: self._do_audio(False)))
        self.btn_calls.connect("clicked", lambda *_: self._run(lambda: self._do_audio(True)))
        self.btn_disconnect.connect("clicked", lambda *_: self._run(self._do_disconnect))
        self.audio_box.append(self.btn_music)
        self.audio_box.append(self.btn_calls)
        self.audio_box.append(self.btn_disconnect)
        box.append(self.audio_box)

        codec_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        codec_card.add_css_class("eara-card")
        self.lbl_codec = Gtk.Label(xalign=0, wrap=True)
        self.lbl_codec.add_css_class("eara-card-title")
        codec_row = Gtk.Box(spacing=8)
        self.codec_drop = Gtk.DropDown.new_from_strings(["sbc"])
        self.btn_codec = Gtk.Button()
        self.btn_codec.add_css_class("eara-chip")
        self.btn_codec.connect("clicked", lambda *_: self._apply_codec())
        codec_row.append(self.codec_drop)
        codec_row.append(self.btn_codec)
        self.lbl_codec_hint = Gtk.Label(wrap=True, xalign=0)
        self.lbl_codec_hint.add_css_class("dim-label")
        codec_card.append(self.lbl_codec)
        codec_card.append(codec_row)
        codec_card.append(self.lbl_codec_hint)
        box.append(codec_card)

        self.lbl_legal_dev = Gtk.Label(wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.lbl_legal_dev.add_css_class("dim-label")
        box.append(self.lbl_legal_dev)
        return Gtk.ScrolledWindow(child=box)

    def _battery_cell(self, key: str, short: str) -> Gtk.Box:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        cell.add_css_class("eara-batt-cell")
        cell.set_hexpand(True)
        head = Gtk.Box(spacing=6)
        lbl_side = _ui_text(Gtk.Label(label=short, xalign=0))
        lbl_side.add_css_class("eara-batt-side")
        lbl_pct = _ui_text(Gtk.Label(label="—", xalign=1))
        lbl_pct.add_css_class("eara-batt-pct")
        head.append(lbl_side)
        head.append(lbl_pct)
        bar = Gtk.ProgressBar()
        bar.add_css_class("eara-batt-bar")
        bar.set_show_text(False)
        lbl_sub = _ui_text(Gtk.Label(label="", xalign=0, wrap=True))
        lbl_sub.add_css_class("eara-batt-sub")
        lbl_sub.set_max_width_chars(16)
        cell.append(head)
        cell.append(bar)
        cell.append(lbl_sub)
        self._batt_cells[key] = {"pct": lbl_pct, "bar": bar, "sub": lbl_sub, "cell": cell}
        return cell

    def _set_badge(self, label: Gtk.Label, text: str, kind: str) -> None:
        label.set_text(text)
        label.remove_css_class("eara-status-badge-ok")
        label.remove_css_class("eara-status-badge-warn")
        label.remove_css_class("eara-status-badge-bad")
        if kind:
            label.add_css_class(f"eara-status-badge-{kind}")

    def _set_status_message(self, message: str, *, offline: bool = False) -> None:
        self.status_name.set_text(message)
        self.status_meta.set_text("")
        self._set_badge(self.badge_bt, t("bt_off").upper(), "bad" if offline else "")
        self._set_badge(self.badge_proto, t("protocol_no").upper(), "bad" if offline else "")
        self.status_dot.remove_css_class("eara-dot-ok")
        self.status_dot.remove_css_class("eara-dot-warn")
        self.status_dot.add_css_class("eara-dot-off" if offline else "eara-dot-warn")
        for key in ("left", "right", "case"):
            self._update_battery_cell(key, None)
        self.chip_anc.set_text("")
        self.chip_eq.set_text("")
        self.chip_anc.set_visible(False)
        self.chip_eq.set_visible(False)

    def _update_battery_cell(self, key: str, item: dict | None) -> None:
        cell = self._batt_cells[key]
        pct = cell["pct"]
        bar = cell["bar"]
        sub = cell["sub"]
        box = cell["cell"]
        bar.remove_css_class("eara-batt-low")
        bar.remove_css_class("eara-batt-charge")
        box.remove_css_class("eara-batt-stale")
        sub.remove_css_class("eara-batt-sub-muted")
        sub.remove_css_class("eara-batt-sub-ok")
        box.remove_css_class("eara-batt-off")
        if isinstance(item, dict) and item.get("available"):
            level = max(0, min(100, int(item.get("level", 0))))
            pct.set_text(f"{level}%")
            bar.set_fraction(level / 100.0)
            bar.set_visible(True)
            if item.get("stale"):
                sub.set_text(t("case_cached"))
                sub.add_css_class("eara-batt-sub-muted")
                box.add_css_class("eara-batt-stale")
            elif item.get("charging"):
                sub.set_text(t("charging"))
                sub.add_css_class("eara-batt-sub-ok")
                bar.add_css_class("eara-batt-charge")
            else:
                sub.set_text("")
            if level <= 20:
                bar.add_css_class("eara-batt-low")
            return
        pct.set_text("—")
        bar.set_fraction(0.0)
        bar.set_visible(True)
        box.add_css_class("eara-batt-off")
        if key == "case":
            sub.set_text(t("case_open_hint"))
            sub.add_css_class("eara-batt-sub-muted")
        else:
            sub.set_text("")

    def _page_sound(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.add_css_class("eara-content")
        outer.set_margin_top(12)
        outer.set_margin_bottom(16)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        cards = Gtk.FlowBox()
        cards.add_css_class("eara-sound-cards")
        cards.set_selection_mode(Gtk.SelectionMode.NONE)
        cards.set_max_children_per_line(2)
        cards.set_min_children_per_line(1)
        cards.set_column_spacing(12)
        cards.set_row_spacing(12)
        cards.set_homogeneous(True)

        quick_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        quick_card.add_css_class("eara-card")
        quick_card.add_css_class("eara-sound-card")
        quick_card.set_vexpand(True)
        quick_card.set_hexpand(True)
        self.lbl_quick_title = Gtk.Label(xalign=0.5)
        self.lbl_quick_title.add_css_class("eara-card-title")
        quick_card.append(self.lbl_quick_title)

        self.row_bass, self.bass_switch, self.lbl_bass = _toggle_row(t("bass"))
        self.row_ied, self.ied_switch, self.lbl_ied = _toggle_row(t("in_ear"))
        self.row_lat, self.lat_switch, self.lbl_lat = _toggle_row(t("latency"))
        self.row_adv, self.adv_switch, self.lbl_adv = _toggle_row(t("adv_eq"))
        self.row_panc, self.panc_switch, self.lbl_panc = _toggle_row(t("personal_anc"))
        self.bass_switch.connect("notify::active", lambda *_: self._on_toggle("bass"))
        self.ied_switch.connect("notify::active", lambda *_: self._on_toggle("ied"))
        self.lat_switch.connect("notify::active", lambda *_: self._on_toggle("lat"))
        self.adv_switch.connect("notify::active", lambda *_: self._on_toggle("adv"))
        self.panc_switch.connect("notify::active", lambda *_: self._on_toggle("panc"))
        toggles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        toggles.add_css_class("eara-toggles")
        for row in (self.row_bass, self.row_ied, self.row_lat, self.row_adv, self.row_panc):
            toggles.append(row)
        quick_card.append(toggles)

        self.listening_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.lbl_listening = _ui_text(Gtk.Label(xalign=0))
        listening_row = Gtk.Box(spacing=8)
        self.listening_drop = Gtk.DropDown.new_from_strings(["normal"])
        self.listening_drop.connect("notify::selected", self._on_listening_changed)
        listening_row.append(self.listening_drop)
        self.listening_box.append(self.lbl_listening)
        self.listening_box.append(listening_row)
        quick_card.append(self.listening_box)

        self.lbl_noise = _ui_text(Gtk.Label(xalign=0))
        quick_card.append(self.lbl_noise)
        self.anc_flow = Gtk.FlowBox(max_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE)
        self.anc_buttons: dict[str, Gtk.Button] = {}
        for mode in ("off", "transparency", "high", "mid", "low", "adaptive"):
            btn = Gtk.Button()
            btn.add_css_class("eara-chip")
            btn.connect("clicked", lambda *_, m=mode: self._run(lambda: self._require().set_anc(m)))
            self.anc_buttons[mode] = btn
            self.anc_flow.append(btn)
        quick_card.append(self.anc_flow)
        quick_wrap = Gtk.FlowBoxChild()
        quick_wrap.set_can_focus(False)
        quick_wrap.set_child(quick_card)
        cards.append(quick_wrap)

        eq_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        eq_card.add_css_class("eara-card")
        eq_card.add_css_class("eara-sound-card")
        eq_card.set_vexpand(True)
        eq_card.set_hexpand(True)
        self.lbl_eq_title = Gtk.Label(xalign=0.5)
        self.lbl_eq_title.add_css_class("eara-card-title")
        eq_card.append(self.lbl_eq_title)
        self.lbl_eq = _ui_text(Gtk.Label(xalign=0))
        eq_card.append(self.lbl_eq)
        eq = Gtk.FlowBox(max_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE)
        self.eq_flow = eq
        self.eq_buttons: dict[str, Gtk.Button] = {}
        for key in ("balanced", "more_bass", "more_treble", "voice"):
            b = Gtk.Button()
            b.add_css_class("eara-chip")
            b.connect("clicked", lambda *_, k=key: self._run(lambda: self._require().set_eq(k)))
            self.eq_buttons[key] = b
            eq.append(b)
        eq_card.append(eq)
        self.lbl_custom = _ui_text(Gtk.Label(xalign=0, wrap=True))
        eq_card.append(self.lbl_custom)
        self.graphic_box = Gtk.Box(spacing=6)
        self.graphic_box.add_css_class("eara-panel")
        self.eq_bands: list[Gtk.Scale] = []
        for hz in GRAPHIC_HZ:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lab = _ui_text(Gtk.Label(label=str(hz) if hz < 1000 else f"{hz // 1000}k"))
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, -6, 6, 0.5)
            scale.set_inverted(True)
            scale.set_value(0)
            scale.set_vexpand(True)
            scale.set_size_request(24, 100)
            col.append(lab)
            col.append(scale)
            self.graphic_box.append(col)
            self.eq_bands.append(scale)
        eq_scroll = Gtk.ScrolledWindow()
        eq_scroll.add_css_class("eara-eq-scroll")
        eq_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        eq_scroll.set_propagate_natural_height(True)
        eq_scroll.set_child(self.graphic_box)
        eq_card.append(eq_scroll)
        self.btn_apply_eq = Gtk.Button()
        self.btn_apply_eq.add_css_class("eara-chip")
        self.btn_apply_eq.connect("clicked", lambda *_: self._apply_eq())
        eq_card.append(self.btn_apply_eq)
        eq_wrap = Gtk.FlowBoxChild()
        eq_wrap.set_can_focus(False)
        eq_wrap.set_child(eq_card)
        cards.append(eq_wrap)

        outer.append(cards)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(outer)
        return scroll

    def _page_gestures(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("eara-content")
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.lbl_gestures = _ui_text(Gtk.Label(wrap=True, xalign=0))
        box.append(self.lbl_gestures)
        self.gesture_rows: list[tuple[str, str, Gtk.DropDown, Gtk.Label, Gtk.Button, Gtk.Label]] = []
        self._gesture_action_keys = list(GESTURE_ACTIONS.keys())
        action_labels = [_gesture_action_label(key) for key in self._gesture_action_keys]
        for side in ("left", "right"):
            side_lab = _ui_text(Gtk.Label(xalign=0))
            side_lab.add_css_class("eara-gesture-side")
            box.append(side_lab)
            for gtype in GESTURE_TYPES:
                drop = Gtk.DropDown.new_from_strings(action_labels)
                lab = _ui_text(Gtk.Label(label=gtype, xalign=0, hexpand=True))
                lab.add_css_class("eara-gesture-type")
                save = Gtk.Button()
                save.add_css_class("eara-chip")
                save.connect(
                    "clicked",
                    lambda *_, s=side, tpe=gtype, d=drop: self._save_gesture(s, tpe, d),
                )
                row = Gtk.Box(spacing=8)
                row.add_css_class("eara-gesture-row")
                row.append(lab)
                row.append(drop)
                row.append(save)
                box.append(row)
                self.gesture_rows.append((side, gtype, drop, lab, save, side_lab))
        self._sync_gesture_dropdowns(merge_gestures({"left": {}, "right": {}}))
        return Gtk.ScrolledWindow(child=box)

    def _sync_gesture_dropdowns(self, gestures: dict) -> None:
        for side, gtype, drop, *_rest in self.gesture_rows:
            action = (gestures.get(side) or {}).get(gtype, "no-action")
            if action not in self._gesture_action_keys:
                action = "no-action"
            drop.set_selected(self._gesture_action_keys.index(action))

    def _page_tools(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("eara-content")
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.btn_find_l = Gtk.Button()
        self.btn_find_r = Gtk.Button()
        self.btn_find_both = Gtk.Button()
        self.btn_stop_ring = Gtk.Button()
        for b in (self.btn_find_l, self.btn_find_r, self.btn_find_both, self.btn_stop_ring):
            b.add_css_class("eara-chip")
        self.btn_find_l.connect("clicked", lambda *_: self._run(lambda: self._require().ring("left")))
        self.btn_find_r.connect("clicked", lambda *_: self._run(lambda: self._require().ring("right")))
        self.btn_find_both.connect("clicked", lambda *_: self._run(lambda: self._require().ring("both")))
        self.btn_stop_ring.connect("clicked", lambda *_: self._run(lambda: self._require().ring("off")))
        box.append(self.btn_find_l)
        box.append(self.btn_find_r)
        box.append(self.btn_find_both)
        box.append(self.btn_stop_ring)

        fit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fit_card.add_css_class("eara-card")
        self.fit_card = fit_card
        self.lbl_fit_hint = _ui_text(Gtk.Label(wrap=True, xalign=0))
        self.lbl_fit_hint.add_css_class("dim-label")
        fit_card.append(self.lbl_fit_hint)
        self.btn_fit = Gtk.Button()
        self.btn_fit.add_css_class("eara-chip")
        self.btn_fit.connect("clicked", lambda *_: self._run(self._do_fit))
        fit_card.append(self.btn_fit)
        self.fit_label = _ui_text(Gtk.Label(wrap=True, xalign=0))
        fit_card.append(self.fit_label)
        box.append(fit_card)

        self.lbl_legal = Gtk.Label(wrap=True, xalign=0)
        self.lbl_legal.add_css_class("dim-label")
        box.append(self.lbl_legal)
        return Gtk.ScrolledWindow(child=box)

    def _show_tab(self, name: str) -> None:
        self.stack.set_visible_child_name(name)
        for key, btn in self._tab_buttons.items():
            if key == name:
                btn.add_css_class("eara-tab-active")
            else:
                btn.remove_css_class("eara-tab-active")

    def _on_active_changed(self, *_args) -> None:
        self._update_focus_class()

    def _update_focus_class(self) -> None:
        if self.is_active():
            self.add_css_class("eara-focused")
        else:
            self.remove_css_class("eara-focused")

    def _set_header_active(self, which: str) -> None:
        self._header_active = which
        self.btn_connect.remove_css_class("eara-header-active")
        self.btn_reset.remove_css_class("eara-header-active")
        if which == "connect":
            self.btn_connect.add_css_class("eara-header-active")
        elif which == "reset":
            self.btn_reset.add_css_class("eara-header-active")

    def _on_connect_clicked(self, *_args) -> None:
        self._set_header_active("connect")
        self._run(self._do_connect)

    def _on_reset_clicked(self, *_args) -> None:
        self._set_header_active("reset")
        self._run(self._do_reset)

    def _apply_lang(self) -> None:
        self.set_title(t("app_title"))
        self.btn_connect.set_label(t("connect"))
        self.btn_reset.set_label(t("reset"))
        self.btn_refresh.set_label(t("refresh"))
        self.btn_about.set_tooltip_text(t("about"))
        self.lbl_tag.set_text(t("brand_tag"))
        titles = ("tab_device", "tab_sound", "tab_gestures", "tab_tools")
        for key, title_key in zip(self._tab_keys, titles):
            self._tab_buttons[key].set_label(t(title_key))
        for page, key in zip(self._stack_pages, titles):
            page.set_title(t(key))
        self.lbl_language.set_text(t("language"))
        self.lbl_pick.set_text(t("pick_device"))
        self.btn_music.set_label(t("music"))
        self.btn_calls.set_label(t("calls"))
        self.btn_disconnect.set_label(t("disconnect"))
        self.lbl_codec.set_text(t("codec"))
        self.btn_codec.set_label(t("apply_codec"))
        self.lbl_codec_hint.set_text(t("codec_hint"))
        self.lbl_quick_title.set_text(t("quick_settings_title"))
        self.lbl_eq_title.set_text(t("equalizer_title"))
        self.lbl_noise.set_text(t("noise"))
        self.lbl_eq.set_text(t("eq"))
        self.lbl_custom.set_text(t("custom_eq"))
        self.btn_apply_eq.set_label(t("apply_eq"))
        self.lbl_bass.set_text(t("bass"))
        self.lbl_ied.set_text(t("in_ear"))
        self.lbl_lat.set_text(t("latency"))
        self.lbl_adv.set_text(t("adv_eq"))
        self.lbl_panc.set_text(t("personal_anc"))
        self.lbl_listening.set_text(t("listening_mode"))
        listening_labels = [t(f"listening_{mode}") for mode in LISTENING_MODES]
        self._listening_keys = list(LISTENING_MODES.keys())
        self.listening_drop.set_model(Gtk.StringList.new(listening_labels))
        for mode, btn in self.anc_buttons.items():
            btn.set_label(t(mode))
        for key, btn in self.eq_buttons.items():
            btn.set_label(t(key))
        self.lbl_gestures.set_text(t("gestures_hint"))
        seen = set()
        for side, _gtype, drop, _lab, save, side_lab in self.gesture_rows:
            save.set_label(t("set"))
            if side not in seen:
                side_lab.set_text(t(side).upper())
                seen.add(side)
            drop.set_model(Gtk.StringList.new([_gesture_action_label(k) for k in self._gesture_action_keys]))
        gestures = (getattr(self, "_last", None) or {}).get("gestures")
        if isinstance(gestures, dict):
            self._sync_gesture_dropdowns(gestures)
        self.btn_find_l.set_label(t("find_left"))
        self.btn_find_r.set_label(t("find_right"))
        self.btn_find_both.set_label(t("find_both"))
        self.btn_stop_ring.set_label(t("stop_ring"))
        self.btn_fit.set_label(t("fit"))
        self.lbl_fit_hint.set_text(t("fit_hint"))
        self.lbl_legal.set_text(t("legal"))
        self.lbl_legal_dev.set_text(t("legal"))
        if not getattr(self, "_last", None):
            self._set_status_message(t("looking"), offline=True)

    def _update_lang_buttons(self) -> None:
        from eara.i18n import LANG

        for code, btn in (("en", self.btn_en), ("uk", self.btn_uk)):
            if LANG == code:
                btn.add_css_class("eara-chip-active")
            else:
                btn.remove_css_class("eara-chip-active")

    def _set_lang(self, lang: str) -> None:
        set_lang(lang)
        self._apply_lang()
        self._update_lang_buttons()
        self._paint()

    def _on_device_changed(self, *_args) -> None:
        if self._busy:
            return
        picked = self._selected_device()
        if picked:
            self.device = picked
            self._run(self._do_refresh)

    def _on_listening_changed(self, *_args) -> None:
        if self._busy or self._ignore_listening:
            return
        idx = int(self.listening_drop.get_selected())
        if 0 <= idx < len(self._listening_keys):
            mode = self._listening_keys[idx]
            self._run(lambda: self._require().set_listening_mode(mode))

    def _fill_devices(self) -> None:
        devices = bluez.paired_devices()
        names = [f"{d['name']}  ({d['address']})" for d in devices] or ["—"]
        self._device_list = devices
        model = Gtk.StringList.new(names)
        self.device_drop.set_model(model)
        if self.device:
            for i, d in enumerate(devices):
                if d["address"] == self.device.address:
                    self.device_drop.set_selected(i)
                    break

    def _selected_device(self) -> Device | None:
        devices = getattr(self, "_device_list", [])
        idx = int(self.device_drop.get_selected())
        if 0 <= idx < len(devices):
            d = devices[idx]
            return Device(d["address"], d["name"])
        return None

    def _require(self) -> Device:
        picked = self._selected_device()
        if picked:
            self.device = picked
            return picked
        if not self.device:
            self.device = Device.discover()
        return self.device

    def _about(self) -> None:
        win = Adw.Window(transient_for=self, modal=True)
        win.add_css_class("eara-about-window")
        win.set_default_size(420, 360)
        win.set_title(t("about"))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(20)
        outer.set_margin_bottom(20)
        outer.set_margin_start(20)
        outer.set_margin_end(20)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("eara-about-card")
        brand = Gtk.Label(label="E A R A", xalign=0)
        brand.add_css_class("eara-about-brand")
        version = _ui_text(Gtk.Label(label=__version__, xalign=0))
        version.add_css_class("eara-about-version")
        body = _ui_text(Gtk.Label(label=t("about_blurb"), wrap=True, xalign=0))
        body.add_css_class("eara-about-body")
        link = Gtk.LinkButton(
            label="github.com/oneydef/EarA-linux",
            uri="https://github.com/oneydef/EarA-linux",
        )
        link.add_css_class("eara-about-link")
        link.set_halign(Gtk.Align.START)
        meta = _ui_text(Gtk.Label(label="Copyright © 2026 oneydef", xalign=0))
        meta.add_css_class("eara-about-meta")
        support_title = _ui_text(Gtk.Label(label=t("about_support").upper(), xalign=0))
        support_title.add_css_class("eara-tag")
        support = _ui_text(Gtk.Label(label=t("about_support_body"), wrap=True, xalign=0))
        support.add_css_class("eara-about-meta")
        coffee = Gtk.Button(label=t("about_coffee_btn"))
        coffee.add_css_class("eara-chip")
        coffee.add_css_class("eara-about-coffee")
        coffee.set_halign(Gtk.Align.START)
        coffee.connect("clicked", lambda *_: _open_uri(win, SUPPORT_URL))
        card.append(brand)
        card.append(version)
        card.append(body)
        card.append(link)
        card.append(meta)
        card.append(support_title)
        card.append(support)
        card.append(coffee)
        outer.append(card)

        close = Gtk.Button(label=t("about_close"))
        close.add_css_class("eara-chip")
        close.set_halign(Gtk.Align.END)
        close.connect("clicked", lambda *_: win.close())
        outer.append(close)

        win.set_content(outer)
        win.present()

    def _show(self, text: str) -> None:
        self.toast.add_toast(Adw.Toast(title=text))

    def _apply_eq(self) -> None:
        gains = [s.get_value() for s in self.eq_bands]
        self._eq_local = True
        self._run(lambda: self._do_custom_eq(gains))

    def _apply_codec(self) -> None:
        idx = int(self.codec_drop.get_selected())
        keys = self._codec_keys
        name = keys[idx] if 0 <= idx < len(keys) else "sbc"
        self._run(lambda: self._do_codec(name))

    def _save_gesture(self, side: str, gtype: str, drop: Gtk.DropDown) -> None:
        selected = int(drop.get_selected())
        self._run(lambda: self._do_gesture(side, gtype, selected))

    def _busy_widgets(self) -> list:
        widgets: list = [
            self.btn_connect,
            self.btn_reset,
            self.btn_refresh,
            self.btn_music,
            self.btn_calls,
            self.btn_disconnect,
            self.btn_apply_eq,
            self.btn_codec,
            self.device_drop,
            self.btn_find_l,
            self.btn_find_r,
            self.btn_find_both,
            self.btn_stop_ring,
            self.btn_fit,
            self.listening_drop,
        ]
        widgets.extend(self.anc_buttons.values())
        widgets.extend(self.eq_buttons.values())
        for _side, _gtype, drop, _lab, save, _side_lab in self.gesture_rows:
            widgets.extend((drop, save))
        for switch in (
            self.bass_switch,
            self.ied_switch,
            self.lat_switch,
            self.adv_switch,
            self.panc_switch,
        ):
            widgets.append(switch)
        return widgets

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in self._busy_widgets():
            widget.set_sensitive(not busy)

    def _run(self, fn) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker():
            err = None
            try:
                fn()
            except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
                err = str(exc)

            def done():
                self._set_busy(False)
                if err:
                    self._show(err)
                else:
                    self._paint()

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def _bootstrap(self) -> bool:
        self._fill_devices()
        try:
            self.device = Device.discover()
            self._set_status_message(
                t("found", name=self.device.name, address=self.device.address),
                offline=False,
            )
            self._fill_devices()
            self._run(self._do_refresh)
        except LookupError:
            self._set_status_message(t("no_device"), offline=True)
        return False

    def _do_connect(self) -> None:
        GLib.idle_add(lambda: self._show(t("connect_busy")) or False)
        result = self._require().connect_audio(False)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error")))
        self._last = self.device.status() if self.device else {}
        GLib.idle_add(lambda: self._show(t("connect_ok")) or False)

    def _do_reset(self) -> None:
        result = self._require().reset_connection()
        self._last = self.device.status() if self.device else {}
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "Reset did not restore A2DP"))
        GLib.idle_add(lambda: self._show(t("reset_ok")) or False)

    def _do_disconnect(self) -> None:
        ear = self._require()
        name = ear.name
        ear.disconnect_audio()
        self._last = {
            "name": name,
            "bt_connected": False,
            "protocol": False,
        }
        GLib.idle_add(lambda: self._show(t("disconnect_ok")) or False)

    def _shutdown_bluetooth(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self.device:
            self.device.shutdown()
        else:
            try:
                bluez.power_off()
            except Exception:
                pass

    def _on_close_request(self, *_args) -> bool:
        self._shutdown_bluetooth()
        return False

    def _do_refresh(self) -> None:
        self._last = self._require().status()

    def _do_audio(self, mic: bool) -> None:
        ear = self._require()
        result = ear.connect_audio(with_mic=mic)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "Audio switch failed"))
        self._last = ear.status()
        if mic:
            GLib.idle_add(lambda: self._show(t("mic_ok")) or False)

    def _do_custom_eq(self, gains: list[float]) -> None:
        self._require().set_graphic_eq(gains)
        self._last = self.device.status() if self.device else {}

    def _do_codec(self, name: str) -> None:
        result = self._require().set_codec(name)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error")))
        self._last = self.device.status() if self.device else {}

    def _do_gesture(self, side: str, gtype: str, selected: int) -> None:
        action = self._gesture_action_keys[selected]
        self._require().set_gesture(side, gtype, action)
        self._last = self._require().status()

    def _do_fit(self) -> None:
        GLib.idle_add(lambda: self._show(t("fit_running")) or False)
        try:
            self._fit = self._require().ear_tip_test()
        except RuntimeError as exc:
            key = str(exc)
            if key in ("fit_timeout", "fit_unsupported"):
                raise RuntimeError(t(key)) from exc
            raise
        GLib.idle_add(self._update_fit_label)

    def _update_fit_label(self) -> bool:
        if getattr(self, "_fit", None):
            self.fit_label.set_text(
                f"{t('fit_result')}: "
                + format_ear_tip(
                    self._fit,
                    left=t("left"),
                    right=t("right"),
                    good=t("fit_good"),
                    poor=t("fit_poor"),
                )
            )
        return False

    def _on_toggle(self, which: str) -> None:
        if self._busy or self._ignore_toggle or not self.device:
            return
        enabled = {
            "bass": self.bass_switch.get_active(),
            "ied": self.ied_switch.get_active(),
            "lat": self.lat_switch.get_active(),
            "adv": self.adv_switch.get_active(),
            "panc": self.panc_switch.get_active(),
        }[which]
        self._run(lambda: self._toggle(which, enabled))

    def _toggle(self, which: str, enabled: bool) -> None:
        ear = self._require()
        if which == "bass":
            ear.set_bass(enabled)
        elif which == "ied":
            ear.set_in_ear_detection(enabled)
        elif which == "lat":
            ear.set_latency(enabled)
        elif which == "adv":
            ear.set_advanced_eq(enabled)
        elif which == "panc":
            ear.set_personalized_anc(enabled)
        self._last = ear.status()

    def _set_chip_active(self, buttons: dict[str, Gtk.Button], active: str | None) -> None:
        wire = {
            "balanced": "balanced",
            "more_bass": "more_bass",
            "more_treble": "more_treble",
            "voice": "voice",
            "bass": "more_bass",
            "treble": "more_treble",
        }
        pick = wire.get(active or "", active)
        for key, btn in buttons.items():
            if pick and key == pick:
                btn.add_css_class("eara-chip-active")
            else:
                btn.remove_css_class("eara-chip-active")

    def _apply_capabilities(self, caps: dict) -> None:
        self.row_bass.set_visible(bool(caps.get("bass_enhance")))
        self.row_ied.set_visible(bool(caps.get("in_ear", True)))
        self.row_lat.set_visible(bool(caps.get("low_latency", True)))
        self.row_adv.set_visible(bool(caps.get("advanced_eq", True)))
        self.row_panc.set_visible(bool(caps.get("personalized_anc")))
        self.listening_box.set_visible(bool(caps.get("listening_mode")))
        self.lbl_noise.set_visible(bool(caps.get("anc")))
        self.anc_flow.set_visible(bool(caps.get("anc")))
        self.lbl_eq.set_visible(bool(caps.get("eq_presets", True)))
        self.eq_flow.set_visible(bool(caps.get("eq_presets", True)))
        self.graphic_box.set_visible(bool(caps.get("custom_eq", True)))
        self.btn_apply_eq.set_visible(bool(caps.get("custom_eq", True)))
        self.lbl_custom.set_visible(bool(caps.get("custom_eq", True)))
        find_visible = bool(caps.get("find_my", True))
        self.btn_find_l.set_visible(find_visible)
        self.btn_find_r.set_visible(find_visible)
        self.btn_find_both.set_visible(find_visible)
        self.btn_stop_ring.set_visible(find_visible)
        gestures_tab = bool(caps.get("gestures", True))
        self._tab_buttons["gestures"].set_visible(gestures_tab)
        if not gestures_tab and self.stack.get_visible_child_name() == "gestures":
            self._show_tab("device")

    def _paint(self) -> None:
        status = getattr(self, "_last", None) or {}
        if getattr(self, "_fit", None):
            self._update_fit_label()
        caps = (status.get("model") or {}).get("features") or {}
        if not caps and self.device:
            caps = self.device.model.as_dict().get("features") or {}
        self._apply_capabilities(caps)
        if hasattr(self, "fit_card"):
            name = (status.get("name") or (self.device.name if self.device else "")).lower()
            show_fit = bool(caps.get("ear_tip_fit", True)) or "ear (a)" in name
            self.fit_card.set_visible(show_fit)
        if not status:
            if hasattr(self, "fit_card") and self.device:
                nm = self.device.name.lower()
                self.fit_card.set_visible(self.device.model.ear_tip_fit or "ear (a)" in nm)
            return
        name = status.get("name") or "—"
        model = (status.get("model") or {}).get("name") or name
        bt_ok = bool(status.get("bt_connected"))
        proto_ok = bool(status.get("protocol"))
        self.status_name.set_text(name)
        if bt_ok and proto_ok:
            headline = t("status_ready")
            dot = "eara-dot-ok"
        elif bt_ok:
            headline = t("status_partial")
            dot = "eara-dot-warn"
        else:
            headline = t("status_offline")
            dot = "eara-dot-off"
        self.status_dot.remove_css_class("eara-dot-ok")
        self.status_dot.remove_css_class("eara-dot-warn")
        self.status_dot.remove_css_class("eara-dot-off")
        self.status_dot.add_css_class(dot)
        self._set_badge(self.badge_bt, t("bt_on" if bt_ok else "bt_off").upper(), "ok" if bt_ok else "bad")
        self._set_badge(
            self.badge_proto,
            t("protocol_ok" if proto_ok else "protocol_no").upper(),
            "ok" if proto_ok else ("warn" if bt_ok else "bad"),
        )
        fw = status.get("firmware") or "—"
        serial_raw = status.get("serial") or status.get("address") or "—"
        serial = _mask_serial(str(serial_raw))
        self.status_meta.set_text(f"{headline} · {model} · fw {fw} · {serial}")
        battery = status.get("battery") or {}
        for key in ("left", "right", "case"):
            item = battery.get(key)
            self._update_battery_cell(key, item if isinstance(item, dict) else None)
        anc_name = status.get("anc")
        eq_name = status.get("eq")
        if isinstance(anc_name, str) and anc_name:
            self.chip_anc.set_text(f"ANC · {t(anc_name)}")
            self.chip_anc.set_visible(True)
        else:
            self.chip_anc.set_visible(False)
        if isinstance(eq_name, str) and eq_name:
            eq_label = t(eq_name) if eq_name in ("balanced", "more_bass", "more_treble", "voice") else eq_name
            self.chip_eq.set_text(f"EQ · {eq_label}")
            self.chip_eq.set_visible(True)
        else:
            self.chip_eq.set_visible(False)
        if isinstance(eq_name, str):
            self._set_chip_active(self.eq_buttons, eq_name)
        if isinstance(anc_name, str):
            self._set_chip_active(self.anc_buttons, anc_name)
        gestures = status.get("gestures")
        if isinstance(gestures, dict):
            self._sync_gesture_dropdowns(gestures)
        self._ignore_toggle = True
        try:
            if status.get("latency") is not None:
                self.lat_switch.set_active(bool(status["latency"]))
            if status.get("in_ear") is not None:
                self.ied_switch.set_active(bool(status["in_ear"]))
            bass = status.get("bass") or {}
            if isinstance(bass, dict) and "enabled" in bass:
                self.bass_switch.set_active(bool(bass["enabled"]))
            if status.get("advanced_eq") is not None:
                self.adv_switch.set_active(bool(status["advanced_eq"]))
            if status.get("personalized_anc") is not None:
                self.panc_switch.set_active(bool(status["personalized_anc"]))
        finally:
            self._ignore_toggle = False
        listening = status.get("listening")
        if isinstance(listening, str) and listening in self._listening_keys:
            self._ignore_listening = True
            try:
                self.listening_drop.set_selected(self._listening_keys.index(listening))
            finally:
                self._ignore_listening = False
        graphic = status.get("graphic_eq")
        if isinstance(graphic, list) and not self._eq_local:
            for scale, value in zip(self.eq_bands, graphic):
                scale.set_value(float(value))
        audio_info = status.get("audio") or {}
        options = list(audio_info.get("codecs") or [])
        keys = [str(item.get("key") or "sbc") for item in options] or ["sbc"]
        advertised = {str(item.get("key") or "") for item in options}
        self.lbl_codec_hint.set_text(
            t("codec_hint") if "lhdc" in advertised else t("codec_no_lhdc")
        )
        if keys != self._codec_keys:
            self._codec_keys = keys
            selected = int(self.codec_drop.get_selected())
            self.codec_drop.set_model(Gtk.StringList.new([k.upper().replace("_", " ") for k in keys]))
            current = (audio_info.get("codec") or "sbc").lower().replace("-", "_")
            if current in keys:
                self.codec_drop.set_selected(keys.index(current))
            elif 0 <= selected < len(keys):
                self.codec_drop.set_selected(selected)
        extra = []
        if audio_info.get("codec"):
            extra.append(str(audio_info["codec"]))
        if status.get("device_codec"):
            extra.append(f"device {status['device_codec']}")
        if extra:
            self.lbl_codec_hint.set_text(self.lbl_codec_hint.get_text() + "  ·  " + " / ".join(extra))


class EarAApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="io.github.oneydef.eara")

    def do_shutdown(self) -> None:  # noqa: N802
        win = self.props.active_window
        if isinstance(win, EarAWindow):
            win._shutdown_bluetooth()
        super().do_shutdown()

    def do_activate(self) -> None:  # noqa: N802
        win = self.props.active_window
        if not win:
            win = EarAWindow(self)
        win.present()


def run() -> int:
    return EarAApp().run(None)
