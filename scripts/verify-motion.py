#!/usr/bin/env python3
"""Exercise real frame-clock motion without Bluetooth, audio or persistence writes."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
from gi.repository import Gtk, Adw, GLib
from eara import gui,motion

for method in ('_bootstrap','_probe_services','_refresh_battery','_poll_services'):
    setattr(gui.EarAWindow,method,lambda *_:False)
gui._ensure_fonts=lambda:None
gui.load_lang=lambda:None
commands=[]
real_run=gui.EarAWindow._run
gui.EarAWindow._run=lambda *args,**kw:commands.append(args)
app=Adw.Application(application_id='io.github.oneydef.eara.MotionVerification')
app.register(None)
w=gui.EarAWindow(app)
w._last={'name':'Nothing Ear (a)','bt_connected':True,'protocol':True,
         'battery':{'left':{'available':True,'level':35},'right':{'available':True,'level':65}},
         'anc':'high','eq':'custom','graphic_eq':[2,1,0,-1,-2,-1,0,1],
         'latency':False,'in_ear':True,'bass':{'enabled':True,'level':2},
         'model':{'features':{'anc':True,'custom_eq':True,'bass_enhance':True,'in_ear':True,'low_latency':True,'gestures':True}},
         'audio':{'profile':'a2dp-sink'}}
w._paint();w.present()
checks={};frames=[];errors=[]
settings=Gtk.Settings.get_default();original=settings.get_property('gtk-enable-animations')
settings.set_property('gtk-enable-animations',True)
loop=GLib.MainLoop()
def later(ms,fn):
    def call():
        try:fn()
        except Exception as exc:errors.append(repr(exc))
        return False
    GLib.timeout_add(ms,call)
def sample(widget,clock):
    frames.append(clock.get_frame_time())
    return True
w.add_tick_callback(sample)
def start():
    w._reset_eq()
    w.btn_save_preset.set_state_flags(Gtk.StateFlags.ACTIVE,False)
    checks['press_geometry_before']=[w.btn_save_preset.get_width(),w.btn_save_preset.get_height()]
def midway():
    checks['eq_interpolates'] = 0 < w.eq_bands[0].get_value() < 2
    checks['native_press_without_layout'] = checks['press_geometry_before']==[w.btn_save_preset.get_width(),w.btn_save_preset.get_height()]
    w.btn_save_preset.unset_state_flags(Gtk.StateFlags.ACTIVE)
    motion.animate_eq(w,[-2]*8,user=True)
def reverse():
    checks['eq_retarget_keeps_current_position'] = -2 < w.eq_bands[0].get_value() < 2
    # A drag must stop the interpolation immediately and retain the user's value.
    motion.cancel_eq(w)
    w.eq_bands[0].set_value(3)
    checks['drag_is_immediate']=w.eq_bands[0].get_value()==3 and w._eq_motion.tick==0
    w._set_chip_active(w.anc_buttons,'off')
def selection_mid():
    group=w.anc_buttons['off'].get_parent()
    checks['selection_moves_continuously']=bool(group.motion.tick) and group.bounds[0]>0
    # Retarget before the spring settles. Sample velocity on a later frame: a
    # GLib timeout may run after the redraw is queued but before its first tick.
    w._set_chip_active(w.anc_buttons,'transparency')
def selection_velocity():
    group=w.anc_buttons['off'].get_parent()
    checks['selection_has_physical_velocity']=any(abs(state.velocity)>0 for state in group.motion.states)
def switch_start():
    sensitive=[]
    button=w.btn_music
    button.connect('notify::sensitive',lambda *_:sensitive.append(True))
    before=(button.get_can_target(),button.get_focusable())
    w._set_busy(True)
    checks['button_busy_blocks_input_without_dimming']=not button.get_can_target() and button.get_sensitive()
    w._set_busy(False)
    checks['button_completion_does_not_flash_enabled_state']=not sensitive and before==(button.get_can_target(),button.get_focusable())

    w._ignore_toggle=True
    w.lat_switch.set_active(True)
    w._ignore_toggle=False
def switch_mid():
    checks['switch_uses_native_animation']=w.lat_switch.get_active() and 'do_snapshot' not in type(w.lat_switch).__dict__
    w._ignore_toggle=True
    w.lat_switch.set_active(False)
    w._ignore_toggle=False
toggle_events=[]
toggle_writes=[]
sensitivity_events=[]
def toggle_transaction():
    w.device=object()  # The backend below is a fixture; no hardware access.
    w._run=lambda fn,**kw:real_run(w,fn,**kw)
    def write(which,value,level):
        time.sleep(.08)  # Exercise the asynchronous acknowledgement boundary.
        toggle_writes.append((which,value))
        w._last={**w._last,'latency':value}
    w._toggle=write
    for name,switch in [('device',w.dashboard_switches['lat']),('sound',w.lat_switch)]:
        switch.connect('notify::active',lambda sw,_,name=name:toggle_events.append((name,sw.get_active())))
        switch.connect('notify::sensitive',lambda *_:sensitivity_events.append(True))
    w.dashboard_switches['lat'].set_active(True)
def check_transaction():
    group=w.anc_buttons['off'].get_parent()
    checks['settled_selection_keeps_same_renderer']=not group.motion.tick and group.has_css_class('eara-motion-background')
    checks['one_toggle_write']=toggle_writes==[('lat',True)]
    checks['one_state_change_per_page']=sorted(toggle_events)==[('device',True),('sound',True)]
    checks['no_disabled_animation_during_write']=not sensitivity_events
    checks['toggle_transaction_unlocked']=not w._busy and w.lat_switch.get_can_target()
    w.device=None
    w._run=lambda *args,**kw:commands.append(args)
def reduced():
    settings.set_property('gtk-enable-animations',False)
    motion.animate_eq(w,[1]*8)
    checks['reduced_eq_immediate']=[s.get_value() for s in w.eq_bands]==[1]*8 and w._eq_motion.tick==0
    w._ignore_toggle=True;w.lat_switch.set_active(True);w._ignore_toggle=False
    checks['reduced_switch_native_state']=w.lat_switch.get_active() and w.lat_switch.get_state()
    w._show_tab('tools');w._show_tab('device');w._show_tab('sound')
    checks['rapid_navigation_final_page']=w.stack.get_visible_child_name()=='sound'
    checks['fixed_window']=(w.get_width(),w.get_height(),w.get_resizable())==(1200,720,False)
    checks['no_hardware_calls']=not commands
    checks['sidebar_width_unchanged']=round(w.buttons.compute_bounds(w)[1].get_width())==218
    checks['no_custom_press_animation']=not hasattr(w.btn_save_preset,'press')
    del checks['press_geometry_before']
def finish():
    settings.set_property('gtk-enable-animations',original)
    intervals=[(b-a)/1000 for a,b in zip(frames,frames[1:]) if b>a]
    report={'checks':checks,'errors':errors,'frame_intervals_ms':{'count':len(intervals),'median':sorted(intervals)[len(intervals)//2] if intervals else None,'max':max(intervals,default=0)},'hardware_commands':len(commands)}
    path=Path('docs/verification/motion');path.mkdir(parents=True,exist_ok=True)
    (path/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    w.destroy();loop.quit()
for ms,fn in [(500,lambda:w._show_tab('sound')),(700,start),(820,midway),(940,reverse),(1020,selection_mid),(1120,selection_velocity),(1600,switch_start),(1700,switch_mid),(1950,toggle_transaction),(2250,check_transaction),(2400,reduced),(2700,finish)]:later(ms,fn)
loop.run()
sys.exit(0 if all(checks.values()) and not errors else 1)
