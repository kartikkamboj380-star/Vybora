#!/usr/bin/env python3
"""Render the existing Vybora vector into required bitmap-compatible resources.

Run from any directory after installing Pillow: python3 scripts/render_branding_assets.py
No network access is used. The checked-in PNGs are source assets; CI does not need
Pillow or this generator. BitmapDrawable/BitmapFactory callers cannot use an XML
vector as a drop-in replacement for these two resources.
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

RES = Path(__file__).resolve().parents[1] / "app/src/main/res"
ANDROID = "{http://schemas.android.com/apk/res/android}"
SCALE = 4
SIZE = 512


def curves(path_data):
    """Sample the absolute M/C paths used by ic_vybora_mark.xml."""
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", path_data)
    index = 0
    points = []
    joins = []
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "M":
            if points:
                yield points, joins
            point = (float(tokens[index]), float(tokens[index + 1]))
            index += 2
            points, joins = [point], [point]
        elif command == "C":
            values = list(map(float, tokens[index:index + 6]))
            index += 6
            start = points[-1]
            control1, control2, end = values[:2], values[2:4], values[4:]
            for step in range(1, 121):
                t = step / 120
                point = tuple((1 - t) ** 3 * start[axis]
                              + 3 * (1 - t) ** 2 * t * control1[axis]
                              + 3 * (1 - t) * t ** 2 * control2[axis]
                              + t ** 3 * end[axis] for axis in range(2))
                points.append(point)
            joins.append(tuple(end))
        else:
            raise ValueError(f"Unsupported brand path command: {command}")
    if points:
        yield points, joins


def render(background):
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), background)
    draw = ImageDraw.Draw(image)
    vector = ET.parse(RES / "drawable/ic_vybora_mark.xml").getroot()
    for path in vector.findall("path"):
        color = path.attrib[ANDROID + "strokeColor"]
        width = round(float(path.attrib[ANDROID + "strokeWidth"]) * SCALE)
        radius = width / 2
        for points, _joins in curves(path.attrib[ANDROID + "pathData"]):
            draw.line([(x * SCALE, y * SCALE) for x, y in points], fill=color, width=width)
            # Union round disks along the sampled curve. Pillow's curved-join
            # optimization can leave wedges when segments are shorter than the
            # stroke width; explicit disks produce a solid SVG-like round stroke.
            for x, y in points:
                x, y = x * SCALE, y * SCALE
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    render((0, 0, 0, 0)).save(RES / "drawable/ic_launcher_nobg.png", optimize=True)
    render("#171525").save(RES / "drawable/icon.png", optimize=True)
