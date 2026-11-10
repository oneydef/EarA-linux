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
checks={};frames=[];errors=[];geometry=[]
settings=Gtk.Settings.get_default();original=settings.get_property('gtk-enable-animations')
settings.set_property('gtk-enable-animations',True)
loop=GLib.MainLoop()
def start():
    w._reset_eq()
    checks['press_geometry_before']=[w.btn_save_preset.get_width(),w.btn_save_preset.get_height()]
    w.btn_save_preset.set_state_flags(Gtk.StateFlags.ACTIVE,False)
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
    # GTK versions account for CSD borders/shadows differently. Verify the
    # requested fixed size and that the allocated content stayed unchanged.
    checks['fixed_window']=(tuple(w.get_default_size())==(1200,720) and
                            tuple(w.get_size_request())==(1200,720) and
                            not w.get_resizable() and
                            [w.get_width(),w.get_height()]==geometry[-1][:2])
    checks['no_hardware_calls']=not commands
    checks['sidebar_width_unchanged']=round(w.buttons.compute_bounds(w)[1].get_width())==218
    checks['no_custom_press_animation']=not hasattr(w.btn_save_preset,'press')
    del checks['press_geometry_before']
def finish():
    settings.set_property('gtk-enable-animations',original)
    intervals=[(b-a)/1000 for a,b in zip(frames,frames[1:]) if b>a]
    report={'checks':checks,'errors':errors,'geometry_samples':geometry,'frame_intervals_ms':{'count':len(intervals),'median':sorted(intervals)[len(intervals)//2] if intervals else None,'max':max(intervals,default=0)},'hardware_commands':len(commands),
            'toggle_state':{'writes':toggle_writes,'events':toggle_events,'busy':w._busy}}
    path=Path('docs/verification/motion');path.mkdir(parents=True,exist_ok=True)
    (path/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    w.destroy();loop.quit()
w._show_tab('sound')
def stable_allocation():
    sizes=[w.get_width(),w.get_height(),w.btn_save_preset.get_width(),w.btn_save_preset.get_height()]
    geometry.append(sizes)
    return (w.btn_save_preset.get_mapped() and min(sizes)>0 and
            len(geometry)>=6 and all(g==sizes for g in geometry[-6:]) and
            not w.stack.get_transition_running())
def group():
    return w.anc_buttons['off'].get_parent()
steps=[
    ('stable_allocation',stable_allocation,start),
    ('eq_interpolation',lambda:0<w.eq_bands[0].get_value()<2,midway),
    ('eq_retarget',lambda:-2<w.eq_bands[0].get_value()<0,reverse),
    ('selection_motion',lambda:bool(group().motion.tick) and bool(group().bounds) and group().bounds[0]>0,selection_mid),
    ('selection_velocity',lambda:any(abs(s.velocity)>0 for s in group().motion.states),selection_velocity),
    ('selection_settle',lambda:not group().motion.tick,switch_start),
    ('switch_native',lambda:w.lat_switch.get_active(),switch_mid),
    ('toggle_begin',lambda:not w.lat_switch.get_active(),toggle_transaction),
    ('toggle_complete',lambda:bool(toggle_writes) and not w._busy,check_transaction),
    ('reduced_motion',lambda:True,reduced),
    ('finish',lambda:True,finish),
]
step_started=time.monotonic()
def await_worker():
    """Leave the frame clock idle so GTK's idle completion can be dispatched.

    A permanent tick callback forces software-rendered frames even though this
    stage tests worker acknowledgement, not animation. On slow GTK/Xvfb that
    can starve the lower-priority idle callback which unlocks the transaction.
    """
    global step_started
    name,ready,action=steps[0]
    try:
        if ready():
            steps.pop(0)
            action()
            step_started=time.monotonic()
            w.add_tick_callback(sample)
            return False
        if time.monotonic()-step_started>5:
            raise TimeoutError('Worker condition not reached: '+name)
    except Exception as exc:
        errors.append(repr(exc))
        finish()
        return False
    return True

def sample(widget,clock):
    global step_started
    frames.append(clock.get_frame_time())
    if not steps:
        return False
    name,ready,action=steps[0]
    try:
        if ready():
            steps.pop(0)
            action()
            step_started=time.monotonic()
            if steps and steps[0][0]=='toggle_complete':
                GLib.timeout_add(16,await_worker)
                return False
        elif time.monotonic()-step_started>5:
            raise TimeoutError('Frame condition not reached: '+name)
    except Exception as exc:
        errors.append(repr(exc))
        finish()
        return False
    return bool(steps)
def watchdog():
    errors.append('No frame-clock progress before global watchdog')
    finish()
    return False
w.add_tick_callback(sample)
GLib.timeout_add_seconds(30,watchdog)
loop.run()
sys.exit(0 if all(checks.values()) and not errors else 1)
