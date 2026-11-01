"""Rendering helpers; native widgets retain keyboard and accessible semantics."""
import math
import cairo
from gi.repository import Adw, Gdk, GdkPixbuf, Gtk, Pango, PangoCairo


def dotted_label(label, size):
    """Render the live label through a circular dot mask (not a bitmap caption)."""
    overlay = Gtk.Overlay()
    label.set_opacity(0)
    label.set_size_request(-1, size + 10)
    # The dots are drawn from the widget allocation; the hidden label must not
    # force its full text width into the container's minimum size.
    label.set_ellipsize(Pango.EllipsizeMode.END)
    label.set_width_chars(2)
    overlay.set_child(label)
    dots = Gtk.DrawingArea()
    dots.set_can_target(False)
    def paint(widget, cr, width, height):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        mask = cairo.Context(surface)
        layout = PangoCairo.create_layout(mask)
        font = Pango.FontDescription(f'Inter Medium {size}')
        font.set_absolute_size(size * Pango.SCALE)
        layout.set_font_description(font)
        layout.set_text(label.get_text(), -1)
        tw, th = layout.get_pixel_size()
        scale = min(1, width / max(tw, 1))
        mask.translate(0, (height-th*scale)/2)
        mask.scale(scale, scale)
        mask.set_source_rgba(1,1,1,1)
        PangoCairo.show_layout(mask, layout)
        surface.flush()
        pixels = surface.get_data()
        stride = surface.get_stride()
        color = label.get_style_context().get_color()
        cr.set_source_rgba(color.red,color.green,color.blue,color.alpha)
        step = 3.1 if size >= 30 else 2.7
        for y in range(int(height/step)):
            for x in range(int(width/step)):
                px, py = int(x*step+step/2), int(y*step+step/2)
                if pixels[py*stride+px*4+3] > 75:
                    cr.arc(px,py,step*.34,0,math.tau)
                    cr.fill()
    dots.set_draw_func(paint)
    label.connect('notify::label', lambda *_: dots.queue_draw())
    overlay.add_overlay(dots)
    return overlay


def reference_art(path, rectangle, max_scale=2):
    """Reuse only the illustration region of the approved source PNG in the UI."""
    source = GdkPixbuf.Pixbuf.new_from_file(str(path))
    pixbuf = source.new_subpixbuf(*rectangle)
    art = Gtk.DrawingArea()
    def paint(widget, cr, width, height):
        scale = min(max_scale, width / pixbuf.get_width(), height / pixbuf.get_height())
        cr.translate((width-pixbuf.get_width()*scale)/2, (height-pixbuf.get_height()*scale)/2)
        cr.scale(scale,scale)
        Gdk.cairo_set_source_pixbuf(cr,pixbuf,0,0)
        cr.paint()
    art.set_draw_func(paint)
    art.update_property([Gtk.AccessibleProperty.LABEL], ['Earbuds illustration'])
    return art


def equalizer_grid(bands_box, bands):
    overlay = Gtk.Overlay()
    bands_box.set_margin_start(51)
    bands_box.set_margin_end(19)
    overlay.set_child(bands_box)
    grid = Gtk.DrawingArea()
    grid.set_can_target(False)
    def paint(widget, cr, width, height):
        ok, bounds = bands[0].compute_bounds(overlay)
        if not ok: return
        top = bounds.get_y()+9
        bottom = bounds.get_y()+bounds.get_height()-9
        color = widget.get_style_context().get_color()
        cr.set_line_width(1)
        for index in range(9):
            y = top + (bottom-top)*index/8
            cr.set_source_rgba(color.red,color.green,color.blue, .28 if index==4 else .12)
            cr.set_dash([2,5])
            cr.move_to(55,y);cr.line_to(width-8,y);cr.stroke()
            if index in (0,4,8):
                cr.set_dash([])
                cr.set_source_rgba(color.red,color.green,color.blue,.7)
                cr.select_font_face('Inter',cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(12)
                cr.move_to(4,y+4)
                cr.show_text({0:'+6 dB',4:'0 dB',8:'−6 dB'}[index])
        cr.set_dash([])
    grid.set_draw_func(paint)
    overlay.add_overlay(grid)
    return overlay


def brand_mark(dark_path, light_path):
    """The constant brand mark reuses the actual approved artwork for each theme."""
    images = {}
    for dark, path, rect in ((True, dark_path, (80, 101, 108, 43)),
                             (False, light_path, (68, 87, 128, 45))):
        if path is not None:
            images[dark] = GdkPixbuf.Pixbuf.new_from_file(str(path)).new_subpixbuf(*rect)
    mark = Gtk.DrawingArea(content_width=102, content_height=40)
    mark.set_valign(Gtk.Align.CENTER)
    mark.update_property([Gtk.AccessibleProperty.LABEL], ['EarA'])
    def paint(widget, cr, width, height):
        pixbuf = images.get(Adw.StyleManager.get_default().get_dark())
        if pixbuf is None:
            return
        scale = min(width/pixbuf.get_width(), height/pixbuf.get_height())
        cr.translate(0, (height-pixbuf.get_height()*scale)/2)
        cr.scale(scale,scale)
        Gdk.cairo_set_source_pixbuf(cr,pixbuf,0,0)
        cr.paint()
    mark.set_draw_func(paint)
    Adw.StyleManager.get_default().connect('notify::dark', lambda *_: mark.queue_draw())
    return mark

class SvgIcon(Gtk.DrawingArea):
    """Tint a reference SVG alpha mask with the live GTK foreground color."""
    def __init__(self, directory, name, size=28):
        super().__init__(content_width=size, content_height=size)
        self.directory = directory
        self.name = name
        self.cache = {}
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_draw_func(self._paint)

    def set_from_icon_name(self, name):
        self.name = name.removeprefix('eara-').removesuffix('-symbolic')
        self.cache.clear()
        self.queue_draw()

    def set_pixel_size(self, size):
        self.set_content_width(size)
        self.set_content_height(size)

    def _paint(self, widget, cr, width, height):
        key = (self.name, width, height)
        if key not in self.cache:
            self.cache[key] = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(self.directory / f'eara-{self.name}-symbolic.svg'), width, height, True)
        cr.push_group()
        Gdk.cairo_set_source_pixbuf(cr, self.cache[key], 0, 0)
        cr.paint()
        mask = cr.pop_group()
        color = self.get_style_context().get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.mask(mask)
