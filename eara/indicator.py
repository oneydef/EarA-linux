"""Battery and noise control in a StatusNotifier-compatible desktop panel.

Gio exports the small StatusNotifierItem interface; libdbusmenu handles menus.
Ubuntu's libayatana-appindicator is GTK3-only and does not expose Activate,
so it cannot provide the direct window activation needed here.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

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
  <property name="XAyatanaLabel" type="s" access="read"/>
  <property name="XAyatanaLabelGuide" type="s" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <signal name="NewToolTip"/>
  <signal name="NewStatus"><arg type="s"/></signal>
  <signal name="XAyatanaNewLabel"><arg type="s"/><arg type="s"/></signal>
</interface></node>
"""


def battery_text(item: dict | None) -> str:
    if not item or not item.get("available"):
        return "—"
    return f"{'~' if item.get('stale') else ''}{item['level']}%{'+' if item.get('charging') else ''}"


def panel_label(status: dict) -> str:
    if not status.get("bt_connected"):
        return ""
    if not status.get("protocol"):
        return "— · ANC ?"
    battery = status.get("battery") or {}
    left, right = (battery_text(battery.get(side)) for side in ("left", "right"))
    charge = left if left == right and left != "—" else f"{left}/{right}"
    anc = status.get("anc")
    noise = t(f"indicator_{anc}") if anc in ANC_MODES else "ANC ?"
    if not status.get("model", {}).get("features", {}).get("anc", True):
        return charge
    return f"{charge} · {noise}"


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
        self._properties = {
            "Id": GLib.Variant("s", "eara"),
            "Category": GLib.Variant("s", "Hardware"),
            "Title": GLib.Variant("s", "EarA"),
            "Status": GLib.Variant("s", "Passive"),
            "IconName": GLib.Variant("s", "audio-headphones-symbolic"),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", ITEM_PATH + "/Menu"),
            "XAyatanaLabel": GLib.Variant("s", "…"),
            "XAyatanaLabelGuide": GLib.Variant("s", ""),
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
        label = panel_label(status)
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
        if self._properties["XAyatanaLabel"].unpack() == label and self._properties["ToolTip"].equal(tooltip):
            return False
        self._properties["XAyatanaLabel"] = GLib.Variant("s", label)
        self._properties["ToolTip"] = tooltip
        self._bus.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, "XAyatanaNewLabel", GLib.Variant("(ss)", (label, "")))
        self._bus.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, "NewToolTip", None)
        self._bus.emit_signal(
            None, ITEM_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (ITEM_INTERFACE, {
                "XAyatanaLabel": self._properties["XAyatanaLabel"],
                "ToolTip": self._properties["ToolTip"],
            }, [])),
        )
        return False

    def do_shutdown(self) -> None:
        self._stopping = True
        GLib.source_remove(self._timer)
        Gio.bus_unwatch_name(self._watcher)
        self._bus.unregister_object(self._registration)
        Gio.Application.do_shutdown(self)


def run(preferred: str = "") -> int:
    try:
        gi.require_version("Dbusmenu", "0.4")
    except ValueError as exc:
        raise RuntimeError("Panel support needs libdbusmenu (Ubuntu: gir1.2-dbusmenu-glib-0.4)") from exc
    return IndicatorApp(preferred).run([])
