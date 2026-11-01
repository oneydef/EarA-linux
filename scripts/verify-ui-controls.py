#!/usr/bin/env python3
"""Exercise actual GTK signals and persistence without Bluetooth I/O."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
from gi.repository import Adw
from eara import gui, i18n, eq_presets

gui._ensure_fonts = lambda: None
gui.load_lang = lambda: None
gui.EarAWindow._bootstrap = lambda self: False
gui.EarAWindow._probe_services = lambda self: False
gui.EarAWindow._refresh_battery = lambda self: False

def reject(*args, **kwargs):
    raise AssertionError('Unexpected hardware action')
gui.EarAWindow._run = reject
app = Adw.Application(application_id='io.github.oneydef.eara.ControlCheck')
app.register(None)
w = gui.EarAWindow(app)
w._last = {'name':'Nothing Ear (a)','bt_connected':True,'protocol':True,
           'graphic_eq':[1,-1,2,-2,3,-3,4,-4], 'eq':'custom', 'anc':'mid',
           'model':{'features':{'anc':True,'custom_eq':True,'gestures':True}}}
w._paint()
checks = {}
checks['backend_values_populate_real_scales'] = [s.get_value() for s in w.eq_bands] == w._last['graphic_eq']
checks['hidden_presets_do_not_allocate_empty_rows'] = all(
    b.get_parent().get_visible() == b.get_visible() for b in w.eq_buttons.values())
w._last['audio'] = {'profile':'headset-head-unit'}
w._paint()
checks['audio_profile_has_one_active_segment'] = (
    w.btn_calls.has_css_class('eara-chip-active')
    and not w.btn_music.has_css_class('eara-chip-active')
    and not w.btn_music.has_css_class('eara-dashboard-primary'))
w.eq_bands[0].set_value(2.5)
checks['slider_signal_marks_pending'] = w._eq_dirty and w._eq_local
w._paint()
checks['refresh_preserves_unsent_edit'] = w.eq_bands[0].get_value()==2.5
w._reset_eq()
checks['reset_moves_all_scales'] = all(s.get_value()==0 for s in w.eq_bands)
with TemporaryDirectory() as directory, patch.object(eq_presets,'_path',return_value=Path(directory)/'preset.json'):
    w.eq_bands[2].set_value(-3.5)
    w._save_eq_preset()
    w._reset_eq()
    w._load_eq_preset()
    checks['save_load_restores_real_controls'] = w.eq_bands[2].get_value()==-3.5 and w._eq_dirty
for page in ('device','sound','gestures','tools'):
    w._tab_buttons[page].emit('clicked')
    checks[f'navigation_{page}'] = w.stack.get_visible_child_name()==page
    checks[f'dark_theme_{page}'] = Adw.StyleManager.get_default().get_dark()
    checks[f'stable_device_icon_{page}'] = w._nav_icons['device'].name == 'device'
checks['footer_is_contextual'] = not w.system_strip.get_visible()
i18n.LANG='uk'
w._apply_lang()
checks['language_updates_existing_pages'] = w.gestures_title.get_text()=='Жести' and w.sound_title.get_text()==i18n.t('tab_sound')
w._last['protocol']=False
w._paint()
checks['partial_connection_disables_hardware_pages'] = w.stack.get_visible_child_name()=='device' and not w._tab_buttons['sound'].get_sensitive() and w.partial_card.get_visible()
checks['recovery_is_light'] = not Adw.StyleManager.get_default().get_dark()
checks['window_cannot_resize'] = not w.get_resizable()
checks['theme_control_removed'] = not hasattr(w, 'btn_theme')
w._set_busy(True)
checks['diagnostics_available_during_connection'] = w.btn_diagnostics.get_sensitive()
w._set_busy(False)
w._health = {'bluetooth': False, 'audio': True}
w._update_help_health()
checks['help_reflects_service_failure'] = i18n.t('health_unavailable') in w.help_status_labels[0].get_text()
w._last = {}
w._update_help_health()
checks['disconnected_controls_wait'] = i18n.t('health_waiting') in w.help_status_labels[2].get_text()
w.present()
w.advanced.emit('clicked')
checks['details_open_separate_window'] = w.details_window.get_visible() and w.details_box.get_root() == w.details_window
w.details_window.close()
report={'checks':checks,'hardware_commands_executed':0}
print(json.dumps(report,indent=2))
report_path = Path('docs/verification/audit/control-checks.json')
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report,indent=2)+'\n')
w.destroy()
sys.exit(0 if all(checks.values()) else 1)
