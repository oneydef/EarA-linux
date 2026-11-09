"""Battery and noise control in a StatusNotifier-compatible desktop panel.

Gio exports the small StatusNotifierItem interface; libdbusmenu handles menus.
Ubuntu's libayatana-appindicator is GTK3-only and does not expose Activate,
so it cannot provide the direct window activation needed here.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import gi

from gi.repository import Gio, GLib

from eara.i18n import load_lang, t
from eara.protocol import ANC_MODES
from eara.session import Device

ITEM_PATH = "/StatusNotifierItem"
ITEM_INTERFACE = "org.kde.StatusNotifierItem"
WATCHER = "org.kde.StatusNotifierWatcher"
POLL_SECONDS = 10

ITEM_XML = """
<node><interface name="org.kde.StatusNotifierItem">
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <property name="Id" type="s" access="read"/>
  <property name="Category" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <signal name="NewToolTip"/>
  <signal name="NewIcon"/>
  <signal name="NewStatus"><arg type="s"/></signal>
</interface></node>
"""


def battery_text(item: dict | None) -> str:
    if not item or not item.get("available"):
        return "—"
    return f"{'~' if item.get('stale') else ''}{item['level']}%{'+' if item.get('charging') else ''}"


def panel_icon(status: dict) -> str:
    """Draw separate battery gauges and a listening-mode symbol without GTK."""
    available = status.get("bt_connected") and status.get("protocol")
    battery = (status.get("battery") or {}) if available else {}
    anc = status.get("anc") if available else None
    has_anc = status.get("model", {}).get("features", {}).get("anc", True)
    width = 40 if has_anc else 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="22" viewBox="0 0 {width} 22">',
        '<defs><g id="buds" fill="none" stroke-linecap="round" stroke-linejoin="round">',
        '<path d="M7 3C2 1 1 8 5 9v5h3V6C8 4 8 3 7 3Z"/>',
        '<path d="M13 3c5-2 6 5 2 6v5h-3V6c0-2 0-3 1-3Z"/>',
    ]
    if has_anc:
        if anc in ("high", "mid", "low", "adaptive"):
            parts.append('<path d="m29 3 6 2v5c0 3-3 5-6 7-3-2-6-4-6-7V5Z"/>')
        elif anc == "transparency":
            parts.append('<path d="M25 6q-4 4 0 8m-3-11q-7 7 0 14m10-11q4 4 0 8m3-11q7 7 0 14"/>')
        elif anc == "off":
            parts.append('<circle cx="29" cy="10" r="5"/>')
        else:
            parts.append('<path d="M24 10h1m4 0h1m4 0h1"/>')
    # A thin dark outline keeps the light strokes visible on light panels too.
    parts.extend([
        '</g></defs><use href="#buds" stroke="#242424" stroke-width="2.5"/>',
        '<use href="#buds" stroke="#eeeeec" stroke-width="1.5"/>',
    ])
    for side, x in (("left", 2), ("right", 12)):
        item = battery.get(side) or {}
        known = item.get("available") and not item.get("stale")
        if not known:
            parts.append(f'<path d="M{x} 19h2m3 0h2" stroke="#999999" stroke-width="2"/>')
            continue
        level = max(0, min(100, item["level"]))
        color = "#ff7b63" if level <= 20 else "#eeeeec"
        border = color if level == 0 else "#242424"
        parts.append(f'<rect x="{x}" y="18" width="7" height="2" rx="1" fill="#62666c" stroke="{border}" stroke-width="1"/>')
        if level:
            parts.append(f'<rect x="{x}" y="18" width="{7 * level / 100:g}" height="2" rx="1" fill="{color}"/>')
    parts.append('</svg>')
    return "".join(parts)


class IndicatorApp(Gio.Application):
    def __init__(self, preferred: str = "") -> None:
        super().__init__(application_id="io.github.oneydef.eara.Indicator")
        self.preferred = preferred
        self.device: Device | None = None
        self._busy = False
        self._stopping = False
        self._pending_mode: str | None = None

    def do_startup(self) -> None:
        Gio.Application.do_startup(self)
        self.hold()
        load_lang()
        self._icon_dir = TemporaryDirectory(prefix="eara-indicator-")
        self._icon_files: list[Path] = []
        self._icon_svg = ""
        self._properties = {
            "Id": GLib.Variant("s", "eara"),
            "Category": GLib.Variant("s", "Hardware"),
            "Title": GLib.Variant("s", "EarA"),
            "Status": GLib.Variant("s", "Passive"),
            "IconName": GLib.Variant("s", "audio-headphones-symbolic"),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", ITEM_PATH + "/Menu"),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("audio-headphones-symbolic", [], "EarA", "")),
        }
        self._build_menu()
        self._bus = self.get_dbus_connection()
        interface = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        self._registration = self._bus.register_object(
            ITEM_PATH, interface, self._method_call,
            lambda connection, sender, path, iface, name: self._properties[name], None,
        )
        self._watcher = Gio.bus_watch_name_on_connection(
            self._bus, WATCHER, Gio.BusNameWatcherFlags.NONE, self._host_appeared, None,
        )
        self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._refresh)
        self._refresh()

    def do_activate(self) -> None:
        # Gio.Application makes repeated launches reuse the existing indicator.
        pass

    def _build_menu(self) -> None:
        from gi.repository import Dbusmenu

        self._menu_root = Dbusmenu.Menuitem.new()
        self._menu_server = Dbusmenu.Server.new(ITEM_PATH + "/Menu")
        self._menu_server.set_root(self._menu_root)
        self._item(t("indicator_open"), self._open_window)
        self._device_item = self._item(t("looking"))
        self._battery_items = {side: self._item(t(key)) for side, key in (
            ("left", "left"), ("right", "right"), ("case", "case_label"),
        )}
        self._item(t("noise"))
        self._anc_items = {}
        for mode in ANC_MODES:
            item = self._item(t(mode), lambda mode=mode: self._refresh(mode))
            item.property_set("toggle-type", "radio")
            item.property_set_int("toggle-state", 0)
            item.property_set_bool("enabled", False)
            self._anc_items[mode] = item
        self._item(t("refresh"), self._refresh)
        self._item(t("indicator_quit"), self.quit)

    def _item(self, label: str, action=None):
        from gi.repository import Dbusmenu

        item = Dbusmenu.Menuitem.new()
        item.property_set("label", label)
        item.property_set_bool("enabled", action is not None)
        if action is not None:
            item.connect("item-activated", lambda *_: action())
        self._menu_root.child_append(item)
        return item

    def _host_appeared(self, connection, name, owner) -> None:
        connection.call(
            WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (ITEM_PATH,)), None, Gio.DBusCallFlags.NONE, 5000,
            None, self._registered,
        )

    def _registered(self, connection, result) -> None:
        try:
            connection.call_finish(result)
        except GLib.Error as exc:
            print(f"Panel registration failed: {exc.message}", file=sys.stderr)

    def _method_call(self, connection, sender, path, interface, method, parameters, invocation) -> None:
        self._open_window()
        invocation.return_value(None)

    def _open_window(self) -> None:
        launcher = Gio.SubprocessLauncher()
        launcher.set_cwd(str(Path(__file__).resolve().parent.parent))
        process = launcher.spawnv([sys.executable, "-m", "eara", "gui"])
        process.wait_async(None, lambda child, result: child.wait_finish(result))

    def _refresh(self, mode: str | None = None) -> bool:
        if self._stopping:
            return False
        if self._busy:
            if mode is not None:
                self._pending_mode = mode
            return True
        self._busy = True

        def worker():
            status = {}
            try:
                if mode is None:
                    candidate = Device.discover(self.preferred)
                    if self.device is None or self.device.address != candidate.address:
                        self.device = candidate
                device = self.device
                if device is not None:
                    status = {"name": device.name, "bt_connected": device.connected}
                    if status["bt_connected"]:
                        if mode is not None:
                            device.set_anc(mode)
                        status = device.monitor()
            except LookupError:
                self.device = None
            except Exception as exc:
                # Background failures must not leave the indicator permanently busy
                # or present old readings as current after a disconnect.
                status["error"] = str(exc)
            GLib.idle_add(self._show, status)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _show(self, status: dict) -> bool:
        self._busy = False
        if self._stopping:
            return False
        load_lang()
        self._update_icon(status)
        visibility = "Active" if status.get("bt_connected") else "Passive"
        if self._properties["Status"].unpack() != visibility:
            self._properties["Status"] = GLib.Variant("s", visibility)
            self._bus.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, "NewStatus", GLib.Variant("(s)", (visibility,)))
            self._bus.emit_signal(
                None, ITEM_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (ITEM_INTERFACE, {"Status": self._properties["Status"]}, [])),
            )
        self._device_item.property_set("label", status.get("name") or t("status_offline"))
        lines = []
        battery = status.get("battery") or {}
        for side, key in (("left", "left"), ("right", "right"), ("case", "case_label")):
            text = f"{t(key)}: {battery_text(battery.get(side))}"
            self._battery_items[side].property_set("label", text)
            lines.append(text)
        features = status.get("model", {}).get("features", {})
        for mode, item in self._anc_items.items():
            supported = features.get("anc", False) and (mode != "adaptive" or features.get("adaptive_anc", False))
            item.property_set_bool("enabled", bool(status.get("protocol") and supported))
            item.property_set_int("toggle-state", int(status.get("anc") == mode))
        if status.get("anc"):
            lines.append(f"{t('noise')}: {t(status['anc'])}")
        if status.get("error"):
            lines.append(status["error"])
        tooltip = GLib.Variant(
            "(sa(iiay)ss)", ("audio-headphones-symbolic", [], status.get("name") or "EarA", "\n".join(lines)),
        )
        pending, self._pending_mode = self._pending_mode, None
        if pending is not None:
            self._refresh(pending)
        if self._properties["ToolTip"].equal(tooltip):
            return False
        self._properties["ToolTip"] = tooltip
        self._bus.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, "NewToolTip", None)
        self._bus.emit_signal(
            None, ITEM_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (ITEM_INTERFACE, {
                "ToolTip": self._properties["ToolTip"],
            }, [])),
        )
        return False

    def _update_icon(self, status: dict) -> None:
        svg = panel_icon(status)
        if svg == self._icon_svg:
            return
        # Different paths invalidate the host's image cache. Keep the previous
        # file available for an asynchronous load, without accumulating files.
        with NamedTemporaryFile(mode="w", suffix=".svg", dir=self._icon_dir.name, delete=False) as icon:
            icon.write(svg)
            path = Path(icon.name)
        self._icon_files.append(path)
        if len(self._icon_files) > 2:
            self._icon_files.pop(0).unlink(missing_ok=True)
        self._icon_svg = svg
        self._properties["IconName"] = GLib.Variant("s", str(path))
        self._bus.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, "NewIcon", None)
        self._bus.emit_signal(
            None, ITEM_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (ITEM_INTERFACE, {"IconName": self._properties["IconName"]}, [])),
        )

    def do_shutdown(self) -> None:
        self._stopping = True
        GLib.source_remove(self._timer)
        Gio.bus_unwatch_name(self._watcher)
        self._bus.unregister_object(self._registration)
        self._icon_dir.cleanup()
        Gio.Application.do_shutdown(self)


def run(preferred: str = "") -> int:
    try:
        gi.require_version("Dbusmenu", "0.4")
    except ValueError as exc:
        raise RuntimeError("Panel support needs libdbusmenu (Ubuntu: gir1.2-dbusmenu-glib-0.4)") from exc
    return IndicatorApp(preferred).run([])
