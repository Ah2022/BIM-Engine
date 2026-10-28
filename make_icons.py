# -*- coding: utf-8 -*-
"""
Generates flat-style PNG icons for the Model Scanner ribbon buttons.
Run once at build time; output PNGs are committed alongside each
pushbutton's script.py / bundle.yaml.
"""
import os
import math
from PIL import Image, ImageDraw

OUT_ROOT = os.path.join(os.path.dirname(__file__), "BIMEngine.extension", "BIMEngine.tab", "ModelScanner.panel")

# Palette: navy/steel to match the existing Clash Radar dark-navy panel style,
# plus an accent color per icon.
NAVY = (30, 41, 59, 255)
STEEL = (71, 85, 105, 255)
WHITE = (241, 245, 249, 255)
ACCENT_SCAN = (56, 189, 248, 255)   # cyan - "run scan / radar sweep"
ACCENT_SETTINGS = (148, 163, 184, 255)  # slate - gear
ACCENT_REPORT = (248, 113, 113, 255)  # red/orange - flagged issues


def new_canvas(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def draw_run_scan(size):
    img, d = new_canvas(size)
    cx = cy = size / 2
    r_outer = size * 0.42

    # Octree-ish nested squares (nod to the spatial index) behind a radar sweep
    d.rectangle([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                outline=STEEL, width=max(1, size // 16))
    r_mid = r_outer * 0.55
    d.rectangle([cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid],
                outline=STEEL, width=max(1, size // 20))

    # Radar sweep arc + center dot in the accent color
    d.pieslice([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
               start=-30, end=60, fill=(*ACCENT_SCAN[:3], 90))
    d.ellipse([cx - size * 0.05, cy - size * 0.05, cx + size * 0.05, cy + size * 0.05],
              fill=ACCENT_SCAN)

    # A couple of "clash" pips on the grid
    for dx, dy in [(-r_mid * 0.6, r_mid * 0.5), (r_mid * 0.5, -r_mid * 0.4)]:
        px, py = cx + dx, cy + dy
        rad = size * 0.045
        d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=WHITE)

    return img


def draw_settings(size):
    img, d = new_canvas(size)
    cx = cy = size / 2

    # Gear body: a plain disc plus chunky rectangular teeth (6, not 8+) so it
    # still reads as a gear rather than a starburst once scaled down to 16px.
    r_body = size * 0.28
    d.ellipse([cx - r_body, cy - r_body, cx + r_body, cy + r_body], fill=ACCENT_SETTINGS)

    tooth_w = size * 0.15
    tooth_len = size * 0.11
    teeth = 6
    for i in range(teeth):
        angle = (2 * math.pi / teeth) * i
        tx = cx + (r_body + tooth_len / 2) * math.cos(angle)
        ty = cy + (r_body + tooth_len / 2) * math.sin(angle)
        d.ellipse([tx - tooth_w / 2, ty - tooth_w / 2, tx + tooth_w / 2, ty + tooth_w / 2], fill=ACCENT_SETTINGS)

    # Center hole
    r_inner = size * 0.11
    d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=NAVY)

    return img


def draw_issue_report(size):
    img, d = new_canvas(size)
    margin = size * 0.16
    # Clipboard / list body
    d.rounded_rectangle([margin, margin * 1.3, size - margin, size - margin * 0.7],
                         radius=size * 0.06, outline=STEEL, width=max(1, size // 16))
    # clip tab
    tab_w = size * 0.26
    d.rounded_rectangle([cx_left := (size - tab_w) / 2, margin * 0.5, cx_left + tab_w, margin * 1.5],
                         radius=size * 0.03, fill=STEEL)

    # list lines
    line_x0 = margin * 1.6
    line_x1 = size - margin * 1.6
    for i, frac in enumerate([0.38, 0.55, 0.72]):
        y = size * frac
        color = ACCENT_REPORT if i in (0, 2) else STEEL
        d.line([(line_x0, y), (line_x1, y)], fill=color, width=max(1, size // 18))
        # flag dot for "issue" rows
        if i in (0, 2):
            rad = size * 0.035
            d.ellipse([line_x0 - rad * 2.4, y - rad, line_x0 - rad * 0.4, y + rad], fill=ACCENT_REPORT)

    return img


ICON_SETS = {
    "RunScan.pushbutton": draw_run_scan,
    "Settings.pushbutton": draw_settings,
    "IssueReport.pushbutton": draw_issue_report,
}

for folder, draw_fn in ICON_SETS.items():
    out_dir = os.path.join(OUT_ROOT, folder)
    for size, filename in [(32, "icon.png"), (16, "icon.small.png")]:
        img = draw_fn(size)
        img.save(os.path.join(out_dir, filename))
        print("wrote", os.path.join(out_dir, filename))
