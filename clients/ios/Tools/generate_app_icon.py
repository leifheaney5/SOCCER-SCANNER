#!/usr/bin/env python
"""Render the Soccer Scanner app icon from the brand geometry.

The mark is defined in `static/favicon.svg` on a 64x64 grid. No SVG rasteriser
is available in this toolchain, so the same geometry is reproduced with PIL and
scaled up. Keeping this as a script means the icon is reproducible rather than
an unexplained binary in the tree.

App Store icons must be fully opaque with no alpha channel and no rounded
corners of their own (iOS applies the mask), so the output is a flat RGB square.
The same rule holds for the PWA/manifest icons emitted by `--web`, so every
output below is a flat RGB image.

Usage:
    python clients/ios/Tools/generate_app_icon.py          # iOS AppIcon-1024.png (default)
    python clients/ios/Tools/generate_app_icon.py --web     # static/icons/* + static/social-card.png
"""

import argparse
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


def render_maskable(size, inset_fraction=0.8):
    """A maskable variant for Android's adaptive-icon safe zone.

    Android crops maskable icons to a circle or squircle, so the mark is
    inset to roughly 80% of the canvas here; anything drawn closer to the
    edge than that risks the corner brackets being cut off by the crop.
    """

    canvas = Image.new("RGB", (size, size), BACKGROUND)
    inner_size = round(size * inset_fraction)
    inner = render(inner_size)
    offset = (size - inner_size) // 2
    canvas.paste(inner, (offset, offset))
    return canvas


def render_social_card(width=1200, height=630):
    """The Open Graph / Twitter card: the mark centred on the brand black.

    No text is rendered here — several platforms crop or scale card images
    unpredictably, and the mark alone reads at any crop.
    """

    canvas = Image.new("RGB", (width, height), BACKGROUND)
    mark_size = min(width, height) - 210
    mark = render(mark_size)
    offset = ((width - mark_size) // 2, (height - mark_size) // 2)
    canvas.paste(mark, offset)
    return canvas


# size in pixels for every `render(size)` output written by --web
WEB_ICON_SIZES = {
    "icon-192.png": 192,
    "icon-512.png": 512,
    "apple-touch-icon.png": 180,
    "favicon-32.png": 32,
}

MASKABLE_SIZE = 512


def _save_opaque(image, destination):
    assert image.mode == "RGB", f"{destination.name} must not carry an alpha channel"
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG")
    print(f"wrote {destination} ({image.size[0]}x{image.size[1]}, {image.mode})")


def write_web_assets(repo_root):
    icons_dir = repo_root / "static" / "icons"

    for filename, size in WEB_ICON_SIZES.items():
        _save_opaque(render(size), icons_dir / filename)

    _save_opaque(render_maskable(MASKABLE_SIZE), icons_dir / "icon-maskable-512.png")
    _save_opaque(render_social_card(), repo_root / "static" / "social-card.png")


def write_ios_asset(repo_root):
    destination = (
        repo_root / "clients" / "ios"
        / "SoccerScanner" / "Resources" / "Assets.xcassets"
        / "AppIcon.appiconset" / "AppIcon-1024.png"
    )
    _save_opaque(render(), destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--web",
        action="store_true",
        help="write the web/PWA icon suite and social card into static/ instead of the iOS asset catalog",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]

    if args.web:
        write_web_assets(repo_root)
    else:
        write_ios_asset(repo_root)


if __name__ == "__main__":
    main()
