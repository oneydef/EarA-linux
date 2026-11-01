"""Shared geometry, theme palette and scalable line icons for the GTK UI."""
import math
import re


def draw_icon(widget, cr, width, height, name):
    color = widget.get_style_context().get_color()
    cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
    cr.scale(width / 32, height / 32)
    cr.set_line_width(1.8)
    cr.set_line_cap(1)
    cr.set_line_join(1)
    def line(points):
        cr.move_to(*points[0])
        for point in points[1:]:
            cr.line_to(*point)
        cr.stroke()
    if name == 'warning':
        cr.arc(16,16,12,0,math.tau);cr.fill()
        cr.set_source_rgb(1,1,1)
        line([(16,8),(16,17)])
        cr.arc(16,23,1,0,math.tau);cr.fill()
    elif name == 'help':
        cr.arc(16,16,10,0,math.tau);cr.stroke()
        cr.move_to(12,12);cr.curve_to(12,6,23,9,18,15)
        cr.line_to(16,18);cr.stroke()
        cr.arc(16,22,1,0,math.tau);cr.fill()
    elif name == 'sun':
        cr.arc(16,16,5,0,math.tau);cr.stroke()
        for angle in range(8):
            a=angle*math.pi/4
            line([(16+9*math.cos(a),16+9*math.sin(a)),(16+12*math.cos(a),16+12*math.sin(a))])
    elif name == 'device':
        for x,y in ((5,5),(19,5),(5,19),(19,19)):
            cr.rectangle(x,y,8,8)
        cr.stroke()
    elif name == 'reset':
        cr.arc(16,16,10,-2.3,2.5); cr.stroke()
        line([(5,5),(5,13),(13,13)])
    elif name == 'save':
        line([(5,4),(24,4),(28,8),(28,28),(5,28),(5,4)])
        cr.rectangle(10,4,12,9);cr.rectangle(10,20,13,8);cr.stroke()
    elif name == 'info':
        cr.arc(16,16,12,0,math.tau);cr.stroke()
        line([(16,14),(16,23)])
        cr.arc(16,9,1,0,math.tau);cr.fill()
    elif name == 'dots':
        for x in (10,16,22):
            for y in (6,12,18,24):
                cr.arc(x,y,1,0,math.tau);cr.fill()
    elif name in ('sound','high','bass'):
        for x,h in ((5,6),(10,14),(16,24),(22,16),(27,8)):
            line([(x,16-h/2),(x,16+h/2)])
    elif name == 'gestures':
        line([(9,26),(4,17),(5,14),(8,15),(11,19),(11,6),(13,4),(15,6),(15,16),(15,3),(17,2),(19,4),(19,16),(19,6),(21,5),(23,7),(23,18),(23,11),(25,10),(27,12),(27,23),(23,29),(15,30),(9,26)])
    elif name == 'tools':
        line([(20,3),(16,6),(15,11),(4,23),(4,27),(7,29),(10,28),(22,16),(27,15),(30,10),(24,12),(21,9),(23,3),(20,3)])
    elif name in ('off','transparency'):
        if name == 'transparency': cr.set_dash([1,5])
        cr.arc(16,16,11,0,2*math.pi);cr.stroke();cr.set_dash([])
        if name == 'off': line([(5,27),(27,5)])
    elif name == 'music':
        line([(13,23),(13,7),(26,4),(26,20)])
        for x,y in ((9,24),(22,21)):
            cr.arc(x,y,4,0,2*math.pi);cr.fill()
    elif name == 'calls':
        line([(8,3),(3,7),(5,15),(12,23),(23,29),(28,25),(23,19),(19,22),(11,14),(13,10),(8,3)])
    elif name == 'lat':
        line([(18,2),(7,18),(16,18),(13,30),(26,13),(17,13),(18,2)])
    elif name == 'ied':
        cr.arc(17,12,9,math.pi,2*math.pi);cr.stroke()
        line([(26,12),(25,18),(20,21),(18,27),(14,29),(10,27)])
        cr.arc(17,12,4,math.pi,2*math.pi);cr.stroke()
        line([(21,12),(18,17),(14,17)])


# Keep the Device navigation geometry on every page.
# Device window reference: top cards 386px, lower cards 272px -> 333/235px at 1280.
GEOMETRY = dict(rail=218, header=64, footer=36, gap=14, inset=16, card_padding=22, radius=17)
PALETTES = {
    True: dict(bg='#0d0d0c', rail='#101010', header='#0d0d0d', card='#161817', card_end='#141414',
               text='#f4f4f4', muted='#969699', line='#303030', control='#1c1c1c',
               active_nav='#1b1415', disabled='#737373'),
    False: dict(bg='#f5f4f2', rail='#f3f3f0', header='#f4f4f2', card='#fdfdfc', card_end='#ffffff',
                text='#0b0b12', muted='#626269', line='#dcdcdc', control='#efefed',
                active_nav='#e4e4e3', disabled='#838386'),
}


def build_css(dot_font, ui_font, dark):
    p = PALETTES[dark]
    css = '''
window.eara-window { background: $bg; color: $text; font-family: "$font"; }
.eara-stack { background: $bg; }
headerbar { min-height: $header_height; padding: 0 24px; background: $header; color: $text; border-bottom: 1px solid $line; }
headerbar separator { min-width: 1px; background: $line; margin: 18px 20px; }
.eara-header-title { font-size: 40px; letter-spacing: 2px; min-width: 100px; }
headerbar button.eara-header-selector { background: transparent; border: none; }
.eara-header-device { padding: 0 4px; }
.eara-header-device label { font-size: 16px; font-weight: 400; }
headerbar button, headerbar menubutton > button { color: $text; min-width: 32px; min-height: 32px; border-radius: 11px; padding: 4px; margin: 0 5px; }
headerbar button.flat { background: $card; border: 1px solid $line; }
windowcontrols button { background: transparent; border: none; min-width: 24px; min-height: 24px; padding: 0; margin: 0 5px; color: $text; }
windowcontrols button image { color: $text; background: transparent; }
.eara-status-dot { min-width: 12px; min-height: 12px; border-radius: 99px; background: #929292; }
.eara-dot-ok { background: #2bca49; }
.eara-dot-warn { background: #e7a123; }
.eara-buttons { background: $rail; border-right: 1px solid $line; padding: 22px 7px; }
button.eara-tab { padding: 0 10px; min-height: 58px; border: 1px solid transparent; border-radius: 15px; background: transparent; color: $text; box-shadow: none; }
button.eara-tab:hover { background: $control; }
button.eara-tab.eara-tab-active { background: $active_nav; border-color: #ed1726; }
button.eara-tab:disabled { color: $disabled; opacity: 1; }
button.eara-tab:disabled image, button.eara-tab:disabled label { opacity: 1; color: $disabled; }
.eara-tab-label { font-size: 18px; font-weight: 500; }
.eara-tab-icon { min-width: 24px; min-height: 24px; }
.eara-content { font-family: "$font"; font-size: 15px; color: $text; }
.eara-content button { font-family: "$font"; font-size: 14px; font-weight: 400; color: $text; padding: 8px 16px; min-height: 26px; border: 1px solid $line; border-radius: 15px; background: $control; box-shadow: none; }
.eara-content button:disabled { opacity: .45; }
.eara-card, .eara-status-card { border: 1px solid $line; border-radius: $card_radius; padding: $card_padding; background: linear-gradient(130deg, $card, $card_end); }
.eara-dashboard .eara-status-card, .eara-dashboard > grid:first-child > .eara-card { min-height: 288px; }
.eara-dashboard > grid:last-child > .eara-card { min-height: 189px; }
.eara-dashboard-title { font-size: 22px; font-weight: 650; margin-bottom: 12px; }
.eara-card-title { font-size: 20px; font-weight: 650; }
.eara-page-title { font-size: 36px; font-weight: 800; }
.dim-label { color: $muted; font-size: 16px; opacity: 1; }
.eara-status-name { font-size: 27px; min-width: 220px; margin-bottom: 6px; }
.eara-device-art { min-width: 180px; min-height: 260px; }
.eara-status-badge { font-size: 16px; padding: 5px 10px; border-radius: 16px; }
.eara-status-badge-ok { background: #102c14; border: 1px solid #235b29; color: #e2ffe6; }
.eara-status-badge + .eara-status-badge { background: transparent; border: none; color: $muted; padding: 4px 0; }
.eara-status-meta { font-size: 0; }
.eara-status-batteries { margin-top: 14px; }
separator { background: $line; min-height: 1px; }
.eara-status-head separator { margin-top: 16px; }
.eara-batt-cell { padding: 8px; border-right: 1px solid $line; }
.eara-batt-cell:last-child { border: none; }
.eara-batt-side { font-size: 16px; }
.eara-batt-pct { font-size: 30px; font-weight: 750; }
progressbar.eara-batt-bar trough { min-width: 36px; min-height: 10px; padding: 2px; border: 1px solid #aaaaaa; border-radius: 2px; background: #292929; }
progressbar.eara-batt-bar progress { background: #2bca49; border-radius: 0; min-height: 10px; }
progressbar.eara-batt-low progress { background: #e61a25; }
.eara-battery-terminal { min-width: 3px; min-height: 7px; background: #aaaaaa; border-radius: 0 2px 2px 0; }
.eara-segmented { border: 1px solid $line; border-radius: 18px; background: transparent; }
.eara-content button.eara-segment { background: transparent; border: none; border-right: 1px solid alpha($text,.05); border-radius: 0; min-height: 76px; padding: 10px 6px; font-size: 16px; font-weight: 400; }
/* Pointer hover must not outline individual segments. Keyboard focus
   retains the shared :focus-visible indicator. */
.eara-content button.eara-segment:hover { box-shadow: none; }
.eara-content button.eara-segment:hover:not(.eara-chip-active):not(.eara-dashboard-primary) { background: transparent; }
.eara-content button.eara-segment:first-child { border-radius: 17px 0 0 17px; }
.eara-content button.eara-segment:last-child { border-radius: 0 17px 17px 0; border: none; }
.eara-content .eara-strength button.eara-segment { min-height: 32px; }
.eara-device-noise > .eara-segmented:not(.eara-strength) button.eara-segment { min-height: 96px; font-size: 14px; }
.eara-device-noise > separator { margin: 12px 0; }
.eara-content button.eara-segment.eara-chip-active, .eara-content button.eara-chip-active, .eara-content button.eara-dashboard-primary { background: linear-gradient(170deg, #df0c1b, #c70f1a); color: #ffffff; border-color: #ed1726; border-radius: 17px; }
.eara-toggle-row { padding: 11px 0; border-bottom: 1px solid $line; }
.eara-toggle-row:last-child { border: none; }
.eara-quick-card .eara-toggle-row { padding: 11px 0; }
.eara-quick-card { padding-bottom: 8px; }
.eara-toggle-label { font-size: 16px; }
.eara-recovery-main > .dim-label { color: $muted; font-size: 18px; }
switch.eara-switch { min-width: 58px; min-height: 28px; padding: 1px; border: 1px solid #505050; border-radius: 99px; background: #333333; }
switch.eara-switch slider { min-width: 24px; min-height: 24px; margin: 1px; background: #eeeeee; border: none; border-radius: 99px; }
switch.eara-switch:checked { background: #df0c1b; border-color: #df0c1b; }
switch.eara-switch:disabled { opacity: .45; }
.eara-sound-page .eara-card { padding: 16px; }
.eara-sound-page .eara-toggle-row { padding: 8px 0; }
.eara-sound-page flowboxchild { min-width: 0; padding: 0; }
.eara-sound-page flowbox { padding: 0; }
.eara-sound-page flowbox button { padding-left: 8px; padding-right: 8px; }
.eara-sound-page .eara-card-title { font-size: 18px; margin-bottom: 14px; }
.eara-sound-subtitle { font-size: 18px; }
.eara-sound-page .eara-noise-label { font-size: 18px; margin-bottom: 14px; }
.eara-listening-card .eara-card-title { margin-bottom: 0; }
.eara-panel { margin-top: 12px; padding: 0; }
.eara-content scale.vertical { padding: 8px 0; min-width: 10px; }
.eara-content scale.vertical trough { background: #393939; min-width: 4px; border-radius: 2px; }
.eara-content scale.vertical highlight { background: #df0c1b; min-width: 4px; border-radius: 2px; }
.eara-content scale.vertical slider { background: #df0c1b; min-width: 8px; min-height: 8px; border: 4px solid #ffffff; border-radius: 99px; box-shadow: none; }
.eara-eq-frequency { font-size: 13px; color: $muted; margin-top: 4px; }
.eara-content .eara-compact-segments button.eara-segment { min-height: 34px; font-size: 12px; padding: 8px 2px; }
.eara-noise-label { font-size: 20px; font-weight: 650; }
.eara-content dropdown > button { border-radius: 12px; min-height: 26px; background: $control; color: $text; }
.eara-content dropdown label { color: $text; }
.eara-eq-footer, .eara-sound-page .eara-eq-footer { padding: 10px; }
.eara-eq-hint { color: $muted; font-size: 16px; }
.eara-content button.eara-save-preset { background: #df0c1b; color: #ffffff; }
.eara-advanced { margin-top: 8px; font-size: 13px; color: $muted; }
.eara-system-strip { min-height: $footer_height; padding: 0 24px; border-top: 1px solid $line; background: $rail; color: $muted; }
.eara-system-strip separator { margin: 10px 6px; min-width: 1px; }
.eara-system-item { font-size: 13px; }
.eara-system-strip button { background: transparent; color: $muted; box-shadow: none; }
.eara-recovery-main { padding: 8px 0; }
.eara-recovery-title { font-size: 40px; font-weight: 800; }
.eara-recovery-device { background: $card; border: 1px solid $line; border-radius: 16px; padding: 18px; margin-top: 12px; }
.eara-recovery-device .eara-card-title, .eara-recovery-main > .eara-card-title { font-size: 12px; letter-spacing: 2px; color: $muted; }
.eara-recovery-step { padding: 10px 4px; }
.eara-recovery-step-art { min-width: 90px; min-height: 100px; }
.eara-connection-help { font-size: 18px; }
.eara-connection-help .eara-dashboard-title { font-size: 20px; }
.eara-connection-help > box { min-height: 32px; }
.eara-connection-help > separator { margin: 12px 0; }
.eara-connection-help expander { background: $control; padding: 14px 10px; border-radius: 10px; margin-bottom: 6px; }
.eara-connection-help > button { min-height: 38px; }
.eara-partial-card > box { min-height: 60px; }
.eara-partial-card { font-size: 16px; }
.eara-help-dot { min-width: 12px; min-height: 12px; border-radius: 99px; }
.eara-help-dot-ok { background: #168144; }
.eara-help-dot-wait { background: #929292; }
.eara-partial-card { background: #301010; border-color: #633030; }
.eara-gesture-side { font-size: 20px; font-weight: 650; }
.eara-gesture-row { padding: 6px 0; border-bottom: 1px solid $line; }
.eara-gesture-row:last-child { border: none; }
.eara-gesture-type { font-size: 15px; }
.eara-button-icon { margin-right: 6px; }
.eara-offline-pill { background: alpha(currentColor,.06); border-radius: 25px; padding: 8px 16px; }
window.eara-window button.eara-tab:disabled box { opacity: 1; }
window.eara-window button.eara-tab:disabled { opacity: 1; filter: none; color: $disabled; }
window.eara-window button.eara-tab:disabled label, window.eara-window button.eara-tab:disabled image { filter: none; }
.eara-discovery-row { border: 1px solid $line; border-radius: 14px; padding: 16px; }
.eara-option-row { border: 1px solid $line; border-radius: 14px; padding: 10px 14px; }
.eara-option-name { font-size: 15px; font-weight: 650; }
.eara-option-badge { font-size: 12px; color: $muted; }
.eara-option-connect { min-height: 30px; min-width: 88px; font-size: 13px; font-weight: 600; background: #0b0b12; color: #ffffff; border-radius: 10px; }
.light-palette .eara-option-connect { background: #0b0b12; color: #ffffff; }
.eara-content button.eara-device-picker,
.eara-content button.eara-device-picker:hover,
.eara-content button.eara-device-picker:active { background: transparent; border: none; padding: 0; box-shadow: none; }
.eara-discovery-name { font-size: 22px; font-weight: 650; }
.eara-paired { background: $control; border-radius: 20px; padding: 5px 16px; font-size: 14px; }
.eara-content .eara-discovery-row button.eara-header-connect { min-width: 126px; min-height: 44px; font-size: 18px; font-weight: 600; border-radius: 12px; }
.eara-content button.eara-help-toggle { min-height: 38px; border: none; font-size: 18px; }
.eara-connection-help > button, .eara-partial-card > button { font-size: 18px; min-height: 38px; }
.eara-recovery-main > button { font-size: 18px; min-height: 40px; }
.eara-recovery-step label { font-size: 15px; font-weight: 400; }
.eara-recovery-step label.eara-recovery-step-strong { font-weight: 650; }
.eara-device-page .eara-system-item { font-size: 15px; }
button:focus-visible, switch:focus-visible, scale:focus-visible { outline: 2px solid #4285ff; outline-offset: 3px; }
'''
    values = {**p, 'font': ui_font, 'header_height': f'{GEOMETRY["header"]}px',
              'footer_height': f'{GEOMETRY["footer"]}px', 'card_radius': f'{GEOMETRY["radius"]}px',
              'card_padding': f'{GEOMETRY["card_padding"]}px'}
    css = re.sub(r'\$(\w+)', lambda match: values[match[1]], css)
    if not dark:
        css += '''
button.eara-tab.eara-tab-active { border-color: transparent; }
.eara-partial-card { background: #fef0ef; border-color: #ffcccc; color: #ba0015; }
.eara-status-badge-ok { color: #166534; background: #e0f2e5; }
headerbar button.flat { background: transparent; border-color: transparent; }
button.eara-header-connect { background: #0b0b12; color: #ffffff; }
'''
    return css
