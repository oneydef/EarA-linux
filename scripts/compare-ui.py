#!/usr/bin/env python3
"""Build aligned comparison evidence. No percentage similarity claims.

Reference PNG window bounds are measured manually. Images are scaled uniformly
by client width; a <=1px rounding difference in height is padded, not stretched.
GTK captures have native widget bounds in their adjacent .checks.json files.
"""
import html
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/verification/audit'
CASES = {
    'device': ('ui-refresh-device-dashboard.png', (52,83,1535,931), {
        'navigation':(52,157,305,873), 'device_card':(321,177,1031,563),
        'device_noise':(1048,177,1518,563), 'audio_profile':(321,583,864,855),
        'quick_controls':(881,583,1518,855)}),
    'sound': ('ui-refresh-sound-eq.png', (44,51,1544,941), {
        'navigation':(44,133,223,941),'equalizer':(242,278,1034,830),
        'listening':(1048,278,1524,584),'sound_noise':(1048,599,1524,830),
        'eq_actions':(242,846,1524,925)}),
    'recovery': ('ui-refresh-connection-recovery-light.png', (40,65,1547,929), {
        'navigation':(40,153,295,929), 'found_devices':(316,363,1090,557),
        'connection_help':(1134,184,1529,650), 'partial_warning':(1134,673,1529,870),
        'recovery_steps':(325,630,1060,797)}),
}
results = {}
sections = []
for name, (source, crop, reference_bounds) in CASES.items():
    report = json.loads((OUT/f'{name}.png.checks.json').read_text())
    actual = Image.open(OUT/f'{name}.client.png').convert('RGB')
    reference = Image.open(ROOT/'docs/mockups'/source).convert('RGB').crop(crop)
    scale = actual.width/reference.width
    scaled_size = (actual.width, round(reference.height*scale))
    if abs(scaled_size[1]-actual.height)>1:
        raise ValueError(f'{name}: viewport aspect mismatch; recapture at {scaled_size}')
    scaled = reference.resize(scaled_size, Image.Resampling.LANCZOS)
    reference = Image.new('RGB',actual.size,scaled.getpixel((scaled.width//2,scaled.height-2)))
    reference.paste(scaled,(0,0))
    reference.save(OUT/f'{name}-reference.png')
    Image.blend(reference,actual,.5).save(OUT/f'{name}-overlay.png')
    diff = ImageChops.difference(reference,actual)
    # Luminance difference mapped from black (0) through red to yellow (255).
    heat = ImageOps.colorize(diff.convert('L'), black='#101010', white='#ffff00', mid='#db1825')
    heat.save(OUT/f'{name}-heatmap.png')
    side = Image.new('RGB',(actual.width*2,actual.height+36),'#eeeeee')
    side.paste(reference,(0,36));side.paste(actual,(actual.width,36))
    draw = ImageDraw.Draw(side)
    draw.text((16,10),'APPROVED REFERENCE (uniformly scaled)',fill='#111111')
    draw.text((actual.width+16,10),'ACTUAL GTK (explicit UI fixture)',fill='#111111')
    side.save(OUT/f'{name}-comparison.png')
    measures = {}
    for key, box in reference_bounds.items():
        if key not in report['geometry']:
            continue
        x,y,r,b = box
        expected = [(x-crop[0])*scale,(y-crop[1])*scale,(r-x)*scale,(b-y)*scale]
        observed = report['geometry'][key]
        measures[key] = {'reference_xywh':list(map(lambda n:round(n,1),expected)),
                         'gtk_xywh':observed,
                         'delta_xywh': [round(a-e,1) for a,e in zip(observed,expected)]}
    results[name] = {'viewport':list(actual.size),'source_window_crop':crop,'uniform_scale':round(scale,6),
                     'reference_measurement_tolerance_px':3,'components':measures,
                     'pixel_identical':diff.getbbox() is None,
                     'notes':'No aggregate pixel score: text, state details, frequency labels and the unified navigation intentionally differ. Heatmaps show all differences without claiming a percentage similarity.'}
    if name == 'sound':
        # Compare visible text ink, not a guessed font baseline. Rectangles are
        # fixed in the normalized 1280px reference and exclude nearby icons.
        ink = {}
        for title, rect in {'page_heading':(185,95,410,145),
                            'equalizer_heading':(230,210,370,247),
                            'listening_heading':(914,210,1120,247),
                            'page_subtitle':(185,148,410,181)}.items():
            boxes = []
            for source_image in (reference, actual):
                bounds = source_image.crop(rect).convert('L').point(lambda v:255 if v>=140 else 0).getbbox()
                boxes.append([bounds[0]+rect[0],bounds[1]+rect[1],bounds[2]-bounds[0],bounds[3]-bounds[1]] if bounds else None)
            ink[title] = {'reference_ink_xywh':boxes[0], 'gtk_ink_xywh':boxes[1],
                          'delta_xywh':[a-b for a,b in zip(boxes[1],boxes[0])] if all(boxes) else None}
        results[name]['typography'] = {'method':'Visible raster ink at luminance >=140 in fixed ROIs. This is not a font-baseline measurement; antialiasing and font rasterization affect the bounds.', 'regions':ink}
    rows = ''.join(f'<tr><td>{html.escape(key)}</td><td>{m["reference_xywh"]}</td><td>{m["gtk_xywh"]}</td><td>{m["delta_xywh"]}</td></tr>' for key,m in measures.items())
    sections.append(f'''<section><h2>{name.title()}</h2><p>Client viewport: {actual.width} × {actual.height}. Reference scaled uniformly by {scale:.6f}. Raster boundary measurement tolerance: ±3 px in the source.</p>
    <img src="{name}-comparison.png" alt="Reference and actual GTK side by side">
    <details><summary>50% alpha overlay</summary><img src="{name}-overlay.png" alt="Alpha overlay"></details>
    <details><summary>Difference heatmap — dark means equal, brighter means larger difference</summary><img src="{name}-heatmap.png" alt="Pixel difference heatmap"></details>
    <table><thead><tr><th>Component</th><th>Reference x,y,w,h</th><th>GTK x,y,w,h</th><th>Difference x,y,w,h</th></tr></thead><tbody>{rows}</tbody></table></section>''')
(OUT/'measurements.json').write_text(json.dumps(results,indent=2)+'\n')
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>EarA visual verification</title>
<style>body{font:16px system-ui;margin:32px auto;max-width:1400px;padding:0 24px;color:#202124;background:#fafafa}h1{font-size:30px}p{line-height:1.6;max-width:1100px}img{max-width:100%;height:auto;border:1px solid #ccc}section{margin:40px 0;border-top:1px solid #bbb;padding-top:12px}summary{cursor:pointer;padding:12px 0}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}a{color:#134eaa}code{background:#eee;padding:2px 4px}</style>
<h1>EarA — implementation verification</h1>
<p>These are native GTK screenshots, not browser recreations. The three visual comparisons use explicitly identified deterministic fixtures. Device, Sound and recovery are captured at the same aspect ratio as their reference windows. OS shadows are removed before comparison. No unaligned pixel-error percentages are reported.</p>
<p><strong>Scope:</strong> shared 154 px sidebar, reference artwork, component geometry, real EQ sliders and grid, local preset save/load, dark/light themes, grouped Gestures/Tools, service diagnostics. The approved PNGs have different sidebar widths; the implementation uses the compact Sound width consistently, as requested.</p>
<p><strong>Behavior:</strong> Save preset stores eight gains locally. Apply sends them through the existing three-band mapping. Real frequency labels (32–4000 Hz) remain unchanged. Instant application is not advertised. The latest live read found Bluetooth connected and audio service available, but no active audio sink was returned; RFCOMM reported a busy control channel. An earlier read timed out. No successful hardware ANC/EQ/gesture/ringing/fit operation is claimed.</p>
<p><a href="README.md">Full findings, verification and remaining differences</a> · <a href="measurements.json">Machine-readable bounds</a> · <a href="live-status.png">Actual live partial state</a> · <a href="gestures.png">Gestures</a> · <a href="tools.png">Tools</a> · <a href="disconnected.png">Disconnected</a></p>
''' + ''.join(sections) + '''<section><h2>Remaining differences</h2><p>Sound card geometry is within a few normalized pixels of the reference. Device/recovery have deliberate horizontal offsets from the unified compact sidebar. The device model uses live dotted text generated from Inter, because an editable original dotted font is not supplied. Native window controls, the actual device selector and explicit Apply action differ. Existing battery warning thresholds are preserved. Reference artwork contains baked background texture, especially visible when changing theme.</p><p>Gestures/Tools are verified for consistency, not pixel identity: no approved screenshots of these pages were provided.</p></section></html>'''
(OUT/'index.html').write_text(page)
print(json.dumps({key:value['components'] for key,value in results.items()},indent=2))
