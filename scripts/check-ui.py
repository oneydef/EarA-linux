#!/usr/bin/env python3
"""Capture the real GTK frontend using explicit UI fixtures or a recorded live read.

Requires an X11 display and ImageMagick. Fixtures never invoke hardware commands.
EARA_LIVE_STATUS points to a JSON status read from Device.status(), not a fixture.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
from eara import gui, i18n

mode, output = sys.argv[1:3]
width = int(os.environ.get('EARA_TEST_WIDTH', 1200))
height = int(os.environ.get('EARA_TEST_HEIGHT', 720))
page = mode if mode in ('sound', 'gestures', 'tools') else 'device'
exit_code = 0

def reject_hardware(*_args, **_kwargs):
    raise AssertionError('Hardware action attempted by a UI fixture')

gui.EarAWindow._bootstrap = lambda self: False
gui.EarAWindow._probe_services = lambda self: False
gui.EarAWindow._refresh_battery = lambda self: False
gui.EarAWindow._run = reject_hardware
gui._ensure_fonts = lambda: None
gui.load_lang = lambda: None
i18n.LANG = os.environ.get('EARA_TEST_LANG', 'en')
app = Adw.Application(application_id='io.github.oneydef.eara.VisualCheck')


def activate(app):
    window = gui.EarAWindow(app)
    window.set_default_size(width, height)
    style = Adw.StyleManager.get_default()
    style.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT if mode in ('recovery','partial','live') else Adw.ColorScheme.FORCE_DARK)
    window._last = {
        'name':'Nothing Ear (a)', 'bt_connected':mode!='recovery',
        'protocol':mode not in ('recovery','partial'),
        'model':{'features':{'anc':True,'bass_enhance':True,'in_ear':True,'low_latency':True,'advanced_eq':False,'custom_eq':True}},
        'battery':{'left':{'available':True,'level':35},'right':{'available':True,'level':65}},
        'anc':'high','eq':'custom','in_ear':True,'latency':False,
        'bass':{'enabled':True,'level':2},'graphic_eq':[2,1,0,-1,-2.5,-2,0,1.5],
        'audio':{'profile':'a2dp-sink'},
    }
    window._health = {'bluetooth':True,'audio':True}
    source = 'explicit deterministic UI fixture; no hardware validation'
    if os.environ.get('EARA_LIVE_STATUS'):
        window._last = json.loads(Path(os.environ['EARA_LIVE_STATUS']).read_text())
        from eara.health import inspect_services
        window._health = inspect_services()
        source = 'actual Device.status() read; RFCOMM failure is preserved'
    window._device_list = [{'name':window._last.get('name','—'),'address':'00:00:00:00:00:00'}]
    window.recovery_device_drop.set_model(Gtk.StringList.new([window._last.get('name','—')]))
    window._on_recovery_device_changed()
    window._paint()
    window._show_tab(page)
    window.present()
    if mode in ('partial','recovery'):
        window.btn_connect.grab_focus()
        window.set_focus_visible(True)
    if mode == 'partial':
        # The approved concept combines an offline header with a partial warning.
        # Reproduce those independent visual states only in this explicit fixture.
        window.header_device_label.set_text(i18n.t('status_offline'))
        window.header_status.add_css_class('eara-offline-pill')
        window.header_status_arrow.set_visible(False)
        window.header_status_dot.remove_css_class('eara-dot-warn')
        window.header_status_dot.add_css_class('eara-dot-off')
        window.help_status_labels[2].set_text(i18n.t('service_controls')+' — '+i18n.t('health_waiting'))

    def capture():
        global exit_code
        try:
            from gi.repository import GdkX11
            subprocess.run(['import','-window',str(window.get_surface().get_xid()),output], check=True)
            from PIL import Image
            # GTK's surface includes CSD shadows. GTK widget size excludes them.
            im = Image.open(output)
            dx = (im.width-window.get_width())//2
            dy = (im.height-window.get_height())//2
            # On this GTK/X11 compositor upper/lower shadow insets differ by 18px.
            # Derive top inset from header allocation in the native surface.
            top = window.header.compute_bounds(window)[1].get_y()
            # Header is at client y=0; first near-opaque window row finds the shadow boundary.
            pixels = im.convert('RGB')
            bg = (244,244,242) if not style.get_dark() else (13,13,13)
            candidates = [y for y in range(max(0,dy-20),dy+20)
                          if max(abs(pixels.getpixel((im.width//2,y))[i]-bg[i]) for i in range(3)) < 5]
            dy = candidates[0] if candidates else dy
            client = im.crop((dx,dy,dx+window.get_width(),dy+window.get_height()))
            client.save(str(Path(output).with_suffix('.client.png')))
            regions = {'navigation':window.buttons,'content':window.stack,'device_card':window.status_card,
                       'header':window.header, **window._ui_regions}
            geometry = {}
            for name, widget in regions.items():
                ok, bounds = widget.compute_bounds(window)
                if ok and widget.get_mapped():
                    geometry[name] = [round(bounds.get_x(),2),round(bounds.get_y(),2),
                                      round(bounds.get_width(),2),round(bounds.get_height(),2)]
            adjustment = window.stack.get_visible_child().get_vadjustment()
            scroll_range = max(0, adjustment.get_upper()-adjustment.get_page_size())
            checks = {
                'requested_width':window.get_width()==width,
                'fixed_size':not window.get_resizable() and window.get_height()==height,
                'page_theme':style.get_dark() == (mode not in ('recovery','partial','live')),
                'no_vertical_scroll':scroll_range <= 1,
                'navigation_order':list(window._tab_buttons)==['device','sound','gestures','tools'],
                'selected_page':window.stack.get_visible_child_name()==page,
                'partial_warning':window.partial_card.get_visible()==bool(window._last.get('bt_connected') and not window._last.get('protocol')),
                'rail_width': abs(geometry['navigation'][2]-218)<=2,
                'horizontal_bounds':all(x>=-1 and x+w<=window.get_width()+1 for x,y,w,h in geometry.values()),
            }
            if mode=='sound':
                ok, action_bounds = window.btn_save_preset.compute_bounds(window)
                checks['eq_actions_reachable'] = bool(ok and action_bounds.get_y()+action_bounds.get_height()-scroll_range<window.get_height())
            if mode=='sound' and width>=1280 and height>=760:
                ok, bounds = window.btn_save_preset.compute_bounds(window)
                checks['eq_actions_in_view'] = bool(ok and bounds.get_y()+bounds.get_height()<window.get_height()-8)
            font = window.lbl_eq_title.get_pango_context().load_font(window.lbl_eq_title.get_pango_context().get_font_description())
            report = {'mode':mode,'source':source,'language':i18n.LANG,'viewport':[window.get_width(),window.get_height()],
                      'native_capture_crop':[dx,dy,window.get_width(),window.get_height()],
                      'font_loaded':font.describe().to_string(),'vertical_scroll_range':scroll_range,'checks':checks,'geometry':geometry,
                      'pixel_identity':'not claimed; see aligned overlays and component geometry'}
            Path(output+'.checks.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report), flush=True)
            exit_code = int(not all(checks.values()))
        except Exception:
            import traceback
            traceback.print_exc()
            exit_code=1
        app.quit()
        return False
    GLib.timeout_add(1000,capture)

app.connect('activate',activate)
app.run([])
sys.exit(exit_code)
