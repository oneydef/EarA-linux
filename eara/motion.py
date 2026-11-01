"""Native GTK motion. Snapshot effects never change widget allocations.

All frame callbacks stop on completion/unmap. No animation sends device commands.
The GTK enable-animations preference is the native reduced-motion control.
"""
import math
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gtk, Gdk, Graphene, GLib
from eara.motion_physics import Spring, smooth, INSTANT, FAST, NORMAL, SLOW, AMBIENT


def enabled(widget):
    settings = widget.get_settings()
    return bool(settings and settings.get_property('gtk-enable-animations'))


def point(x, y):
    return Graphene.Point().init(x, y)


def rect(w, h):
    return Graphene.Rect().init(0, 0, max(1,w), max(1,h))


def rounded(cr, x, y, w, h, radius):
    r = min(radius, w/2, h/2)
    for cx, cy, start in ((x+w-r,y+r,-math.pi/2),(x+w-r,y+h-r,0),
                           (x+r,y+h-r,math.pi/2),(x+r,y+r,math.pi)):
        cr.arc(cx,cy,r,start,start+math.pi/2)
    cr.close_path()


class Motion:
    def __init__(self, widget, values, update, spring=False, duration=NORMAL):
        self.widget, self.update, self.spring, self.duration = widget, update, spring, duration
        self.values = list(values)
        self.targets = list(values)
        self.states = [Spring(v, target=v) for v in values]
        self.tick = 0
        widget.connect('unmap', lambda *_: self.finish())

    def to(self, values, immediate=False):
        values = list(values)
        if values == self.targets and not immediate:
            return
        self.targets = values
        if immediate or not enabled(self.widget) or not self.widget.get_mapped():
            self.finish()
            return
        self.starts = self.values[:]
        self.start = self.last = time.monotonic()
        for state, target in zip(self.states, values):
            state.target = target
        if not self.tick:
            self.tick = self.widget.add_tick_callback(self._frame)

    def finish(self):
        if self.tick:
            self.widget.remove_tick_callback(self.tick)
            self.tick = 0
        self.values = self.targets[:]
        for state, value in zip(self.states, self.values):
            state.value, state.target, state.velocity = value, value, 0.0
        self.update(self.values)

    def _frame(self, widget, clock):
        now = time.monotonic()
        if not enabled(widget):
            self.tick = 0
            self.finish()
            return False
        if self.spring:
            self.values = [s.step(now-self.last) for s in self.states]
            done = all(s.value == s.target and s.velocity == 0 for s in self.states)
        else:
            t = min(1, (now-self.start)*1000/self.duration)
            self.values = [a+(b-a)*smooth(t) for a,b in zip(self.starts,self.targets)]
            done = t == 1
        self.last = now
        self.update(self.values)
        if done:
            self.tick = 0
        return not done


class MotionButton(Gtk.Button):
    __gtype_name__ = 'EarAMotionButton'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.feedback = None
        self.feedback_tick = 0
        self.connect('clicked', self._clicked)
        self.connect('unmap', self._stop_feedback)
        self.connect('map', self._resume_feedback)
        self.add_css_class('eara-motion-button')

    def _resume_feedback(self, *_):
        if self.feedback == 'ringing' and enabled(self) and not self.feedback_tick:
            self.feedback_tick=self.add_tick_callback(self._feedback_frame)

    def _clicked(self, *_):
        root = self.get_root()
        if root:
            root._motion_action = self

    def set_feedback(self, state):
        state = state if state in ("error", "ringing") else None
        self.feedback, self.feedback_start = state, time.monotonic()
        self.queue_draw()
        if state == "error":
            started=self.feedback_start
            def clear():
                if self.feedback_start == started:
                    self.feedback=None;self.queue_draw()
                return False
            GLib.timeout_add(850,clear)
        if state and enabled(self) and not self.feedback_tick and self.get_mapped():
            self.feedback_tick = self.add_tick_callback(self._feedback_frame)

    def _stop_feedback(self, *_):
        if self.feedback_tick:
            self.remove_tick_callback(self.feedback_tick)
            self.feedback_tick = 0

    def _feedback_frame(self, *_):
        if not enabled(self):
            self.feedback_tick=0
            return False
        if self.feedback != 'ringing' and time.monotonic()-self.feedback_start > .85:
            self.feedback = None
        if not self.feedback:
            self.feedback_tick = 0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def do_snapshot(self, snapshot):
        w,h = self.get_width(),self.get_height()
        snapshot.save()
        if self.feedback == "error" and enabled(self):
            elapsed=time.monotonic()-self.feedback_start
            snapshot.translate(point(2*math.sin(elapsed*45)*math.exp(-elapsed*8),0))
        Gtk.Button.do_snapshot(self,snapshot)
        snapshot.restore()
        if self.feedback:
            cr = snapshot.append_cairo(rect(w,h))
            cr.set_line_width(1.7)
            color=self.get_style_context().get_color()
            cr.set_source_rgba(color.red,color.green,color.blue,.9)
            t=time.monotonic()-self.feedback_start
            if self.feedback == 'error':
                cr.set_source_rgba(.9,.07,.12,.9)
                rounded(cr,1,1,w-2,h-2,14);cr.stroke()
            elif self.feedback == 'ringing':
                for offset in (0,.5):
                    phase=(t/1.5+offset)%1 if enabled(self) else .5
                    cr.set_source_rgba(.9,.07,.12,1-phase)
                    cr.arc(w/2,h/2,6+phase*min(w,h)*.45,0,math.tau);cr.stroke()


class SelectionBox(Gtk.Box):
    __gtype_name__ = 'EarASelectionBox'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selection = None
        self.bounds = None
        self.motion = Motion(self,[0,0,0,0],self._move,spring=True)
        self.add_css_class('eara-motion-selection')

    def _move(self, values):
        self.bounds = values
        self.queue_draw()

    def do_snapshot(self, snapshot):
        def buttons(widget):
            child = widget.get_first_child()
            while child:
                if isinstance(child,Gtk.Button):
                    yield child
                elif isinstance(child,Gtk.Revealer):
                    yield from buttons(child)
                child=child.get_next_sibling()
        active = next((b for b in buttons(self) if b.get_visible() and
                       (b.has_css_class('eara-chip-active') or b.has_css_class('eara-tab-active')
                        or b.has_css_class('eara-dashboard-primary'))),None)
        if active:
            ok,b=active.compute_bounds(self)
            if ok and b.get_width()>0 and b.get_height()>0:
                target=[b.get_x(),b.get_y(),b.get_width(),b.get_height()]
                self.motion.to(target,immediate=self.selection is None)
                self.selection=active
                # Use the same background renderer while moving and at rest.
                # Handing back to CSS changed gradient, border and geometry on
                # the final frame, producing a flash even with transitions off.
                self.add_css_class("eara-motion-background")
                x,y,w,h=self.bounds
                cr=snapshot.append_cairo(rect(self.get_width(),self.get_height()))
                rounded(cr,x+1,y+1,max(1,w-2),max(1,h-2),15 if self.has_css_class('eara-buttons') else 17)
                if self.has_css_class('eara-buttons'):
                    from gi.repository import Adw
                    dark=Adw.StyleManager.get_default().get_dark()
                    cr.set_source_rgb(*((.106,.078,.082) if dark else (.894,.894,.89)))
                    cr.fill_preserve()
                    if dark:
                        cr.set_source_rgb(1,.04,.1);cr.set_line_width(1);cr.stroke()
                else:
                    import cairo
                    gradient=cairo.LinearGradient(x,y,x+w*.2,y+h)
                    gradient.add_color_stop_rgb(0,.875,.047,.106)
                    gradient.add_color_stop_rgb(1,.78,.059,.102)
                    cr.set_source(gradient);cr.fill()
        else:
            self.selection=None
            self.remove_css_class("eara-motion-background")
        Gtk.Box.do_snapshot(self,snapshot)


class MotionSwitch(Gtk.Switch):
    __gtype_name__ = 'EarAMotionSwitch'
    # GtkSwitch already animates its thumb. A second snapshot animation
    # hands back to GTK at a different position and produces a visible replay.
    # Keep one owner of rendering, input, and reduced-motion behavior: GTK.


class MotionStack(Gtk.Stack):
    __gtype_name__ = 'EarAMotionStack'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.set_transition_duration(NORMAL)
        self.offset=0
        self.motion=Motion(self,[0],self._move,duration=NORMAL)
        self.connect('notify::visible-child',self._changed)

    def _move(self, values):
        self.offset=values[0];self.queue_draw()

    def _changed(self,*_):
        if self.get_mapped() and enabled(self):
            self.motion.values=[6.0]
            self.motion.targets=[6.0]
            self.motion.to([0.0])

    def do_snapshot(self,snapshot):
        snapshot.save();snapshot.translate(point(0,self.offset))
        Gtk.Stack.do_snapshot(self,snapshot)
        snapshot.restore()


def animate_eq(window, gains, *, user=False):
    """One animation for all bands. Intermediate values never trigger hardware writes."""
    values=[max(-6,min(6,float(g))) for g in gains]
    if not hasattr(window,'_eq_motion'):
        def update(current):
            window._eq_syncing=True
            try:
                for scale,value in zip(window.eq_bands,current):
                    scale.set_value(value)
            finally:
                window._eq_syncing=False
        window._eq_motion=Motion(window.graphic_box,[s.get_value() for s in window.eq_bands],update,duration=SLOW)
    window._eq_target_gains=values
    window._eq_motion.to(values)
    if user:
        window._eq_local=True
        window._set_eq_dirty(True)


def cancel_eq(window):
    if hasattr(window,'_eq_motion'):
        motion=window._eq_motion
        # Stop at the current displayed values, without jumping under the pointer.
        motion.targets=[s.get_value() for s in window.eq_bands]
        motion.finish()
    window._eq_target_gains=None


def bind_slider(window,scale):
    gesture=Gtk.GestureClick()
    gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    gesture.connect('pressed',lambda *_: cancel_eq(window))
    scale.add_controller(gesture)


def css(reduced=False):
    fast=0 if reduced else FAST
    ambient = "none" if reduced else f"eara-connected {AMBIENT}ms ease-in-out infinite"
    connecting = "none" if reduced else "eara-connected 900ms ease-in-out infinite"
    return f'''
@keyframes eara-connected {{ 0% {{ opacity: 1; }} 50% {{ opacity: .65; }} 100% {{ opacity: 1; }} }}
.eara-status-dot.eara-dot-ok {{ animation: {ambient}; }}
.eara-status-dot.eara-dot-connecting {{ animation: {connecting}; }}
.eara-motion-button {{ transition: none; }}
/* SelectionBox owns the selected background in every frame, including rest. */
.eara-motion-selection button.eara-motion-button {{ transition: none; }}
.eara-motion-selection.eara-motion-background button.eara-chip-active,
.eara-motion-selection.eara-motion-background button.eara-dashboard-primary,
.eara-motion-selection.eara-motion-background button.eara-tab-active {{ background: transparent; border-color: transparent; }}
.eara-content .eara-motion-selection.eara-motion-background button.eara-chip-active,
.eara-content .eara-motion-selection.eara-motion-background button.eara-dashboard-primary {{ background: transparent; border-color: transparent; }}
switch.eara-switch {{ transition: background-color {fast}ms ease-out; }}
.eara-content scale slider {{ transition: box-shadow {fast}ms ease-out; }}
.eara-content scale:hover slider {{ box-shadow: 0 0 0 1px alpha(currentColor,.22); }}
.eara-content scale:active slider {{ box-shadow: 0 0 0 2px alpha(currentColor,.3); }}
'''

class MotionScale(Gtk.Scale):
    __gtype_name__ = 'EarAMotionScale'
    # Keep GTK's native drag handling; transient text painted in snapshots
    # could remain visible when GTK claimed the pointer gesture.


def motion_scale(orientation, minimum, maximum, step):
    return MotionScale(orientation=orientation,adjustment=Gtk.Adjustment(
        lower=minimum,upper=maximum,step_increment=step,page_increment=step*10))


class GestureLabel(Gtk.Label):
    __gtype_name__='EarAGestureLabel'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.preview_tick=0
        self.kind=''
        self.connect('unmap',self.stop)
        hover=Gtk.EventControllerMotion()
        hover.connect('enter',lambda *_:self.preview())
        self.add_controller(hover)

    def stop(self,*_):
        if self.preview_tick:
            self.remove_tick_callback(self.preview_tick);self.preview_tick=0

    def preview(self):
        if not enabled(self) or not self.get_mapped():
            return
        self.preview_start=time.monotonic()
        if not self.preview_tick:
            self.preview_tick=self.add_tick_callback(self._frame)

    def _frame(self,*_):
        if not enabled(self) or time.monotonic()-self.preview_start>1.5:
            self.preview_tick=0;self.queue_draw();return False
        self.queue_draw();return True

    def do_snapshot(self,snapshot):
        Gtk.Label.do_snapshot(self,snapshot)
        if self.preview_tick:
            cr=snapshot.append_cairo(rect(self.get_width(),self.get_height()))
            t=time.monotonic()-self.preview_start
            count=3 if 'triple' in self.kind else 2 if 'double' in self.kind else 1
            cr.set_source_rgba(.875,.047,.106,.85);cr.set_line_width(1.5)
            x,y=self.get_width()-7,self.get_height()/2
            if t < count*.23:
                radius=2+4*math.sin((t%.23)/.23*math.pi)
                cr.arc(x,y,radius,0,math.tau);cr.stroke()
            elif 'hold' in self.kind:
                amount=min(1,(t-count*.23)/.65)
                cr.arc(x,y,5,-math.pi/2,-math.pi/2+math.tau*amount);cr.stroke()


def battery(cell, level):
    if 'motion' not in cell:
        def update(values):
            value=values[0]
            cell['pct'].set_text(f'{round(value)}%')
            cell['bar'].set_fraction(max(0,min(1,value/100)))
        cell['motion']=Motion(cell['bar'],[level],update,duration=SLOW)
        cell['motion'].to([level],immediate=True)
    else:
        cell['motion'].to([level])


def reveal(widget):
    if not hasattr(widget, '_reveal_motion'):
        widget._reveal_motion=Motion(widget,[1.0],lambda values:widget.set_opacity(values[0]),duration=NORMAL)
    if enabled(widget) and widget.get_mapped():
        widget._reveal_motion.values=[.5]
        widget._reveal_motion.targets=[.5]
    widget._reveal_motion.to([1.0])


def bind_gesture(widget, label):
    focus=Gtk.EventControllerFocus()
    focus.connect('enter',lambda *_:label.preview())
    widget.add_controller(focus)
    click=Gtk.GestureClick()
    click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    click.connect('pressed',lambda *_:label.preview())
    widget.add_controller(click)
