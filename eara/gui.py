"""GTK4 / Adwaita companion UI — Nothing-inspired black / white / red theme."""

from __future__ import annotations

from eara.motion import MotionButton, MotionSwitch, SelectionBox, MotionStack, motion_scale, GestureLabel
from eara import motion, operations
from eara.diagnostics import timed
from copy import deepcopy

import math
import sysconfig
import threading
import traceback
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from eara import __version__
from eara import SUPPORT_URL
from eara.i18n import load_lang, power_off_on_exit, set_lang, set_power_off_on_exit, t
from eara.protocol import (
    CMF_BUDS_2_EQ_PRESETS,
    EQ_PRESETS,
    GESTURE_ACTIONS,
    GESTURE_TYPES,
    LISTENING_MODES,
    format_ear_tip,
    merge_gestures,
)
from eara.session import Device
from eara.platforms import default_services
from eara.ui_style import GEOMETRY

_FONT_FILES = (
    "DotGothic16-Regular.ttf",
    "Inter-Regular.ttf",
)
_BATTERY_REFRESH_SECONDS = 30


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


def _asset_path(name: str) -> Path | None:
    """Find a UI asset in a source checkout or an installed package."""
    for path in (
        Path(__file__).resolve().parents[1] / "packaging" / name,
        Path.home() / ".local/share/eara/packaging" / name,
        Path(sysconfig.get_path("data")) / "share/eara/packaging" / name,
        Path("/usr/share/eara/packaging") / name,
    ):
        if path.is_file():
            return path
    return None


def _build_css() -> str:
    from eara.ui_style import build_css
    return build_css(_pick_dot_font(), _pick_ui_font(), Adw.StyleManager.get_default().get_dark()) + motion.css(not Gtk.Settings.get_default().get_property("gtk-enable-animations"))


def _line_icon(name: str) -> Gtk.Widget:
    asset = _asset_path(f"ui/icons/eara-{name}-symbolic.svg")
    if asset is not None:
        from eara.ui_widgets import SvgIcon
        return SvgIcon(asset.parent, name)
    from eara.ui_style import draw_icon
    icon = Gtk.DrawingArea(content_width=28, content_height=28)
    icon.set_valign(Gtk.Align.CENTER)
    icon.set_halign(Gtk.Align.CENTER)
    icon.set_draw_func(lambda widget, cr, width, height: draw_icon(widget, cr, width, height, name))
    return icon


def _icon_button(button: Gtk.Button, icon: str, text: str, *, horizontal=False) -> None:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if horizontal else Gtk.Orientation.VERTICAL, spacing=4 if horizontal else 8)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    image = _line_icon(icon)
    if horizontal:
        image.set_pixel_size(20)
    box.append(image)
    label = Gtk.Label(label=text)
    if horizontal:
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_tooltip_text(text)
    box.append(label)
    button.set_child(box)


def _replace_builtin_arrow(dropdown: Gtk.DropDown) -> None:
    """Swap the GTK builtin triangle for the reference's thin chevron."""
    button = dropdown.get_first_child()
    box = button.get_first_child() if button else None
    while box:
        if isinstance(box, Gtk.Box):
            child = box.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                if type(child).__name__ == "GtkBuiltinIcon":
                    child.set_visible(False)
                child = nxt
            box.append(_line_icon("chevron"))
            return
        box = box.get_next_sibling()


def _dotted_cross() -> Gtk.DrawingArea:
    area = Gtk.DrawingArea(content_width=18, content_height=72)
    area.set_valign(Gtk.Align.CENTER)
    area.set_halign(Gtk.Align.CENTER)

    def paint(_widget, cr, width, height):
        color = _widget.get_style_context().get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, 0.45)
        gap = 7.0
        y = 8.0
        while y < height - 4:
            cr.arc(width / 2, y, 1.1, 0, 2 * math.pi)
            cr.fill()
            y += gap
        x = 4.0
        mid = height / 2
        while x < width - 3:
            if abs(x - width / 2) > 3:
                cr.arc(x, mid, 1.1, 0, 2 * math.pi)
                cr.fill()
            x += gap

    area.set_draw_func(paint)
    return area


def _ui_text(label: Gtk.Label) -> Gtk.Label:
    label.add_css_class("eara-ui-text")
    return label


def _badge_label(text: str) -> Gtk.Label:
    label = _ui_text(Gtk.Label(label=text))
    label.add_css_class("eara-status-badge")
    return label


def _button_with_icon(button: Gtk.Button, icon_name: str, text: str = "") -> Gtk.Label:
    content = Gtk.Box(spacing=12)
    content.set_halign(Gtk.Align.CENTER)
    icon = _line_icon(icon_name) if icon_name in ("reset", "save", "info", "refresh", "diagnostics", "find") else Gtk.Image.new_from_icon_name(icon_name)
    if icon_name in ("reset", "save", "info") and hasattr(icon, "set_pixel_size"):
        icon.set_pixel_size(20)
    icon.add_css_class("eara-button-icon")
    label = _ui_text(Gtk.Label(label=text))
    content.append(icon)
    content.append(label)
    button.set_child(content)
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
    provider = getattr(_load_css, "provider", None)
    if provider is None:
        provider = Gtk.CssProvider()
        _load_css.provider = provider
    try:
        provider.load_from_data(css.encode("utf-8"))
    except TypeError:
        # Older PyGObject bindings still expose GTK's explicit length argument.
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
    switch = MotionSwitch()
    switch.add_css_class("eara-switch")
    switch.set_valign(Gtk.Align.CENTER)
    row.append(label)
    row.append(switch)
    return row, switch, label


def _slider_row(title: str, low: int, high: int) -> tuple[Gtk.Box, Gtk.Scale, Gtk.Label]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("eara-toggle-row")
    label = _ui_text(Gtk.Label(label=title, xalign=0))
    label.add_css_class("eara-toggle-label")
    scale = motion_scale(Gtk.Orientation.HORIZONTAL, low, high, 1)
    scale.set_digits(0)
    scale.set_round_digits(0)
    scale.set_draw_value(True)
    scale.set_value_pos(Gtk.PositionType.RIGHT)
    scale.set_hexpand(True)
    for mark in range(low, high + 1):
        scale.add_mark(mark, Gtk.PositionType.BOTTOM, None)
    row.append(label)
    row.append(scale)
    return row, scale, label


class EarAWindow(Adw.ApplicationWindow):
    @property
    def _last(self):
        """Workers edit a private snapshot; only completion commits it to GTK."""
        context = getattr(self, "_operation_context", None)
        if context is not None and hasattr(context, "status"):
            return context.status
        return getattr(self, "_committed_status", {})

    @_last.setter
    def _last(self, status):
        context = getattr(self, "_operation_context", None)
        if context is not None and hasattr(context, "status"):
            context.status = status
        else:
            self._committed_status = status

    def __init__(self, app: Adw.Application, *, services=None) -> None:
        super().__init__(application=app)
        self._services = default_services() if services is None else services
        self.add_css_class("eara-window")
        self.set_default_size(1200, 720)
        self.set_resizable(False)
        self.set_size_request(1200, 720)
        self.device: Device | None = None
        self._busy = False
        self._last: dict = {}
        self._ignore_toggle = False
        self._ignore_listening = False
        self._eq_local = False
        self._eq_dirty = False
        self._eq_syncing = False
        self._codec_keys: list[str] = ["sbc"]
        self._listening_keys: list[str] = list(LISTENING_MODES.keys())
        self.toast = Adw.ToastOverlay()
        load_lang()
        _ensure_fonts()
        _load_css()
        try:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)
        except Exception:
            pass

        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: _load_css())

        Gtk.Settings.get_default().connect("notify::gtk-enable-animations", lambda *_: _load_css())

        self._header_active = "connect"
        self._shutting_down = False
        self._battery_refreshing = False
        self.connect("notify::is-active", self._on_active_changed)
        self.connect("close-request", self._on_close_request)
        self._update_focus_class()

        self.header = Adw.HeaderBar()
        self.header.set_title_widget(Gtk.Box())
        self.header.set_decoration_layout(":minimize,close")
        self.btn_connect = MotionButton()
        self.btn_connect.add_css_class("eara-header-btn")
        self.btn_connect.add_css_class("eara-header-connect")
        self.btn_connect.add_css_class("eara-header-active")
        self.btn_connect.connect("clicked", self._on_connect_clicked)
        self.btn_reset = MotionButton()
        self.btn_reset.add_css_class("eara-header-btn")
        self.btn_reset.add_css_class("eara-header-reset")
        self.btn_reset.connect("clicked", self._on_reset_clicked)
        self.btn_refresh = MotionButton(child=_line_icon("refresh"))
        self.btn_refresh.add_css_class("flat")
        self.btn_refresh.set_valign(Gtk.Align.CENTER)
        self.btn_refresh.connect("clicked", lambda *_: self._run(self._do_refresh))
        self.btn_about = MotionButton(child=_line_icon("help"))
        self.btn_about.add_css_class("flat")
        self.btn_about.connect("clicked", lambda *_: self._about())
        self.btn_more = Gtk.MenuButton.new()
        self.btn_more.set_icon_name("view-more-symbolic")
        self.btn_more.add_css_class("flat")
        self.btn_more.set_valign(Gtk.Align.CENTER)
        more_popover = Gtk.Popover()
        more_popover.add_css_class("eara-menu")
        more_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        more_box.set_size_request(320, -1)
        for edge in ("top", "bottom", "start", "end"):
            getattr(more_box, "set_margin_" + edge)(12)
        self.menu_settings_title = Gtk.Label(label=t("menu_settings"), xalign=0)
        self.menu_settings_title.add_css_class("eara-menu-heading")
        more_box.append(self.menu_settings_title)
        self.menu_settings = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        more_box.append(self.menu_settings)
        more_box.append(Gtk.Separator())
        self.menu_device_title = Gtk.Label(label=t("tab_device"), xalign=0)
        self.menu_device_title.add_css_class("eara-menu-heading")
        more_box.append(self.menu_device_title)
        self.menu_device = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        more_box.append(self.menu_device)
        more_box.append(Gtk.Separator())
        more_about = MotionButton(label=t("about"))
        more_about.add_css_class("flat")
        more_about.connect("clicked", lambda *_: self._about())
        more_box.append(more_about)
        more_popover.set_child(more_box)
        self.btn_more.set_popover(more_popover)
        self.btn_about.set_valign(Gtk.Align.CENTER)
        self.more_about = more_about

        self.header_brand = Gtk.Label(label="EarA")
        self.header_brand.add_css_class("eara-header-title")
        from eara.ui_widgets import brand_mark
        self.header.pack_start(brand_mark(_asset_path("ui/reference-dashboard.png"), _asset_path("ui/reference-recovery.png")))
        self.header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.header_status = Gtk.Box(spacing=8)
        self.header_status.add_css_class("eara-header-device")
        self.header_status_dot = Gtk.Box()
        self.header_status_dot.set_valign(Gtk.Align.CENTER)
        self.header_status_dot.add_css_class("eara-status-dot")
        self.header_status_dot.add_css_class("eara-dot-off")
        self.header_device_label = _ui_text(Gtk.Label(label=t("status_offline")))
        self.header_status.append(self.header_status_dot)
        self.header_status.append(self.header_device_label)
        self.header_status_arrow = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        self.header_status.append(self.header_status_arrow)
        self.header_selector = MotionButton(child=self.header_status)
        self.header_selector.add_css_class("eara-header-selector")
        self.header_selector.set_valign(Gtk.Align.CENTER)
        self.header_selector.connect("clicked", lambda *_: self._open_details())
        self.header.pack_start(self.header_selector)
        self.header.pack_end(self.btn_more)
        self.header.pack_end(self.btn_refresh)
        self.header.pack_end(self.btn_about)

        self.stack = MotionStack()
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        self.stack.add_css_class("eara-stack")
        self._tab_keys = ("device", "sound", "gestures", "tools")
        self._tab_buttons: dict[str, Gtk.Button] = {}
        self._tab_labels: dict[str, Gtk.Label] = {}
        self._tab_revealers: dict[str, Gtk.Revealer] = {}
        self._tab_icons = {
            "device": "view-grid-symbolic",
            "sound": "audio-volume-high-symbolic",
            "gestures": "input-touchpad-symbolic",
            "tools": "preferences-system-symbolic",
        }

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

        self.buttons = SelectionBox(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.buttons.add_css_class("eara-buttons")
        self.buttons.set_size_request(GEOMETRY["rail"], -1)
        self.buttons.set_hexpand(False)
        self._nav_icons = {}
        for key in self._tab_keys:
            btn = MotionButton()
            btn.add_css_class("eara-tab")
            btn.connect("clicked", lambda *_, k=key: self._show_tab(k))
            content = Gtk.Box(spacing=12)
            content.add_css_class("eara-tab-content")
            icon = _line_icon(key)
            self._nav_icons[key] = icon
            icon.add_css_class("eara-tab-icon")
            label = _ui_text(Gtk.Label(xalign=0, hexpand=True))
            label.add_css_class("eara-tab-label")
            content.append(icon)
            content.append(label)
            btn.set_child(content)
            self._tab_buttons[key] = btn
            self._tab_labels[key] = label
            revealer = Gtk.Revealer()
            revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            revealer.set_transition_duration(160)
            revealer.set_reveal_child(True)
            revealer.set_child(btn)
            self._tab_revealers[key] = revealer
            self.buttons.append(revealer)
        spacer = Gtk.Box(vexpand=True)
        self.buttons.append(spacer)
        rail_status = _ui_text(Gtk.Label(label="●  Bluetooth · RFCOMM", xalign=0, wrap=True))
        rail_status.add_css_class("eara-rail-status")
        # Service state is shown once in the bottom status bar.
        self._show_tab("device")
        self._set_navigation_connected(False)

        self.toast.set_child(self.stack)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.add_css_class("eara-body")
        body.set_vexpand(True)
        body.append(self.buttons)
        body.append(self.toast)
        self.toast.set_hexpand(True)
        self.toast.set_vexpand(True)

        system_strip = Gtk.Box(spacing=14)
        self.system_strip = system_strip
        system_strip.add_css_class("eara-system-strip")
        settings = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        settings.add_css_class("flat")
        settings.connect("clicked", lambda *_: self.btn_more.popup())
        system_strip.append(settings)
        system_strip.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self._service_labels = {}
        self._service_dots: dict[str, Gtk.Box] = {}
        for key, label in (
            ("bluetooth", "Bluetooth"),
            ("rfcomm", "RFCOMM"),
            ("pipewire", "PipeWire"),
        ):
            item = Gtk.Box(spacing=6)
            item.add_css_class("eara-system-item")
            dot = Gtk.Box()
            dot.set_valign(Gtk.Align.CENTER)
            dot.add_css_class("eara-system-dot")
            dot.add_css_class("eara-system-dot-off")
            dot.set_visible(False)
            item.append(dot)
            service_label = Gtk.Label(label=label)
            self._service_labels[key] = service_label
            item.append(service_label)
            system_strip.append(item)
            if key != "pipewire":
                system_strip.append(Gtk.Label(label="•"))
            self._service_dots[key] = dot

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.header)
        outer.append(body)
        outer.append(system_strip)
        self.set_content(outer)
        self._apply_lang()
        self._health = {}
        self._update_help_health()
        GLib.idle_add(self._probe_services)
        GLib.timeout_add_seconds(15, self._poll_services)
        GLib.idle_add(self._bootstrap)
        GLib.timeout_add_seconds(_BATTERY_REFRESH_SECONDS, self._refresh_battery)

    def _page_device(self) -> Gtk.Widget:
        from eara.ui_widgets import dotted_label, reference_art
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("eara-content")
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        toolbar = Gtk.Box(spacing=8)
        self.lbl_language = _ui_text(Gtk.Label(xalign=0, hexpand=True))
        self.btn_en = MotionButton(label="English")
        self.btn_uk = MotionButton(label="Українська")
        self.btn_en.add_css_class("eara-chip")
        self.btn_uk.add_css_class("eara-chip")
        self.btn_en.connect("clicked", lambda *_: self._set_lang("en"))
        self.btn_uk.connect("clicked", lambda *_: self._set_lang("uk"))
        self._update_lang_buttons()
        toolbar.append(self.lbl_language)
        toolbar.append(self.btn_en)
        toolbar.append(self.btn_uk)
        self.menu_settings.append(toolbar)

        self.device_state_stack = Gtk.Stack()
        self.device_state_stack.set_vexpand(True)
        self.device_state_stack.set_hhomogeneous(False)
        self.device_state_stack.set_vhomogeneous(False)
        self.device_state_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.device_state_stack.set_transition_duration(180)

        dashboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        dashboard.add_css_class("eara-dashboard")
        dashboard.set_vexpand(False)
        dashboard_top = Gtk.Grid(column_spacing=14, column_homogeneous=True)
        dashboard_bottom = Gtk.Grid(column_spacing=14, column_homogeneous=True)
        dashboard.append(dashboard_top)
        dashboard.append(dashboard_bottom)

        self._ui_regions = {}
        self.status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.status_card.add_css_class("eara-status-card")
        self.status_card.set_hexpand(True)
        self.status_card.set_vexpand(False)

        head = Gtk.Box(spacing=10)
        head.add_css_class("eara-status-head")
        head.set_vexpand(True)
        hero_asset = _asset_path("ui/reference-dashboard.png")
        if hero_asset is not None:
            device_art = reference_art(hero_asset, (335, 222, 359, 314))
            device_art.add_css_class("eara-device-art")
            device_art.set_size_request(180, 280)
            device_art.set_hexpand(True)
            head.append(device_art)
        self.status_dot = Gtk.Box()
        self.status_dot.add_css_class("eara-status-dot")
        self.status_dot.add_css_class("eara-dot-off")
        title_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_col.set_hexpand(False)
        self.status_name = _ui_text(Gtk.Label(xalign=0, wrap=True))
        self.status_name.add_css_class("eara-status-name")
        badges = Gtk.Box(spacing=6)
        badges.add_css_class("eara-status-badges")
        self.badge_bt = _badge_label("BT")
        self.badge_proto = _badge_label("RFCOMM")
        badges.append(self.badge_bt)
        badges.append(self.badge_proto)
        title_col.append(dotted_label(self.status_name, 30))
        badges.set_orientation(Gtk.Orientation.VERTICAL)
        badges.set_halign(Gtk.Align.START)
        title_col.append(badges)
        self.status_dot.set_visible(False)
        head.append(self.status_dot)
        head.append(title_col)
        self.status_card.append(head)

        self.status_meta = _ui_text(Gtk.Label(wrap=True, xalign=0))
        self.status_meta.add_css_class("eara-status-meta")
        title_col.append(self.status_meta)

        batt_row = Gtk.Box(spacing=8, homogeneous=True)
        batt_row.add_css_class("eara-status-batteries")
        self._batt_cells: dict[str, dict[str, Gtk.Widget]] = {}
        for key, short in (("left", "L"), ("right", "R"), ("case", "Case")):
            batt_row.append(self._battery_cell(key, short))
        title_col.append(Gtk.Separator())
        title_col.append(batt_row)

        modes = Gtk.Box(spacing=8)
        modes.add_css_class("eara-status-modes")
        self.chip_anc = _ui_text(Gtk.Label())
        self.chip_anc.add_css_class("eara-mode-chip")
        self.chip_eq = _ui_text(Gtk.Label())
        self.chip_eq.add_css_class("eara-mode-chip")
        modes.append(self.chip_anc)
        modes.append(self.chip_eq)
        # Detailed mode/firmware metadata belongs in the overflow details.

        dashboard_top.attach(self.status_card, 0, 0, 3, 1)

        noise_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        noise_card.add_css_class("eara-card")
        noise_card.add_css_class("eara-device-noise")
        noise_card.set_hexpand(True)
        noise_card.set_vexpand(False)
        self.lbl_dashboard_noise = Gtk.Label(label=t("noise"), xalign=0)
        self.lbl_dashboard_noise.add_css_class("eara-dashboard-title")
        noise_card.append(self.lbl_dashboard_noise)
        noise_modes = SelectionBox(spacing=0, homogeneous=True)
        noise_modes.add_css_class("eara-segmented")
        self.dashboard_anc_buttons: dict[str, Gtk.Button] = {}
        for mode in ("off", "transparency", "high"):
            button = MotionButton(label=t(mode))
            button.add_css_class("eara-segment")
            button.connect("clicked", lambda *_, m=mode: self._run(lambda: self._do_anc(m)))
            self.dashboard_anc_buttons[mode] = button
            noise_modes.append(button)
        noise_card.append(noise_modes)
        strength = SelectionBox(spacing=0, homogeneous=True)
        strength.add_css_class("eara-segmented")
        strength.add_css_class("eara-strength")
        self.dashboard_strength_buttons: dict[str, Gtk.Button] = {}
        for mode in ("low", "mid", "high"):
            button = MotionButton(label=t(mode).replace("ANC ", ""))
            button.add_css_class("eara-segment")
            button.connect("clicked", lambda *_, m=mode: self._run(lambda: self._do_anc(m)))
            self.dashboard_strength_buttons[mode] = button
            strength.append(button)
        noise_card.append(Gtk.Separator())
        noise_card.append(strength)
        noise_card.set_hexpand(False)
        noise_card.set_size_request(340, -1)
        self._ui_regions["device_noise"] = noise_card
        dashboard_top.attach(noise_card, 3, 0, 2, 1)

        audio_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        audio_card.add_css_class("eara-card")
        audio_card.set_hexpand(True)
        self.lbl_audio_profile = Gtk.Label(label=t("audio_profile"), xalign=0)
        self.lbl_audio_profile.add_css_class("eara-dashboard-title")
        audio_card.append(self.lbl_audio_profile)
        self.audio_box = SelectionBox(spacing=0, homogeneous=True)
        self.audio_box.add_css_class("eara-segmented")
        self.audio_box.set_margin_top(14)
        self.btn_music = MotionButton()
        self.btn_calls = MotionButton()
        self.btn_disconnect = MotionButton()
        self.btn_music.add_css_class("eara-segment")
        self.btn_calls.add_css_class("eara-segment")
        self.btn_disconnect.add_css_class("eara-chip")
        self.btn_disconnect.add_css_class("eara-chip-disconnect")
        self.btn_music.connect("clicked", lambda *_: self._run(lambda: self._do_audio(False)))
        self.btn_calls.connect("clicked", lambda *_: self._run(lambda: self._do_audio(True)))
        self.btn_disconnect.connect("clicked", lambda *_: self._run(self._do_disconnect))
        self.audio_box.append(self.btn_music)
        self.audio_box.append(self.btn_calls)
        audio_card.append(self.audio_box)
        self.menu_device.append(self.btn_disconnect)
        self._ui_regions["audio_profile"] = audio_card
        dashboard_bottom.attach(audio_card, 0, 0, 6, 1)

        quick_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        quick_card.add_css_class("eara-card")
        quick_card.set_hexpand(True)
        self.lbl_dashboard_quick = Gtk.Label(label=t("quick"), xalign=0)
        self.lbl_dashboard_quick.add_css_class("eara-dashboard-title")
        quick_card.append(self.lbl_dashboard_quick)
        self.dashboard_switches: dict[str, Gtk.Switch] = {}
        self.dashboard_toggle_labels = {}
        for key, label_key in (("ied", "in_ear"), ("lat", "latency"), ("bass", "bass")):
            row, switch, _label = _toggle_row(t(label_key))
            switch.connect("notify::active", lambda sw, _pspec, k=key: self._on_dashboard_toggle(k, sw))
            row.prepend(_line_icon(key))
            self.dashboard_switches[key] = switch
            self.dashboard_toggle_labels[label_key] = _label
            quick_card.append(row)
        self._ui_regions["quick_controls"] = quick_card
        quick_card.add_css_class("eara-quick-card")
        dashboard_bottom.attach(quick_card, 6, 0, 7, 1)

        connected = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        connected.set_vexpand(False)
        connected.append(dashboard)

        self.advanced = MotionButton(label=t("device_details"))
        self.advanced.connect("clicked", lambda *_: self._open_details())
        advanced = self.advanced
        advanced.add_css_class("eara-advanced")
        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        pick_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_pick = _ui_text(Gtk.Label(xalign=0))
        self.lbl_pick.set_wrap(True)
        self.device_drop = Gtk.DropDown.new_from_strings(["—"])
        self.device_drop.connect("notify::selected-item", self._on_device_changed)
        pick_row.append(self.lbl_pick)
        pick_row.append(self.device_drop)
        advanced_box.append(pick_row)

        exit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        exit_card.add_css_class("eara-card")
        self.row_power_off, self.power_off_switch, self.lbl_power_off = _toggle_row(t("power_off_exit"))
        self.power_off_switch.set_active(power_off_on_exit())
        self.power_off_switch.connect("notify::active", self._on_power_off_exit_changed)
        exit_card.append(self.row_power_off)
        self.lbl_power_off.set_wrap(True)
        self.lbl_power_off.set_max_width_chars(24)
        self.lbl_power_off_hint = Gtk.Label(wrap=True, xalign=0, max_width_chars=36)
        self.lbl_power_off_hint.add_css_class("dim-label")
        self.lbl_power_off_hint.set_text(t("power_off_exit_hint"))
        exit_card.append(self.lbl_power_off_hint)
        exit_card.remove_css_class("eara-card")
        self.menu_settings.append(exit_card)

        codec_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        codec_card.add_css_class("eara-card")
        self.lbl_codec = Gtk.Label(xalign=0, wrap=True)
        self.lbl_codec.add_css_class("eara-card-title")
        codec_row = Gtk.Box(spacing=8)
        self.codec_drop = Gtk.DropDown.new_from_strings(["sbc"])
        self.codec_drop.set_hexpand(True)
        self.btn_codec = MotionButton()
        self.btn_codec.add_css_class("eara-chip")
        self.btn_codec.connect("clicked", lambda *_: self._apply_codec())
        codec_row.append(self.codec_drop)
        codec_row.append(self.btn_codec)
        self.lbl_codec_hint = Gtk.Label(wrap=True, xalign=0)
        self.lbl_codec_hint.add_css_class("dim-label")
        codec_card.append(self.lbl_codec)
        codec_card.append(codec_row)
        codec_card.append(self.lbl_codec_hint)
        advanced_box.append(codec_card)
        self.details_box = advanced_box
        self.menu_device.prepend(advanced)

        self.lbl_legal_dev = Gtk.Label(wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.lbl_legal_dev.add_css_class("dim-label")
        advanced_box.append(self.lbl_legal_dev)

        recovery = Gtk.Grid(column_spacing=12, row_spacing=14, column_homogeneous=True)
        recovery.set_margin_top(8)
        recovery.add_css_class("eara-recovery")
        recovery_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        recovery_main.add_css_class("eara-recovery-main")
        recovery_main.set_hexpand(True)
        recovery_main.set_vexpand(False)
        self.recovery_eyebrow = Gtk.Label(label=t("tab_device").upper(), xalign=0)
        self.recovery_eyebrow.add_css_class("eara-card-title")
        self.recovery_title = Gtk.Label(label=t("connect_title"), xalign=0, wrap=True)
        self.recovery_title.add_css_class("eara-recovery-title")
        self.recovery_hint = Gtk.Label(
            label=t("connect_hint"),
            xalign=0,
            wrap=True,
        )
        self.recovery_hint.add_css_class("dim-label")
        for intro_label in (self.recovery_eyebrow, self.recovery_title, self.recovery_hint):
            intro_label.set_margin_start(16)
        recovery_main.append(self.recovery_eyebrow)
        recovery_main.append(self.recovery_title)
        recovery_main.append(self.recovery_hint)
        recovery_device = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        recovery_device.add_css_class("eara-recovery-device")
        recovery_device.set_size_request(-1, 177)
        recovery_device.set_margin_end(26)
        self.found_label = Gtk.Label(label=t("found_devices"), xalign=0)
        self.found_label.add_css_class("eara-card-title")
        recovery_device.append(self.found_label)
        device_picker = Gtk.Box(spacing=14)
        device_picker.add_css_class("eara-discovery-row")
        recovery_device_asset = _asset_path("ui/reference-recovery.png")
        if recovery_device_asset is not None:
            recovery_device_art = reference_art(recovery_device_asset, (349, 440, 129, 85))
            recovery_device_art.add_css_class("eara-recovery-device-art")
            recovery_device_art.set_size_request(92, 64)
            device_picker.append(recovery_device_art)
        self.recovery_device_drop = Gtk.DropDown.new_from_strings(["—"])
        self.recovery_device_drop.set_hexpand(True)
        self.recovery_device_drop.connect("notify::selected-item", self._on_recovery_device_changed)
        picker_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        self.recovery_device_name = Gtk.Label(xalign=0, label="—")
        self.recovery_device_name.add_css_class("eara-discovery-name")
        self.recovery_paired = Gtk.Label(label=t("paired"), halign=Gtk.Align.START)
        self.recovery_paired.add_css_class("eara-paired")
        picker_text.append(self.recovery_device_name)
        picker_text.append(self.recovery_paired)
        self.recovery_picker = MotionButton(child=picker_text, hexpand=True)
        self.recovery_picker.connect("clicked", lambda *_: self._open_details())
        self.recovery_picker.add_css_class("eara-device-picker")
        device_picker.append(self.recovery_picker)
        signal = _line_icon("signal")
        signal.set_tooltip_text(t("signal_unavailable"))
        device_picker.append(signal)
        recovery_device.append(device_picker)
        self.found_options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.found_options.set_valign(Gtk.Align.START)
        recovery_device.append(self.found_options)
        connect_row = Gtk.Box(spacing=8)
        device_picker.append(self.btn_connect)
        self.menu_device.append(self.btn_reset)
        self.btn_disconnect.set_label(t("disconnect"))
        self.btn_reset.set_label(t("reset"))
        for button in (self.advanced, self.btn_disconnect, self.btn_reset, self.more_about):
            button.add_css_class("eara-menu-action")
            button.get_child().set_xalign(0)
        self.btn_disconnect.connect("clicked", lambda *_: self.btn_more.popdown())
        self.btn_reset.connect("clicked", lambda *_: self.btn_more.popdown())
        recovery_main.append(recovery_device)
        self.steps_title = Gtk.Label(label=t("recovery_steps"), xalign=0)
        self.steps_title.add_css_class("eara-card-title")
        self.steps_title.set_margin_start(20)
        recovery_main.append(self.steps_title)
        steps = Gtk.Box(spacing=6)
        self.recovery_step_labels: list[Gtk.Label] = []
        for icon, rectangle, text in (
            ("①", (362, 635, 165, 127), t("recovery_case")),
            ("②", (630, 630, 177, 138), t("recovery_button")),
            ("③", (930, 632, 118, 127), t("recovery_refresh")),
        ):
            step = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            step.add_css_class("eara-recovery-step")
            step.set_hexpand(True)
            step_asset = _asset_path("ui/reference-recovery.png")
            if step_asset is not None:
                step_art = reference_art(step_asset, rectangle, max_scale=0.9)
                step_art.add_css_class("eara-recovery-step-art")
                step_art.set_size_request(112, 100)
                step.append(step_art)
            else:
                icon_label = Gtk.Label(label=icon)
                icon_label.add_css_class("eara-recovery-icon")
                step.append(icon_label)
            step_label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
            if icon == "③":
                step_label.add_css_class("eara-recovery-step-strong")
            self.recovery_step_labels.append(step_label)
            step_label.set_valign(Gtk.Align.END)
            step.append(step_label)
            if steps.get_first_child() is not None:
                steps.append(_dotted_cross())
            steps.append(step)
        recovery_main.append(steps)
        self.btn_recovery_refresh = MotionButton()
        self.btn_recovery_refresh.set_halign(Gtk.Align.CENTER)
        self.btn_recovery_refresh.set_size_request(340, -1)
        self.btn_recovery_refresh.add_css_class("eara-chip")
        self.btn_recovery_refresh_label = _button_with_icon(
            self.btn_recovery_refresh, "refresh", t("refresh_devices")
        )
        self.btn_recovery_refresh.connect("clicked", lambda *_: self._fill_devices())
        recovery_main.append(self.btn_recovery_refresh)
        recovery.attach(recovery_main, 0, 0, 2, 1)

        help_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        help_card.add_css_class("eara-card")
        help_card.add_css_class("eara-connection-help")
        help_card.set_valign(Gtk.Align.START)
        help_card.set_size_request(300, 396)
        self.help_title = Gtk.Label(label=t("connection_help"), xalign=0, wrap=True)
        self.help_title.add_css_class("eara-dashboard-title")
        help_card.append(self.help_title)
        self.help_status_labels: list[Gtk.Label] = []
        self.help_status_dots = []
        for kind, text in (("ok", t("bt_service_ready")), ("ok", t("audio_service_ready")), ("wait", t("controls_waiting"))):
            row = Gtk.Box(spacing=9)
            dot = Gtk.Box()
            dot.set_valign(Gtk.Align.CENTER)
            dot.add_css_class("eara-help-dot")
            dot.add_css_class(f"eara-help-dot-{kind}")
            row.append(dot)
            status_label = Gtk.Label(label=text, xalign=0, hexpand=True)
            status_label.set_wrap(True)
            self.help_status_labels.append(status_label)
            self.help_status_dots.append(dot)
            row.append(status_label)
            help_card.append(row)
        self.btn_diagnostics = MotionButton()
        self.btn_diagnostics.add_css_class("eara-chip")
        self.btn_diagnostics_label = _button_with_icon(
            self.btn_diagnostics, "diagnostics", t("run_diagnostics")
        )
        self.btn_diagnostics_label.set_wrap(True)
        self.btn_diagnostics_label.set_max_width_chars(22)
        self.btn_diagnostics.connect("clicked", lambda *_: self._probe_services())
        help_card.append(Gtk.Separator())
        self.recovery_help_expander = Gtk.Revealer()
        self.recovery_help_expander.set_child(Gtk.Label(label=t("connect_hint"), wrap=True, xalign=0))
        self.recovery_help_button = MotionButton()
        self.recovery_help_button.add_css_class("eara-help-toggle")
        help_row = Gtk.Box(spacing=8)
        self.recovery_help_label = Gtk.Label(label=t("still_not_connecting"), xalign=0, hexpand=True, wrap=True)
        help_row.append(self.recovery_help_label)
        help_row.append(_line_icon("chevron"))
        self.recovery_help_button.set_child(help_row)
        self.recovery_help_button.connect("clicked", lambda *_: self._show_connection_help())
        help_card.append(self.recovery_help_button)
        help_card.append(self.recovery_help_expander)
        help_card.append(self.btn_diagnostics)
        recovery_side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        recovery_side.append(help_card)
        self.partial_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.partial_card.add_css_class("eara-card")
        self.partial_card.add_css_class("eara-partial-card")
        self.partial_card.set_size_request(300, 167)
        self.partial_label = Gtk.Label(label=t("partial_help"), wrap=True, xalign=0)
        self.partial_label.set_hexpand(True)
        warning = Gtk.Box(spacing=12)
        warning.append(_line_icon("warning"))
        warning.append(self.partial_label)
        self.partial_card.append(warning)
        self.btn_retry = MotionButton()
        self.btn_retry.set_child(Gtk.Label(label=t("retry_controls"), wrap=True, justify=Gtk.Justification.CENTER))
        self.btn_retry.connect("clicked", self._on_connect_clicked)
        self.partial_card.append(self.btn_retry)
        self.partial_card.set_visible(False)
        recovery_side.append(self.partial_card)
        recovery.attach(recovery_side, 2, 0, 1, 1)
        self._ui_regions.update(found_devices=recovery_device, recovery_steps=steps,
                                connection_help=help_card, partial_warning=self.partial_card)

        self.device_state_stack.add_named(connected, "connected")
        self.device_state_stack.add_named(recovery, "recovery")
        box.append(self.device_state_stack)
        self._set_status_message(t("looking"), offline=True)
        scroll = Gtk.ScrolledWindow(child=box)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        return scroll

    def _on_dashboard_toggle(self, which: str, switch: Gtk.Switch) -> None:
        if self._busy or self._ignore_toggle or not self.device:
            return
        target = {
            "bass": self.bass_switch,
            "ied": self.ied_switch,
            "lat": self.lat_switch,
        }.get(which)
        if target is None:
            return
        self._ignore_toggle = True
        try:
            target.set_active(switch.get_active())
        finally:
            self._ignore_toggle = False
        self._on_toggle(which)

    def _battery_cell(self, key: str, short: str) -> Gtk.Box:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        cell.add_css_class("eara-batt-cell")
        cell.set_hexpand(True)
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lbl_side = _ui_text(Gtk.Label(label=short, xalign=0.5))
        lbl_side.add_css_class("eara-batt-side")
        lbl_pct = _ui_text(Gtk.Label(label="—", xalign=0.5))
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
        battery_shell = Gtk.Box(spacing=0)
        battery_shell.set_halign(Gtk.Align.CENTER)
        battery_shell.append(bar)
        terminal = Gtk.Box()
        terminal.add_css_class("eara-battery-terminal")
        terminal.set_valign(Gtk.Align.CENTER)
        battery_shell.append(terminal)
        cell.append(battery_shell)
        lbl_sub.set_visible(False)
        # Detailed availability/charging information is exposed on hover.
        lbl_sub.connect("notify::label", lambda label, *_: cell.set_tooltip_text(label.get_text()))
        cell.append(lbl_sub)
        self._batt_cells[key] = {"pct": lbl_pct, "bar": bar, "sub": lbl_sub, "cell": cell}
        return cell

    def _set_badge(self, label: Gtk.Label, text: str, kind: str) -> None:
        if text.startswith("●  "):
            label.set_markup('<span foreground="#27cc4c">●</span>  '+GLib.markup_escape_text(text[3:]))
        else:
            label.set_text(text)
        label.remove_css_class("eara-status-badge-ok")
        label.remove_css_class("eara-status-badge-warn")
        label.remove_css_class("eara-status-badge-bad")
        if kind:
            label.add_css_class(f"eara-status-badge-{kind}")

    def _poll_services(self) -> bool:
        if self._shutting_down:
            return False
        if self.stack.get_visible_child_name() == "device":
            self._probe_services()
        return True

    def _probe_services(self) -> bool:
        from eara.health import inspect_services
        if getattr(self, "_health_checking", False):
            return False
        self._health_checking = True
        self.btn_diagnostics.set_sensitive(False)
        def worker():
            try:
                result = inspect_services(self._services)
            except Exception:
                traceback.print_exc()
                result = {"bluetooth": None, "audio": None}
            def done():
                self._health_checking = False
                if self._shutting_down:
                    return False
                self._health = result
                self.btn_diagnostics.set_sensitive(True)
                self._update_help_health()
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()
        return False

    def _update_help_health(self) -> None:
        health = getattr(self, "_health", {})
        states = (health.get("bluetooth"), health.get("audio"),
                  bool(self._last.get("protocol")) if self._last.get("bt_connected") else None)
        for label, dot, title, state in zip(self.help_status_labels, self.help_status_dots,
                                          ("service_bluetooth", "service_audio", "service_controls"), states):
            value = "health_ready" if state else "health_unavailable" if state is False else "health_waiting"
            label.set_text(f"{t(title)} — {t(value)}")
            dot.remove_css_class("eara-help-dot-ok")
            dot.remove_css_class("eara-help-dot-wait")
            dot.add_css_class("eara-help-dot-ok" if state else "eara-help-dot-wait")

    def _set_service_health(self, key: str, state: str) -> None:
        dots = getattr(self, "_service_dots", {})
        dot = dots.get(key)
        if dot is None:
            return
        for css in ("eara-system-dot-ok", "eara-system-dot-warn", "eara-system-dot-off"):
            dot.remove_css_class(css)
        dot.add_css_class(f"eara-system-dot-{state}")
        label = getattr(self, "_service_labels", {}).get(key)
        if label is not None:
            label.set_tooltip_text(f"{key}: {state}")
            label.update_property([Gtk.AccessibleProperty.DESCRIPTION], [f"{key}: {state}"])

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
        if hasattr(self, "partial_card"):
            self.partial_card.set_visible(False)
        if hasattr(self, "device_state_stack"):
            self.device_state_stack.set_visible_child_name("recovery")
        if hasattr(self, "header_device_label"):
            self.header_device_label.set_text(t("status_offline") if offline else message)
            self.header_status_arrow.set_visible(not offline)
            for css in ("eara-dot-ok", "eara-dot-warn", "eara-dot-off"):
                self.header_status_dot.remove_css_class(css)
            self.header_status_dot.add_css_class("eara-dot-off" if offline else "eara-dot-warn")
        self._set_service_health("bluetooth", "off" if offline else "warn")
        self._set_service_health("rfcomm", "off")
        self._set_service_health("pipewire", "off")

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
            motion.battery(cell, level)
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
            if level <= 35:
                bar.add_css_class("eara-batt-low")
            return
        if "motion" in cell:
            cell["motion"].finish()
            del cell["motion"]
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
        outer.add_css_class("eara-sound-page")
        outer.set_margin_top(36)
        outer.set_margin_bottom(16)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        sound_title = Gtk.Label(label=t("tab_sound"), xalign=0)
        self.sound_title = sound_title
        sound_title.add_css_class("eara-page-title")
        sound_title.set_margin_start(24)
        sound_subtitle = Gtk.Label(label=t("tune_earbuds"), xalign=0)
        self.sound_subtitle = sound_subtitle
        sound_subtitle.add_css_class("dim-label")
        sound_subtitle.set_margin_start(24)
        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        intro.set_margin_bottom(8)
        sound_subtitle.add_css_class("eara-sound-subtitle")
        intro.append(sound_title)
        intro.append(sound_subtitle)
        outer.append(intro)

        cards = Gtk.Grid(column_spacing=12, row_spacing=12)
        cards.add_css_class("eara-sound-cards")
        cards.set_size_request(-1, 428)
        cards.set_column_homogeneous(True)

        quick_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        quick_card.add_css_class("eara-card")
        quick_card.add_css_class("eara-sound-card")
        quick_card.add_css_class("eara-listening-card")
        quick_card.set_spacing(0)
        quick_card.set_vexpand(True)
        quick_card.set_hexpand(True)
        self.lbl_quick_title = Gtk.Label(xalign=0)
        self.lbl_quick_title.add_css_class("eara-card-title")
        listening_title_row = Gtk.Box(spacing=14)
        listening_title_row.append(_line_icon("dots"))
        listening_title_row.append(self.lbl_quick_title)
        quick_card.append(listening_title_row)

        self.row_bass, self.bass_switch, self.lbl_bass = _toggle_row(t("bass"))
        self.row_bass_level, self.bass_level, self.lbl_bass_level = _slider_row(t("bass_level"), 1, 5)
        self.bass_level.set_sensitive(False)
        self._bass_level_timer = 0
        self.bass_level.connect("value-changed", self._on_bass_level_changed)
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
        toggles.set_vexpand(True)
        toggles.set_homogeneous(True)
        for row in (self.row_bass, self.row_ied, self.row_lat):
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
        sound_advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sound_advanced_box.add_css_class("eara-card")
        self.lbl_audio_options = Gtk.Label(label=t("audio_options"), xalign=0)
        self.lbl_audio_options.add_css_class("eara-card-title")
        sound_advanced_box.append(self.lbl_audio_options)
        for row in (self.row_bass_level, self.row_adv, self.row_panc, self.listening_box):
            sound_advanced_box.append(row)
        self.details_box.append(sound_advanced_box)
        self.details_box.reorder_child_after(self.lbl_legal_dev, sound_advanced_box)

        self.lbl_noise = _ui_text(Gtk.Label(xalign=0))
        self.lbl_noise.add_css_class("eara-noise-label")
        noise_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        noise_card.add_css_class("eara-card")
        self.lbl_noise.add_css_class("eara-dashboard-title")
        noise_title_row = Gtk.Box(spacing=14)
        noise_title_row.append(_line_icon("dots"))
        noise_title_row.append(self.lbl_noise)
        noise_card.append(noise_title_row)
        self.anc_flow = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        anc_modes = SelectionBox(homogeneous=True)
        anc_modes.add_css_class("eara-segmented")
        anc_modes.add_css_class("eara-compact-segments")
        self.anc_flow.append(anc_modes)
        self.anc_flow.add_css_class("eara-anc-list")
        self.anc_buttons: dict[str, Gtk.Button] = {}
        for mode in ("off", "transparency", "high", "mid", "low", "adaptive"):
            btn = MotionButton()
            btn.add_css_class("eara-chip")
            btn.set_hexpand(True)
            btn.connect("clicked", lambda *_, m=mode: self._run(lambda: self._do_anc(m)))
            btn.add_css_class("eara-segment")
            self.anc_buttons[mode] = btn
            if mode in ("off", "transparency", "high"):
                anc_modes.append(btn)
        self.anc_strength = Gtk.DropDown.new_from_strings([t(key).replace("ANC ", "") for key in ("high", "mid", "low", "adaptive")])
        self.anc_strength.connect("notify::selected", self._on_anc_strength_changed)
        _replace_builtin_arrow(self.anc_strength)
        self.anc_flow.append(self.anc_strength)
        noise_card.append(self.anc_flow)
        eq_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        eq_card.add_css_class("eara-card")
        eq_card.add_css_class("eara-sound-card")
        eq_card.set_vexpand(True)
        eq_card.set_hexpand(True)
        self.lbl_eq_title = Gtk.Label(xalign=0)
        self.lbl_eq_title.add_css_class("eara-card-title")
        eq_title_row = Gtk.Box(spacing=14)
        eq_title_row.append(_line_icon("dots"))
        eq_title_row.append(self.lbl_eq_title)
        eq_card.append(eq_title_row)
        self.lbl_eq = _ui_text(Gtk.Label(xalign=0))
        eq_card.append(self.lbl_eq)
        eq = Gtk.FlowBox(max_children_per_line=5, min_children_per_line=1, homogeneous=True, column_spacing=8, selection_mode=Gtk.SelectionMode.NONE)
        self.eq_flow = eq
        self.eq_buttons: dict[str, Gtk.Button] = {}
        eq_keys = list(dict.fromkeys([*EQ_PRESETS, *CMF_BUDS_2_EQ_PRESETS]))
        for key in eq_keys:
            b = MotionButton()
            b.add_css_class("eara-chip")
            b.connect("clicked", lambda *_, k=key: self._select_eq_preset(k))
            self.eq_buttons[key] = b
            eq.append(b)
        eq_card.append(eq)
        self.lbl_custom = _ui_text(Gtk.Label(xalign=0, wrap=True))
        self.lbl_custom.set_visible(False)
        self.graphic_box = Gtk.Box(spacing=6)
        self.graphic_box.set_homogeneous(True)
        self.graphic_box.add_css_class("eara-panel")
        self.graphic_box.set_margin_top(6)
        self.eq_bands: list[Gtk.Scale] = []
        self.eq_band_values: list[Gtk.Label] = []
        # Approved Z.ai display labels; retain the existing protocol/preset mapping.
        for hz in (60, 120, 250, 500, 1000, 2000, 4000, 8000):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            col.set_hexpand(True)
            value_label = _ui_text(Gtk.Label(label="0 dB"))
            value_label.add_css_class("eara-eq-value")
            lab = _ui_text(Gtk.Label(label=str(hz) if hz < 1000 else f"{hz // 1000}k"))
            lab.add_css_class("eara-eq-frequency")
            scale = motion_scale(Gtk.Orientation.VERTICAL, -6, 6, 0.5)
            scale.set_inverted(True)
            scale.set_value(0)
            scale.set_vexpand(True)
            scale.set_size_request(24, 205)
            scale.set_draw_value(False)
            scale.set_tooltip_text(f"{hz} Hz")
            scale.connect("value-changed", self._on_eq_band_changed, value_label)
            motion.bind_slider(self, scale)
            value_label.set_visible(False)
            scale.set_tooltip_text(f"{hz} Hz · 0 dB")
            col.append(scale)
            col.append(lab)
            self.graphic_box.append(col)
            self.eq_bands.append(scale)
            self.eq_band_values.append(value_label)
        eq_scroll = Gtk.ScrolledWindow()
        eq_scroll.add_css_class("eara-eq-scroll")
        eq_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        eq_scroll.set_propagate_natural_height(True)
        eq_scroll.set_vexpand(False)
        from eara.ui_widgets import equalizer_grid
        eq_scroll.set_child(equalizer_grid(self.graphic_box, self.eq_bands))
        eq_card.append(eq_scroll)
        self._ui_regions.update(eq_graph=self.graphic_box, eq_scroll=eq_scroll,
                                eq_first_scale=self.eq_bands[0], eq_presets=eq)
        eq_actions = Gtk.Box(spacing=8)
        eq_actions.add_css_class("eara-eq-footer")
        self.btn_reset_eq = MotionButton()
        self.btn_reset_eq.add_css_class("eara-chip")
        self.btn_reset_eq_label = _button_with_icon(
            self.btn_reset_eq, "reset", t("reset_eq")
        )
        self.btn_reset_eq.connect("clicked", lambda *_: self._reset_eq())
        eq_actions.append(self.btn_reset_eq)
        self.btn_save_preset = MotionButton()
        self.btn_save_preset.add_css_class("eara-save-preset")
        self.btn_save_preset_label = _button_with_icon(self.btn_save_preset, "save", t("save_preset"))
        self.btn_save_preset.connect("clicked", lambda *_: self._save_eq_preset())
        eq_actions.append(self.btn_save_preset)
        self.btn_load_preset = MotionButton(label=t("load_preset"))
        self.btn_load_preset.connect("clicked", lambda *_: self._load_eq_preset())
        sound_advanced_box.append(self.btn_load_preset)
        eq_actions.add_css_class("eara-card")
        self.lbl_eq_apply_hint = _ui_text(Gtk.Label(xalign=0, wrap=True))
        self.lbl_eq_apply_hint.add_css_class("eara-eq-hint")
        self.lbl_eq_apply_hint.set_hexpand(True)
        self.lbl_eq_apply_hint.set_xalign(1)
        self.lbl_eq_apply_hint.set_wrap(False)
        eq_note = Gtk.Box(spacing=10, hexpand=True, halign=Gtk.Align.END)
        eq_note.append(_line_icon("info"))
        eq_note.append(self.lbl_eq_apply_hint)
        eq_actions.append(eq_note)
        self._ui_regions.update(equalizer=eq_card, listening=quick_card, sound_noise=noise_card, eq_actions=eq_actions)
        cards.attach(eq_card, 0, 0, 5, 2)
        cards.attach(quick_card, 5, 0, 3, 1)
        cards.attach(noise_card, 5, 1, 3, 1)

        # Advanced options live in the overflow menu.
        outer.append(cards)
        outer.append(eq_actions)
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
        gestures_title = Gtk.Label(label=t("tab_gestures"), xalign=0)
        self.gestures_title = gestures_title
        gestures_title.add_css_class("eara-page-title")
        box.append(gestures_title)
        self.lbl_gestures = _ui_text(Gtk.Label(wrap=True, xalign=0))
        box.append(self.lbl_gestures)
        self.gesture_rows: list[tuple[str, str, Gtk.DropDown, Gtk.Label, Gtk.Button, Gtk.Label]] = []
        self._gesture_action_keys = list(GESTURE_ACTIONS.keys())
        action_labels = [_gesture_action_label(key) for key in self._gesture_action_keys]
        gesture_cards = Gtk.Box(spacing=14, homogeneous=True)
        box.append(gesture_cards)
        for side in ("left", "right"):
            side_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            side_card.add_css_class("eara-card")
            side_card.set_hexpand(True)
            gesture_cards.append(side_card)
            side_lab = _ui_text(Gtk.Label(xalign=0))
            side_lab.add_css_class("eara-gesture-side")
            side_card.append(side_lab)
            for gtype in GESTURE_TYPES:
                drop = Gtk.DropDown.new_from_strings(action_labels)
                lab = _ui_text(GestureLabel(label=gtype, xalign=0, hexpand=True))
                lab.kind = gtype
                motion.bind_gesture(drop, lab)
                lab.add_css_class("eara-gesture-type")
                lab.set_wrap(True)
                lab.set_max_width_chars(18)
                save = MotionButton()
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
                side_card.append(row)
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
        tools_title = Gtk.Label(label=t("tab_tools"), xalign=0)
        self.tools_title = tools_title
        tools_title.add_css_class("eara-page-title")
        box.append(tools_title)
        find_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        find_card.add_css_class("eara-card")
        find_title = Gtk.Label(label=t("find_earbuds"), xalign=0)
        self.find_title = find_title
        find_title.add_css_class("eara-dashboard-title")
        find_card.append(find_title)
        find_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        find_card.append(find_actions)
        tools_cards = Gtk.Box(spacing=14, homogeneous=True)
        tools_cards.set_valign(Gtk.Align.START)
        box.append(tools_cards)
        tools_cards.append(find_card)
        self.btn_find_l = MotionButton()
        self.btn_find_r = MotionButton()
        self.btn_find_both = MotionButton()
        self.btn_stop_ring = MotionButton()
        for b in (self.btn_find_l, self.btn_find_r, self.btn_find_both, self.btn_stop_ring):
            b.add_css_class("eara-chip")
        self.btn_find_l_label = _button_with_icon(self.btn_find_l, "find")
        self.btn_find_r_label = _button_with_icon(self.btn_find_r, "find")
        self.btn_find_both_label = _button_with_icon(self.btn_find_both, "find")
        self.btn_stop_ring_label = _button_with_icon(
            self.btn_stop_ring, "media-playback-stop-symbolic"
        )
        self.btn_find_l.connect("clicked", lambda *_: self._run(lambda: self._do_ring("left")))
        self.btn_find_r.connect("clicked", lambda *_: self._run(lambda: self._do_ring("right")))
        self.btn_find_both.connect("clicked", lambda *_: self._run(lambda: self._do_ring("both")))
        self.btn_stop_ring.connect("clicked", lambda *_: self._run(lambda: self._do_ring("off")))
        ring_row = Gtk.Box(spacing=8, homogeneous=True)
        ring_row.append(self.btn_find_l)
        ring_row.append(self.btn_find_r)
        find_actions.append(ring_row)
        ring_all_row = Gtk.Box(spacing=8, homogeneous=True)
        ring_all_row.append(self.btn_find_both)
        ring_all_row.append(self.btn_stop_ring)
        find_actions.append(ring_all_row)

        fit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fit_card.add_css_class("eara-card")
        self.fit_card = fit_card
        fit_title = Gtk.Label(label=t("fit_test"), xalign=0)
        self.fit_title = fit_title
        fit_title.add_css_class("eara-dashboard-title")
        fit_card.append(fit_title)
        self.lbl_fit_hint = _ui_text(Gtk.Label(wrap=True, xalign=0))
        self.lbl_fit_hint.add_css_class("dim-label")
        fit_card.append(self.lbl_fit_hint)
        self.btn_fit = MotionButton()
        self.btn_fit.add_css_class("eara-chip")
        self.btn_fit_label = _button_with_icon(self.btn_fit, "object-select-symbolic")
        self.btn_fit.connect("clicked", lambda *_: self._run(self._do_fit))
        self.btn_fit.set_halign(Gtk.Align.START)
        fit_card.append(self.btn_fit)
        self.fit_label = _ui_text(Gtk.Label(wrap=True, xalign=0))
        fit_card.append(self.fit_label)
        tools_cards.append(fit_card)

        self.lbl_legal = Gtk.Label(wrap=True, xalign=0)
        self.lbl_legal.add_css_class("dim-label")
        box.append(self.lbl_legal)
        return Gtk.ScrolledWindow(child=box)

    def _sync_reference_layout(self) -> None:
        page = self.stack.get_visible_child_name()
        connected = bool((getattr(self, "_last", None) or {}).get("protocol"))
        self.buttons.set_size_request(GEOMETRY["rail"], -1)
        (self.add_css_class if page == "device" else self.remove_css_class)("eara-device-page")
        icon = self._nav_icons["device"]
        icon.set_from_icon_name("eara-device-symbolic")
        recovery = page == "device" and not (connected and self._last.get("bt_connected"))
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_LIGHT if recovery else Adw.ColorScheme.FORCE_DARK)

    def _show_connection_help(self) -> None:
        dialog = Adw.MessageDialog(transient_for=self, modal=True,
                                  heading=t("still_not_connecting"), body=t("connect_hint"))
        dialog.add_response("close", "OK")
        dialog.set_close_response("close")
        dialog.present()

    def _open_details(self) -> None:
        self.btn_more.popdown()
        if not hasattr(self, "details_window"):
            self.details_window = Adw.Window(transient_for=self, modal=True)
            self.details_window.add_css_class("eara-window")
            self.details_window.set_default_size(600, 600)
            self.details_window.set_resizable(False)
            self.details_window.set_destroy_with_parent(True)
            self.details_window.set_hide_on_close(True)
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            body.append(Adw.HeaderBar())
            self.details_box.add_css_class("eara-content")
            for edge in ("top", "bottom", "start", "end"):
                getattr(self.details_box, "set_margin_" + edge)(24)
            scroll = Gtk.ScrolledWindow(child=self.details_box, vexpand=True)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            body.append(scroll)
            self.details_window.set_content(body)
        self.details_window.set_title(t("device_details"))
        self.details_window.present()

    def _show_tab(self, name: str) -> None:
        self.stack.set_visible_child_name(name)
        self._sync_reference_layout()
        if hasattr(self, "system_strip"):
            self.system_strip.set_visible(name == "device" and bool((getattr(self, "_last", None) or {}).get("protocol")))
        for key, btn in self._tab_buttons.items():
            if key == name:
                btn.add_css_class("eara-tab-active")
            else:
                btn.remove_css_class("eara-tab-active")

    def _reveal_navigation_item(self, key: str) -> bool:
        revealer = self._tab_revealers.get(key)
        if revealer is not None:
            revealer.set_reveal_child(True)
        return False

    def _set_navigation_connected(self, connected: bool) -> None:
        for key in ("sound", "gestures", "tools"):
            self._tab_buttons[key].set_sensitive(connected)
        if not connected and self.stack.get_visible_child_name() != "device":
            self._show_tab("device")

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
        self.btn_refresh.set_tooltip_text(t("refresh"))
        self.btn_about.set_tooltip_text(t("about"))
        self.btn_more.set_tooltip_text(t("more_options"))
        self.more_about.set_label(t("about"))
        self.menu_settings_title.set_text(t("menu_settings"))
        self.menu_device_title.set_text(t("tab_device"))
        self.lbl_tag.set_text(t("brand_tag"))
        titles = ("tab_device", "tab_sound", "tab_gestures", "tab_tools")
        for key, title_key in zip(self._tab_keys, titles):
            self._tab_labels[key].set_text(t(title_key))
            self._tab_buttons[key].set_tooltip_text(t(f"{key}_menu_hint"))
        for page, key in zip(self._stack_pages, titles):
            page.set_title(t(key))
        self.lbl_language.set_text(t("language"))
        self.lbl_pick.set_text(t("scan_pick_device", n=len(getattr(self, "_device_list", []))))
        _icon_button(self.btn_music, "music", t("music"))
        _icon_button(self.btn_calls, "calls", t("calls"))
        self.btn_disconnect.set_label(t("disconnect"))
        self.lbl_power_off.set_text(t("power_off_exit"))
        self.lbl_power_off_hint.set_text(t("power_off_exit_hint"))
        self.lbl_codec.set_text(t("codec"))
        self.lbl_audio_options.set_text(t("audio_options"))
        self.btn_codec.set_label(t("apply_codec"))
        self.lbl_codec_hint.set_text(t("codec_hint"))
        self.sound_title.set_text(t("tab_sound"))
        self.sound_subtitle.set_text(t("tune_earbuds"))
        self.gestures_title.set_text(t("tab_gestures"))
        self.tools_title.set_text(t("tab_tools"))
        self.find_title.set_text(t("find_earbuds"))
        self.fit_title.set_text(t("fit_test"))
        for key, label in self.dashboard_toggle_labels.items():
            label.set_text(t(key))
        self.lbl_quick_title.set_text(t("listening_panel"))
        self.lbl_eq_title.set_text(t("equalizer_title"))
        self.lbl_noise.set_text(t("noise"))
        selected_strength = self.anc_strength.get_selected()
        self._ignore_toggle = True
        try:
            self.anc_strength.set_model(Gtk.StringList.new([t(key).replace("ANC ", "") for key in ("high", "mid", "low", "adaptive")]))
            self.anc_strength.set_selected(selected_strength)
        finally:
            self._ignore_toggle = False
        self.lbl_dashboard_noise.set_text(t("noise"))
        self.lbl_dashboard_quick.set_text(t("quick"))
        self.lbl_audio_profile.set_text(t("audio_profile"))
        self.advanced.set_label(t("device_details"))
        self.recovery_eyebrow.set_text(t("tab_device").upper())
        self.recovery_title.set_text(t("connect_title"))
        self.recovery_hint.set_text(t("connect_hint"))
        self.found_label.set_text(t("found_devices"))
        self.steps_title.set_text(t("recovery_steps"))
        for label, key in zip(
            self.recovery_step_labels,
            ("recovery_case", "recovery_button", "recovery_refresh"),
        ):
            label.set_text(t(key))
        self.help_title.set_text(t("connection_help"))
        self.recovery_help_label.set_text(t("still_not_connecting"))
        self.recovery_paired.set_text(t("paired"))
        self.recovery_help_expander.get_child().set_text(t("connect_hint"))
        self.partial_label.set_text(t("partial_help"))
        self.btn_retry.get_child().set_text(t("retry_controls"))
        for label, key in zip(
            self.help_status_labels,
            ("bt_service_ready", "audio_service_ready", "controls_waiting"),
        ):
            label.set_text(t(key))
        self._update_help_health()
        self.btn_diagnostics_label.set_text(t("run_diagnostics"))
        self.btn_recovery_refresh_label.set_text(t("refresh_devices"))
        for mode, button in self.dashboard_anc_buttons.items():
            _icon_button(button, mode, "ANC" if mode == "high" else t(mode))
        for mode, button in self.dashboard_strength_buttons.items():
            button.set_label(t(mode).replace("ANC ", ""))
        self.lbl_eq.set_text("")
        self.lbl_eq.set_visible(False)
        self.lbl_custom.set_text(t("custom_eq"))
        self.btn_save_preset_label.set_text(t("save_preset"))
        self.btn_load_preset.set_label(t("load_preset"))
        self.btn_reset_eq_label.set_text(t("reset_eq"))
        self.lbl_eq_apply_hint.set_text(t("eq_apply_hint"))
        self.lbl_bass.set_text(t("bass"))
        self.lbl_bass_level.set_text(t("bass_level"))
        self.lbl_ied.set_text(t("in_ear"))
        self.lbl_lat.set_text(t("latency"))
        self.lbl_adv.set_text(t("adv_eq"))
        self.lbl_panc.set_text(t("personal_anc"))
        self.lbl_listening.set_text(t("listening_mode"))
        listening_labels = [t(f"listening_{mode}") for mode in LISTENING_MODES]
        self._listening_keys = list(LISTENING_MODES.keys())
        self.listening_drop.set_model(Gtk.StringList.new(listening_labels))
        for mode, btn in self.anc_buttons.items():
            if mode in ("off", "transparency", "high"):
                _icon_button(btn, mode, "ANC" if mode == "high" else t(mode), horizontal=True)
            else:
                btn.set_label(t(mode).replace("ANC ", ""))
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
        self.btn_find_l_label.set_text(t("find_left"))
        self.btn_find_r_label.set_text(t("find_right"))
        self.btn_find_both_label.set_text(t("find_both"))
        self.btn_stop_ring_label.set_text(t("stop_ring"))
        self.btn_fit_label.set_text(t("fit"))
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
        if self._busy or getattr(self, "_syncing_devices", False):
            return
        self.recovery_device_drop.set_selected(self.device_drop.get_selected())
        picked = self._selected_device()
        if picked:
            self.device = picked
            self._run(self._do_refresh)

    def _on_recovery_device_changed(self, *_args) -> None:
        if getattr(self, "_syncing_devices", False):
            return
        selected = int(self.recovery_device_drop.get_selected())
        devices = getattr(self, "_device_list", [])
        known = 0 <= selected < len(devices)
        self.recovery_device_name.set_text(devices[selected]["name"] if known else "—")
        self.recovery_paired.set_visible(known)
        if known:
            self.recovery_paired.set_text(t("paired") if devices[selected].get("paired", True) else t("new_device"))
        if selected != int(self.device_drop.get_selected()):
            self.device_drop.set_selected(selected)

    def _on_anc_strength_changed(self, *_args) -> None:
        if self._busy or self._ignore_toggle or not self.device:
            return
        mode = ("high", "mid", "low", "adaptive")[self.anc_strength.get_selected()]
        self._run(lambda: self._do_anc(mode))

    def _on_listening_changed(self, *_args) -> None:
        if self._busy or self._ignore_listening or not self.device:
            return
        idx = int(self.listening_drop.get_selected())
        if 0 <= idx < len(self._listening_keys):
            mode = self._listening_keys[idx]
            self._run(lambda: self._do_listening(mode))

    def _do_listening(self, mode: str) -> None:
        self._require().set_listening_mode(mode)
        self._last = {**(self._last or {}), "listening": mode}

    def _fill_devices(self, devices=None) -> None:
        if devices is None:
            self._run(self._discover_devices)
            return
        self._syncing_devices = True
        try:
            self._device_list = devices
            names = [f"{d['name']}  ({d['address']})" for d in devices]
            selected = next((i for i, d in enumerate(devices)
                             if self.device and d['address'] == self.device.address), None)
            if selected is None:
                selected = next((i for i, d in enumerate(devices)
                                 if d.get('paired') and (d.get('compatible') or self._services.is_compatible_name(d['name']))), None)
            if selected is None and devices:
                selected = next((i for i, d in enumerate(devices)
                                 if d.get('compatible') or self._services.is_compatible_name(d['name'])), 0)
            self.device_drop.set_model(Gtk.StringList.new(names))
            self.recovery_device_drop.set_model(Gtk.StringList.new(names))
            self.device_drop.set_selected(selected if selected is not None else Gtk.INVALID_LIST_POSITION)
            self.recovery_device_drop.set_selected(selected if selected is not None else Gtk.INVALID_LIST_POSITION)
        finally:
            self._syncing_devices = False
        self.lbl_pick.set_text(t("scan_pick_device", n=len(devices)))
        self._on_recovery_device_changed()
        extra = [d for i, d in enumerate(devices) if i != selected]
        self._render_found_options(extra if len(devices) > 1 else [])

    def _discover_devices(self) -> None:
        EarAWindow._post(self, lambda: self._show(t("scan_progress_zero")) or False)
        try:
            devices = self._services.scan_devices(7.0, progress=self._scan_progress)
        except Exception:
            devices = []
        if not devices:
            devices = self._services.paired_devices()
        def done():
            if not self._shutting_down:
                self._fill_devices(devices)
            return False
        EarAWindow._post(self, done)

    def _selected_device(self) -> Device | None:
        devices = getattr(self, "_device_list", [])
        idx = int(self.device_drop.get_selected())
        if 0 <= idx < len(devices):
            d = devices[idx]
            # Keep the same Device while the same earbuds stay selected: it remembers the
            # last case battery reading and the model detected from the serial number.
            if self.device is not None and self.device.address == d["address"].upper():
                return self.device
            return Device(d["address"], d["name"])
        return None

    def _require(self) -> Optional[Device]:
        # Selection is synchronized by GTK callbacks on the main thread.
        # Workers use the device captured when their operation was submitted.
        context = getattr(self, "_operation_context", None)
        picked = getattr(context, "device", None)
        if picked is not None:
            return picked
        if not self.device:
            try:
                self.device = Device.discover()
            except LookupError:
                return None
        return self.device

    def _about(self) -> None:
        self.btn_more.popdown()
        win = Adw.Window(transient_for=self, modal=True)
        self.about_window = win
        win.add_css_class("eara-window")
        win.add_css_class("eara-about-window")
        win.set_default_size(440, 460)
        win.set_resizable(False)
        win.set_destroy_with_parent(True)
        win.set_title(t("about"))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        for edge in ("top", "bottom", "start", "end"):
            getattr(outer, "set_margin_" + edge)(24)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card.add_css_class("eara-about-card")
        brand = Gtk.Label(label="EarA", xalign=0, hexpand=True)
        brand.add_css_class("eara-about-brand")
        version = _ui_text(Gtk.Label(label=__version__, valign=Gtk.Align.CENTER))
        version.add_css_class("eara-about-version")
        body = _ui_text(Gtk.Label(label=t("about_blurb"), wrap=True, xalign=0, max_width_chars=44))
        body.add_css_class("eara-about-body")
        link = Gtk.LinkButton(
            label=t("about_source"),
            uri="https://github.com/oneydef/EarA-linux",
        )
        link.add_css_class("eara-about-link")
        link.set_halign(Gtk.Align.START)
        meta = _ui_text(Gtk.Label(label="Copyright © 2026 oneydef", xalign=0))
        meta.add_css_class("eara-about-meta")
        support_title = _ui_text(Gtk.Label(label=t("about_support"), xalign=0))
        support_title.add_css_class("eara-menu-heading")
        support = _ui_text(Gtk.Label(label=t("about_support_body"), wrap=True, xalign=0))
        support.add_css_class("eara-about-meta")
        coffee = MotionButton(label=t("about_coffee_btn"))
        coffee.add_css_class("eara-chip")
        coffee.add_css_class("eara-about-coffee")
        coffee.set_hexpand(True)
        coffee.connect("clicked", lambda *_: _open_uri(win, SUPPORT_URL))
        heading = Gtk.Box(spacing=12)
        heading.append(brand)
        heading.append(version)
        card.append(heading)
        card.append(body)
        card.append(link)
        card.append(meta)
        support_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        support_box.add_css_class("eara-about-support")
        for widget in (support_title, support, coffee):
            support_box.append(widget)
        card.append(support_box)
        outer.append(card)

        close = MotionButton(label=t("about_close"))
        close.add_css_class("eara-chip")
        close.set_halign(Gtk.Align.END)
        close.connect("clicked", lambda *_: win.close())
        outer.append(close)

        win.set_content(outer)
        win.present()

    def _show(self, text: str) -> None:
        self.toast.add_toast(Adw.Toast(title=text))

    def _select_eq_preset(self, key: str) -> None:
        if key == "custom":
            saved = (getattr(self, "_last", None) or {}).get("graphic_eq")
            if isinstance(saved, list):
                motion.animate_eq(self, saved)
                self._eq_local = True
                self.lbl_eq_apply_hint.set_text(t("eq_apply_hint"))
            self._set_chip_active(self.eq_buttons, key)
            self.eq_bands[0].grab_focus()
        else:
            if self._busy:
                return
            # A pending Custom debounce must not overwrite the selected preset.
            if getattr(self, "_eq_apply_timer", 0):
                GLib.source_remove(self._eq_apply_timer)
                self._eq_apply_timer = 0
            motion.cancel_eq(self)
            self._run(lambda: self._do_eq_preset(key))

    def _save_eq_preset(self) -> None:
        from eara.eq_presets import save_preset
        try:
            save_preset(getattr(self, "_eq_target_gains", None) or [band.get_value() for band in self.eq_bands])
        except (OSError, ValueError) as exc:
            self._show(str(exc))
            return
        self._show(t("preset_saved"))

    def _load_eq_preset(self) -> None:
        from eara.eq_presets import load_preset
        try:
            gains = load_preset()
        except (OSError, ValueError) as exc:
            self._show(str(exc))
            return
        if gains is None:
            self._show(t("preset_missing"))
            return
        motion.animate_eq(self, gains, user=True)
        self._set_chip_active(self.eq_buttons, "custom")

    def _apply_eq(self) -> None:
        gains = getattr(self, "_eq_target_gains", None) or [s.get_value() for s in self.eq_bands]
        self._eq_local = True
        self._run(lambda: self._do_custom_eq(gains))

    def _reset_eq(self) -> None:
        motion.animate_eq(self, [0.0]*len(self.eq_bands), user=True)

    def _on_eq_band_changed(self, scale: Gtk.Scale, value_label: Gtk.Label) -> None:
        value = float(scale.get_value())
        value_label.set_text(f"{value:+g} dB" if value else "0 dB")
        frequency = (scale.get_tooltip_text() or "").split(" · ")[0]
        scale.set_tooltip_text(f"{frequency} · {value:+.1f} dB")
        if not self._eq_syncing:
            if hasattr(self, "lbl_eq_apply_hint"):
                self.lbl_eq_apply_hint.set_text(t("eq_apply_hint"))
            motion.cancel_eq(self)
            self._eq_local = True
            self._set_eq_dirty(True)

    def _set_eq_dirty(self, dirty: bool) -> None:
        self._eq_dirty = dirty
        if dirty:
            if hasattr(self, "lbl_eq_apply_hint"):
                self.lbl_eq_apply_hint.set_text(t("eq_apply_hint"))
            self._set_chip_active(self.eq_buttons, "custom")
            self._queue_eq_apply()

    def _queue_eq_apply(self) -> None:
        """Coalesce slider motion; never write on refresh or to another device."""
        if getattr(self, "_eq_apply_timer", 0):
            GLib.source_remove(self._eq_apply_timer)
            self._eq_apply_timer = 0
        device = self.device
        if not device or not (getattr(self, "_last", None) or {}).get("protocol"):
            return
        def apply_pending():
            if self.device is not device or self._shutting_down or not self._last.get("protocol"):
                self._eq_apply_timer = 0
                return False
            if self._busy:
                return True
            self._eq_apply_timer = 0
            if self._eq_dirty:
                self._apply_eq()
            return False
        self._eq_apply_timer = GLib.timeout_add(300, apply_pending)

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
            self.btn_reset_eq,
            self.btn_codec,
            self.device_drop,
            self.recovery_device_drop,
            self.btn_find_l,
            self.btn_find_r,
            self.btn_find_both,
            self.btn_stop_ring,
            self.btn_fit,
            self.btn_retry,
            self.listening_drop,
            self.anc_strength,
            self.btn_recovery_refresh,
        ]
        widgets.extend(self.anc_buttons.values())
        widgets.extend(self.dashboard_anc_buttons.values())
        widgets.extend(self.dashboard_strength_buttons.values())
        widgets.extend(self.eq_buttons.values())
        for _side, _gtype, drop, _lab, save, _side_lab in self.gesture_rows:
            widgets.extend((drop, save))
        for switch in (
            self.bass_switch,
            self.ied_switch,
            self.lat_switch,
            self.adv_switch,
            self.panc_switch,
            *self.dashboard_switches.values(),
        ):
            widgets.append(switch)
        return widgets

    def _set_busy(self, busy: bool) -> None:
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            widgets = [*self._busy_widgets(), self.bass_level]
            self._busy_input_states = [(widget, widget.get_can_target(), widget.get_focusable())
                                       for widget in widgets]
            for widget, _, _ in self._busy_input_states:
                widget.set_can_target(False)
                widget.set_focusable(False)
        else:
            for widget, can_target, focusable in getattr(self, "_busy_input_states", []):
                widget.set_can_target(can_target)
                widget.set_focusable(focusable)
            self._busy_input_states = []

    def _post(self, callback, *args):
        """Discard queued worker UI callbacks after close, cancel or replacement."""
        context = getattr(self, "_operation_context", None)
        generation = getattr(context, "generation", getattr(self, "_busy_generation", 0))
        device = getattr(context, "device", getattr(self, "device", None))
        cancel = getattr(context, "cancel", None)
        def deliver():
            if getattr(self, "_shutting_down", False) or getattr(self, "_busy_generation", 0) != generation:
                return False
            if cancel is not None and cancel.is_set():
                return False
            if device is not None and getattr(self, "device", None) is not device:
                return False
            callback(*args)
            return False
        return GLib.idle_add(deliver)

    def _run(self, fn, *, soft_timeout: float = 90.0, local_widgets=None, repaint=None) -> None:
        if self._busy or getattr(self, "_shutting_down", False):
            return
        if getattr(self, "_device_list", []):
            picked = self._selected_device()
            if picked is not None:
                self.device = picked
        action = getattr(self, "_motion_action", None)
        self._motion_action = None
        if fn == getattr(self, "_do_connect", None):
            self.header_status_dot.add_css_class("eara-dot-connecting")
        # Small control changes keep the rest of the page visually stable.
        # The operation lock still serializes all device commands.
        sensitivity = [(widget, widget.get_can_target(), widget.get_focusable()) for widget in local_widgets] if local_widgets is not None else None
        if sensitivity is None:
            self._set_busy(True)
        else:
            self._busy = True
            # Do not change :disabled while GtkSwitch is animating: it
            # interrupts the native transition and dims/re-enables the control.
            for widget, _can_target, _focusable in sensitivity:
                widget.set_can_target(False)
                widget.set_focusable(False)
        generation = getattr(self, "_busy_generation", 0) + 1
        self._busy_generation = generation
        device = getattr(self, "device", None)
        if not hasattr(self, "_operation_context"):
            self._operation_context = threading.local()
        context = self._operation_context
        snapshot = deepcopy(getattr(self, "_last", {}))
        cancel = threading.Event()
        self._operation_cancel = cancel

        def worker():
            context.device = device
            context.status = snapshot
            context.generation = generation
            context.cancel = cancel
            err = None
            try:
                with operations.scope(soft_timeout if soft_timeout > 0 else 90, cancel):
                    fn()
            except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
                err = str(exc)
            except Exception as exc:
                # A plugin/library exception must not strand the window in its
                # busy state. Keep the traceback for diagnostics and surface a
                # compact error in the UI before re-enabling the controls.
                traceback.print_exc()
                err = f"{type(exc).__name__}: {exc}"
            finally:
                if err:
                    cancel.set()
                status = context.status
                del context.device
                del context.status
                del context.generation
                del context.cancel

            def done():
                if getattr(self, "_busy_generation", 0) != generation or getattr(self, "_shutting_down", False):
                    return False
                if sensitivity is None:
                    self._set_busy(False)
                else:
                    self._busy = False
                    for widget, can_target, focusable in sensitivity:
                        widget.set_can_target(can_target)
                        widget.set_focusable(focusable)
                if hasattr(self, "header_status_dot"):
                    self.header_status_dot.remove_css_class("eara-dot-connecting")
                if device is not None and getattr(self, "device", None) is not device:
                    return False
                if not err and not cancel.is_set():
                    self._last = status
                if err and isinstance(action, MotionButton):
                    action.set_feedback("error")
                if err:
                    self._show(err)
                (repaint or self._paint)()
                return False

            # Completion unlocks user input. Do not let continuous GTK redraws
            # starve it at the lower default idle priority (notably GTK 4.6).
            GLib.idle_add(done, priority=GLib.PRIORITY_DEFAULT)

        def watchdog():
            if getattr(self, "_busy_generation", 0) != generation or not self._busy:
                return False
            cancel.set()
            # Keep commands exclusive until the in-flight platform call returns
            # and the worker observes cancellation; never start a second connect.
            self._show(t("connect_timeout") if fn == self._do_connect else t("busy_timeout"))
            return False

        threading.Thread(target=worker, daemon=True).start()
        if soft_timeout > 0:
            GLib.timeout_add(int(soft_timeout * 1000), watchdog)

    def _bootstrap(self) -> bool:
        self._run(self._restore_connection)
        return False

    def _restore_connection(self) -> None:
        devices = self._services.paired_devices()
        candidate = next((d for d in devices if d.get('compatible') or self._services.is_compatible_name(d['name'])), None)
        device = Device(candidate['address'], candidate['name']) if candidate else None
        def populate():
            if not self._shutting_down:
                self.device = device
                self._fill_devices(devices)
            return False
        EarAWindow._post(self, populate)
        # Read the existing link. Never connect, reset or reload audio on startup.
        status = device.status() if device else {}
        if not self._shutting_down:
            self._last = status

    def _refresh_battery(self) -> bool:
        """Re-read the battery while the window is open.

        The case only reports while a bud is docked, so a single read at startup
        usually misses it. Skipped while another action runs; never connects.
        """
        if self._shutting_down:
            return False
        device = self.device
        if device is None or self._busy or self._battery_refreshing:
            return True
        self._battery_refreshing = True

        def worker():
            battery = None
            try:
                battery = device.battery()
            except Exception:
                # A failed background refresh must never leave refreshes wedged.
                pass
            GLib.idle_add(self._show_battery, device, battery)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _show_battery(self, device: Device, battery: dict | None) -> bool:
        self._battery_refreshing = False
        if battery is None or device is not self.device or self._busy:
            return False
        self._last = {**(self._last or {}), "battery": battery}
        for key in ("left", "right", "case"):
            item = battery.get(key)
            self._update_battery_cell(key, item if isinstance(item, dict) else None)
        return False

    def _do_connect(self) -> None:
        EarAWindow._post(self, lambda: self._show(t("connect_busy")) or False)
        device = self._require()
        if device is None:
            # Native flow like the phone app: reuse the last scan results when
            # they exist, so a retry never re-enters discovery in a loop.
            candidates = list(getattr(self, "_scan_candidates", []))
            if candidates:
                EarAWindow._post(self, lambda: self._fill_devices(candidates) or False)
            else:
                EarAWindow._post(self, lambda: self._show(t("scan_progress_zero")) or False)
                candidates = self._services.scan_devices(9.0, progress=self._scan_progress)
                if not candidates:
                    raise LookupError(t("scan_none"))
                self._scan_candidates = candidates
                EarAWindow._post(self, lambda: self._fill_devices(candidates) or False)
            best = candidates[0]
            EarAWindow._post(self, lambda: self._show(t("pairing") if not best.get("paired") else t("connect_busy")) or False)
            device = Device(best["address"], best["name"])
            self.device = device
        # A missing host audio sink must not tear down working earbud control.
        # Resume the existing session before attempting audio recovery.
        if device.connected:
            status = device.status(refresh_audio=True)
            if status.get("bt_connected") and status.get("protocol"):
                self._last = status
                self._scan_candidates = []
                message = "connect_ok" if (status.get("audio") or {}).get("sink") else "connect_controls_only"
                EarAWindow._post(self, lambda: self._render_found_options([]))
                EarAWindow._post(self, lambda: self._show(t(message)))
                return
        if not self._services.is_paired(device.address):
            EarAWindow._post(self, lambda: self._show(t("pairing").format(name=device.name)) or False)
            self._services.pair(device.address)
        # Keep the header button responsive: fewer retries, fast path if already linked.
        try:
            result = device.connect_audio(False, attempts=2)
        except RuntimeError as exc:
            if "not paired" in str(exc):
                # The buds accepted Pair() and then dropped it — they are still
                # acting as a phone headset. Pairing mode is the only way through.
                raise LookupError(t("pairing_dropped"))
            raise
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error")))
        self._last = self.device.status() if self.device else {}
        self._scan_candidates = []
        EarAWindow._post(self, lambda: self._render_found_options([]) or False)
        EarAWindow._post(self, lambda: self._show(t("connect_ok")) or False)

    def _scan_progress(self, found: int) -> None:
        if self._shutting_down:
            return
        message = t("scan_progress").format(n=found) if found else t("scan_progress_zero")
        EarAWindow._post(self, lambda: self._show(message) or False)

    def _render_found_options(self, candidates: list) -> None:
        """Show extra scan candidates as compact rows under the main device row."""
        from eara.ui_widgets import reference_art

        if getattr(self, "_syncing_devices", False):
            return
        for child in list(self.found_options):
            self.found_options.remove(child)
        selected = int(self.recovery_device_drop.get_selected())
        devices = list(getattr(self, "_device_list", []))
        for index, cand in enumerate(devices):
            if index == selected and self.device is not None:
                continue
            row = Gtk.Box(spacing=10)
            row.add_css_class("eara-option-row")
            art = reference_art(_asset_path("ui/reference-recovery.png"), (349, 440, 129, 85)) if _asset_path("ui/reference-recovery.png") else None
            if art is not None:
                art.add_css_class("eara-recovery-device-art")
                art.set_size_request(46, 32)
                row.append(art)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            name = Gtk.Label(label=cand.get("name", "—"), xalign=0)
            name.add_css_class("eara-option-name")
            text.append(name)
            badge_text = t("paired") if cand.get("paired") else t("new_device")
            badge = Gtk.Label(label=badge_text, xalign=0)
            badge.add_css_class("eara-option-badge")
            text.append(badge)
            rssi = cand.get("rssi")
            if rssi is not None:
                name.set_tooltip_text(t("signal_strength").format(db=rssi))
            row.append(text)
            pick = MotionButton(label=t("connect"))
            pick.add_css_class("eara-option-connect")
            pick.connect("clicked", lambda *_, i=index: self._pick_and_connect(i))
            row.append(pick)
            self.found_options.append(row)

    def _pick_and_connect(self, index: int) -> None:
        self._syncing_devices = True
        try:
            self.device_drop.set_selected(index)
            self.recovery_device_drop.set_selected(index)
        finally:
            self._syncing_devices = False
        self._on_recovery_device_changed()
        self._set_header_active("connect")
        self._run(self._do_connect)

    def _do_reset(self) -> None:
        result = self._require().reset_connection()
        self._last = self.device.status() if self.device else {}
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "Reset did not restore A2DP"))
        EarAWindow._post(self, lambda: self._show(t("reset_ok")) or False)

    def _do_disconnect(self) -> None:
        ear = self._require()
        name = ear.name
        ear.disconnect_audio()
        self._last = {
            "name": name,
            "bt_connected": False,
            "protocol": False,
        }
        EarAWindow._post(self, lambda: self._show(t("disconnect_ok")) or False)

    def _shutdown_bluetooth(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        cancel = getattr(self, "_operation_cancel", None)
        if cancel is not None:
            cancel.set()
        self._busy_generation = getattr(self, "_busy_generation", 0) + 1
        device = self.device
        power_off = power_off_on_exit()
        def cleanup():
            if device:
                device.shutdown(power_off=power_off)
            elif power_off:
                try:
                    self._services.power_off()
                except Exception:
                    pass
        threading.Thread(target=cleanup, daemon=True).start()

    def _on_power_off_exit_changed(self, switch: Gtk.Switch, _pspec) -> None:
        set_power_off_on_exit(bool(switch.get_active()))

    def _on_close_request(self, *_args) -> bool:
        self._shutdown_bluetooth()
        return False

    def _do_refresh(self) -> None:
        self._last = self._require().status(refresh_audio=True)

    def _do_audio(self, mic: bool) -> None:
        ear = self._require()
        result = ear.connect_audio(with_mic=mic)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "Audio switch failed"))
        self._last = ear.status()
        if mic:
            EarAWindow._post(self, lambda: self._show(t("mic_ok")) or False)

    def _do_anc(self, mode: str) -> None:
        ear = self._require()
        ear.set_anc(mode)
        self._last = ear.status()

    def _do_eq_preset(self, key: str) -> None:
        ear = self._require()
        ear.set_eq(key)
        status = ear.status()
        if status.get("eq") != key:
            raise RuntimeError(t("eq_not_confirmed"))
        self._last = status
        def accepted():
            self._eq_local = False
            self._set_eq_dirty(False)
            return False
        EarAWindow._post(self, accepted)

    def _do_custom_eq(self, gains: list[float]) -> None:
        self._require().set_graphic_eq(gains)
        self._last = self.device.status() if self.device else {}
        EarAWindow._post(self, lambda: self._set_eq_dirty(False) or False)

    def _do_codec(self, name: str) -> None:
        result = self._require().set_codec(name)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error")))
        self._last = self.device.status() if self.device else {}

    def _do_gesture(self, side: str, gtype: str, selected: int) -> None:
        action = self._gesture_action_keys[selected]
        self._require().set_gesture(side, gtype, action)
        self._last = self._require().status()

    def _do_ring(self, side: str) -> None:
        self._require().ring(side)
        def confirmed():
            if not self._shutting_down:
                self.btn_find_l.set_feedback("ringing" if side in ("left", "both") else None)
                self.btn_find_r.set_feedback("ringing" if side in ("right", "both") else None)
            return False
        EarAWindow._post(self, confirmed)

    def _do_fit(self) -> None:
        EarAWindow._post(self, lambda: self._show(t("fit_running")) or False)
        try:
            self._fit = self._require().ear_tip_test()
        except RuntimeError as exc:
            key = str(exc)
            if key in ("fit_timeout", "fit_unsupported"):
                raise RuntimeError(t(key)) from exc
            raise
        EarAWindow._post(self, self._update_fit_label)

    def _update_fit_label(self) -> bool:
        if getattr(self, "_fit", None):
            if getattr(self, "_motion_fit_result", None) != self._fit:
                self._motion_fit_result = self._fit
                motion.reveal(self.fit_label)
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
        level = round(self.bass_level.get_value())  # read here: _toggle runs off the GTK thread
        if which == "bass":
            self.bass_level.set_sensitive(enabled)
        widgets = [self.bass_switch, self.ied_switch, self.lat_switch,
                   self.adv_switch, self.panc_switch,
                   *self.dashboard_switches.values(), self.bass_level]
        self._run(lambda: self._toggle(which, enabled, level),
                  local_widgets=widgets, repaint=self._paint_toggles)

    def _on_bass_level_changed(self, *_args) -> None:
        if self._ignore_toggle or not self.device:
            return
        # Apply once the slider has settled, not on every step of a drag.
        if self._bass_level_timer:
            GLib.source_remove(self._bass_level_timer)
        self._bass_level_timer = GLib.timeout_add(500, self._apply_bass_level)

    def _apply_bass_level(self) -> bool:
        if self._shutting_down:
            self._bass_level_timer = 0
            return False
        if self._busy:
            return True  # try again once the running action is done
        self._bass_level_timer = 0
        level = round(self.bass_level.get_value())
        self._run(lambda: self._toggle("bass", True, level))
        return False

    def _toggle(self, which: str, enabled: bool, bass_level: float = 1.0) -> None:
        ear = self._require()
        if which == "bass":
            ear.set_bass(enabled, bass_level)
        elif which == "ied":
            ear.set_in_ear_detection(enabled)
        elif which == "lat":
            ear.set_latency(enabled)
        elif which == "adv":
            ear.set_advanced_eq(enabled)
        elif which == "panc":
            ear.set_personalized_anc(enabled)
        else:
            raise ValueError(f"Unknown toggle: {which}")
        key = {"bass": "bass", "ied": "in_ear", "lat": "latency",
               "adv": "advanced_eq", "panc": "personalized_anc"}[which]
        value = {"enabled": enabled, "level": int(max(0, min(5, bass_level)) * 2) / 2} if which == "bass" else enabled
        self._last = {**(getattr(self, "_last", None) or {}), key: value}

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
        self.row_bass_level.set_visible(bool(caps.get("bass_enhance")))
        self.row_ied.set_visible(bool(caps.get("in_ear", True)))
        self.row_lat.set_visible(bool(caps.get("low_latency", True)))
        self.row_adv.set_visible(bool(caps.get("advanced_eq", True)))
        self.row_panc.set_visible(bool(caps.get("personalized_anc")))
        self.listening_box.set_visible(bool(caps.get("listening_mode")))
        self.lbl_noise.set_visible(bool(caps.get("anc")))
        self.anc_flow.set_visible(bool(caps.get("anc")))
        self.lbl_eq.set_visible(False)
        self.eq_flow.set_visible(bool(caps.get("eq_presets", True)))
        family = str(caps.get("eq_preset_family") or "standard")
        visible_presets = CMF_BUDS_2_EQ_PRESETS if family == "cmf-buds-2" else EQ_PRESETS
        for key, button in self.eq_buttons.items():
            button.set_visible(key in visible_presets)
            button.get_parent().set_visible(key in visible_presets)
        self.graphic_box.set_visible(bool(caps.get("custom_eq", True)))
        self.btn_reset_eq.set_visible(bool(caps.get("custom_eq", True)))
        self.btn_save_preset.set_visible(bool(caps.get("custom_eq", True)))
        self.btn_load_preset.set_visible(bool(caps.get("custom_eq", True)))
        self.lbl_eq_apply_hint.set_visible(bool(caps.get("custom_eq", True)))
        self.lbl_custom.set_visible(False)
        self.graphic_box.set_tooltip_text(t("custom_eq"))
        find_visible = bool(caps.get("find_my", True))
        self.btn_find_l.set_visible(find_visible)
        self.btn_find_r.set_visible(find_visible)
        self.btn_find_both.set_visible(find_visible)
        self.btn_stop_ring.set_visible(find_visible)
        gestures_tab = bool(caps.get("gestures", True))
        self._tab_buttons["gestures"].set_visible(gestures_tab)
        if not gestures_tab and self.stack.get_visible_child_name() == "gestures":
            self._show_tab("device")

    def _paint_toggles(self) -> None:
        """Synchronize both pages without rebuilding unrelated UI state."""
        status = getattr(self, "_last", None) or {}
        self._ignore_toggle = True
        try:
            if status.get("latency") is not None:
                self.lat_switch.set_active(bool(status["latency"]))
                self.dashboard_switches["lat"].set_active(bool(status["latency"]))
            if status.get("in_ear") is not None:
                self.ied_switch.set_active(bool(status["in_ear"]))
                self.dashboard_switches["ied"].set_active(bool(status["in_ear"]))
            bass = status.get("bass") or {}
            if isinstance(bass, dict) and "enabled" in bass:
                self.bass_switch.set_active(bool(bass["enabled"]))
                self.dashboard_switches["bass"].set_active(bool(bass["enabled"]))
                self.bass_level.set_sensitive(bool(bass["enabled"]))
                if bass.get("level"):
                    self.bass_level.set_value(max(1.0, min(5.0, float(bass["level"]))))
            if status.get("advanced_eq") is not None:
                self.adv_switch.set_active(bool(status["advanced_eq"]))
            if status.get("personalized_anc") is not None:
                self.panc_switch.set_active(bool(status["personalized_anc"]))
        finally:
            self._ignore_toggle = False

    @timed("gui.paint_state")
    def _paint(self) -> None:
        status = getattr(self, "_last", None) or {}
        if getattr(self, "_fit", None):
            self._update_fit_label()
        caps = (status.get("model") or {}).get("features") or {}
        if not caps and self.device:
            caps = self.device.model.as_dict().get("features") or {}
        self._update_help_health()
        self._apply_capabilities(caps)
        self._sync_reference_layout()
        connected = bool(status.get("bt_connected") and status.get("protocol"))
        if not connected:
            for button in (self.btn_find_l, self.btn_find_r):
                if button.feedback == "ringing":
                    button.set_feedback(None)
        self.btn_about.set_visible(not connected)
        self.btn_refresh.set_visible(connected)
        self.system_strip.set_visible(connected and self.stack.get_visible_child_name() == "device")
        if hasattr(self, "fit_card"):
            name = (status.get("name") or (self.device.name if self.device else "")).lower()
            show_fit = bool(caps.get("ear_tip_fit", True)) or "ear (a)" in name
            self.fit_card.set_visible(show_fit)
        if not status:
            self._set_navigation_connected(False)
            if hasattr(self, "fit_card") and self.device:
                nm = self.device.name.lower()
                self.fit_card.set_visible(self.device.model.ear_tip_fit or "ear (a)" in nm)
            return
        name = status.get("name") or "—"
        model = (status.get("model") or {}).get("name") or name
        bt_ok = bool(status.get("bt_connected"))
        proto_ok = bool(status.get("protocol"))
        self.partial_card.set_visible(bt_ok and not proto_ok)
        self._set_navigation_connected(bt_ok and proto_ok)
        self._set_service_health("bluetooth", "ok" if bt_ok else "off")
        self._set_service_health("rfcomm", "ok" if proto_ok else ("warn" if bt_ok else "off"))
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
        for css in ("eara-dot-ok", "eara-dot-warn", "eara-dot-off"):
            self.header_status_dot.remove_css_class(css)
        self.header_status_dot.add_css_class(dot)
        self.header_device_label.set_text(name if bt_ok else t("status_offline"))
        self.header_status_arrow.set_visible(bt_ok)
        (self.header_status.remove_css_class if bt_ok else self.header_status.add_css_class)("eara-offline-pill")
        self.device_state_stack.set_visible_child_name("connected" if bt_ok and proto_ok else "recovery")
        self._set_badge(self.badge_bt, ("●  " + t("status_ready")) if bt_ok and proto_ok else t("bt_off"), "ok" if bt_ok else "bad")
        self._set_badge(
            self.badge_proto,
            t("protocol_ok" if proto_ok else "protocol_no"),
            "ok" if proto_ok else ("warn" if bt_ok else "bad"),
        )
        fw = status.get("firmware") or "—"
        serial_raw = status.get("serial") or status.get("address") or "—"
        serial = _mask_serial(str(serial_raw))
        self.status_meta.set_text("")
        self.status_card.set_tooltip_text(f"{headline} · {model} · fw {fw} · {serial}")
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
            self._set_chip_active(self.eq_buttons, "custom" if self._eq_local else eq_name)
        if isinstance(anc_name, str):
            self._set_chip_active(self.anc_buttons, "high" if anc_name in ("low", "mid", "high", "adaptive") else anc_name)
            self._ignore_toggle = True
            try:
                self.anc_strength.set_sensitive(anc_name not in ("off", "transparency"))
                if anc_name in ("high", "mid", "low", "adaptive"):
                    self.anc_strength.set_selected(("high", "mid", "low", "adaptive").index(anc_name))
            finally:
                self._ignore_toggle = False
            self._set_chip_active(self.dashboard_anc_buttons, "high" if anc_name in ("low", "mid", "high", "adaptive") else anc_name)
            self._set_chip_active(self.dashboard_strength_buttons, anc_name)
        gestures = status.get("gestures")
        if isinstance(gestures, dict):
            self._sync_gesture_dropdowns(gestures)
        self._paint_toggles()
        listening = status.get("listening")
        if isinstance(listening, str) and listening in self._listening_keys:
            self._ignore_listening = True
            try:
                self.listening_drop.set_selected(self._listening_keys.index(listening))
            finally:
                self._ignore_listening = False
        from eara.eq_presets import display_gains
        graphic, preview = display_gains(status)
        if isinstance(graphic, list) and not self._eq_local:
            motion.animate_eq(self, graphic)
            self._set_eq_dirty(False)
        preview = preview and not self._eq_local
        self.lbl_eq_apply_hint.set_text(t("eq_preview_hint") if preview else t("eq_apply_hint"))
        self.graphic_box.set_tooltip_text(t("eq_preview_hint") if preview else t("custom_eq"))
        audio_info = status.get("audio") or {}
        profile = str(audio_info.get("profile") or "").lower()
        self.btn_music.remove_css_class("eara-dashboard-primary")
        self._set_chip_active({"music": self.btn_music, "calls": self.btn_calls},
                              "music" if "a2dp" in profile else "calls" if "headset" in profile or "handsfree" in profile else None)
        audio_ok = bool(audio_info.get("sink") or audio_info.get("profile") or audio_info.get("codec"))
        self._set_service_health("pipewire", "ok" if audio_ok else ("warn" if bt_ok else "off"))
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
        # PyGObject: super().do_shutdown() can call Gio.Application.shutdown() incorrectly.
        Adw.Application.do_shutdown(self)

    def do_activate(self) -> None:  # noqa: N802
        win = self.props.active_window
        if not win:
            win = EarAWindow(self)
        win.present()


def _gtk_log_handler(log_domain, log_level, message, unused_data=None) -> None:
    """Keep GTK 4.10's cosmetic corner-value critical quiet, forward the rest.

    `_gtk_css_corner_value_get_x/y: assertion 'corner->class == ...'` fires from
    inside GTK's own snapshot code (a border-radius value type check); rendering
    falls back and continues. EarA's stylesheet is verified clean, and this class
    of GTK 4.10 renderer warning is fixed upstream in later releases, so filter
    exactly this message and leave every other critical visible.
    """
    if "_gtk_css_corner_value_get_" in message:
        return
    GLib.log_default_handler(log_domain, log_level, message, unused_data)


def _quiet_gtk_corner_criticals() -> None:
    try:
        GLib.log_set_handler("Gtk", GLib.LogLevelFlags.LEVEL_CRITICAL, _gtk_log_handler)
    except Exception:
        pass  # a logging filter must never break startup


def run() -> int:
    _quiet_gtk_corner_criticals()
    return EarAApp().run(None)
