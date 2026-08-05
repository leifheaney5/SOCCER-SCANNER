#!/usr/bin/env python
"""Render the Soccer Scanner app icon from the brand geometry.

The mark is defined in `static/favicon.svg` on a 64x64 grid. No SVG rasteriser
is available in this toolchain, so the same geometry is reproduced with PIL and
scaled up. Keeping this as a script means the icon is reproducible rather than
an unexplained binary in the tree.

App Store icons must be fully opaque with no alpha channel and no rounded
corners of their own (iOS applies the mask), so the output is a flat RGB square.

Usage:
    python clients/ios/Tools/generate_app_icon.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

GRID = 64          # brand co-ordinate space
TARGET = 1024      # App Store icon size
SUPERSAMPLE = 4    # draw large, downsample for clean edges

BACKGROUND = (0, 0, 0)
GREEN = (124, 255, 0)      # #7cff00
BRACKET = (242, 242, 242)  # #f2f2f2


def arc_points(centre, radius, start_degrees, end_degrees, steps=24):
    """Points along a circular arc, in SVG screen space (y grows downward)."""
    cx, cy = centre
    points = []
    for index in range(steps + 1):
        t = start_degrees + (end_degrees - start_degrees) * index / steps
        radians = math.radians(t)
        points.append((cx + radius * math.cos(radians), cy + radius * math.sin(radians)))
    return points


def scanner_s():
    """The blocky 'S', matching the favicon path exactly."""
    points = [(17, 16), (47, 16), (47, 24), (25, 24), (25, 30), (42, 30)]
    # (42,30) -> (49,37), centre (42,37): from straight up round to the right.
    points += arc_points((42, 37), 7, -90, 0)
    points += [(49, 41)]
    # (49,41) -> (42,48), centre (42,41): from the right round to straight down.
    points += arc_points((42, 41), 7, 0, 90)
    points += [(15, 48), (15, 40), (41, 40), (41, 34), (24, 34)]
    # (24,34) -> (17,27), centre (24,27): from straight down round to the left.
    points += arc_points((24, 27), 7, 90, 180)
    return points


def corner_brackets():
    """Four scanner corners, as in the favicon."""
    return [
        # top-left
        (11, 11, 21, 14), (11, 11, 14, 21),
        # top-right
        (43, 11, 53, 14), (50, 11, 53, 21),
        # bottom-left
        (11, 50, 21, 53), (11, 43, 14, 53),
        # bottom-right
        (43, 50, 53, 53), (50, 43, 53, 53),
    ]


def render(size=TARGET):
    canvas = size * SUPERSAMPLE
    scale = canvas / GRID
    image = Image.new("RGB", (canvas, canvas), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.polygon([(x * scale, y * scale) for x, y in scanner_s()], fill=GREEN)
    for x0, y0, x1, y1 in corner_brackets():
        draw.rectangle([x0 * scale, y0 * scale, x1 * scale, y1 * scale], fill=BRACKET)

    return image.resize((size, size), Image.LANCZOS)


def main():
    destination = (
        Path(__file__).resolve().parents[1]
        / "SoccerScanner" / "Resources" / "Assets.xcassets"
        / "AppIcon.appiconset" / "AppIcon-1024.png"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    icon = render()
    assert icon.mode == "RGB", "App Store icons must not carry an alpha channel"
    icon.save(destination, "PNG")
    print(f"wrote {destination} ({icon.size[0]}x{icon.size[1]}, {icon.mode})")


if __name__ == "__main__":
    main()
