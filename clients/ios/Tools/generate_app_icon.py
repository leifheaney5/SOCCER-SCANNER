#!/usr/bin/env python
"""Render the Soccer Radar app icons from the shared radar geometry.

The mark is defined in `static/favicon.svg` on a 360x360 grid. No SVG
rasteriser is available in this toolchain, so the geometry is reproduced with
PIL and scaled up. Keeping this as a script makes the generated icons
reproducible rather than unexplained binaries in the tree.

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

from PIL import Image, ImageDraw, ImageFont

GRID = 360         # brand co-ordinate space
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


def render(size=TARGET):
    canvas = size * SUPERSAMPLE
    scale = canvas / GRID
    image = Image.new("RGB", (canvas, canvas), BACKGROUND)
    draw = ImageDraw.Draw(image)

    def box(centre, radius):
        cx, cy = centre
        return tuple(round(value * scale) for value in (
            cx - radius, cy - radius, cx + radius, cy + radius,
        ))

    def arc(radius, start, end, color, width):
        draw.arc(box((180, 180), radius), start, end, fill=color, width=round(width * scale))

    def circle(centre, radius, color):
        cx, cy = centre
        draw.ellipse(box((cx, cy), radius), fill=color)

    def line(points, color, width):
        draw.line(
            [(round(x * scale), round(y * scale)) for x, y in points],
            fill=color,
            width=round(width * scale),
        )

    # A restrained sweep sector recalls the live scanner without obscuring the
    # target rings at app-icon sizes.
    sweep = [(180, 180)] + arc_points((180, 180), 138, -90, -26)
    draw.polygon([(round(x * scale), round(y * scale)) for x, y in sweep], fill=(39, 83, 0))
    sweep_core = [(180, 180)] + arc_points((180, 180), 124, -90, -26)
    draw.polygon([(round(x * scale), round(y * scale)) for x, y in sweep_core], fill=(53, 111, 0))

    # Black under-strokes preserve separation between the rings and outer frame
    # at icon sizes.
    for start, end in ((184, 266), (274, 356), (4, 86), (94, 176)):
        arc(156, start, end, BACKGROUND, 16)
    arc(156, 184, 266, BRACKET, 8)
    arc(156, 274, 356, BRACKET, 8)
    arc(156, 4, 86, GREEN, 8)
    arc(156, 94, 176, GREEN, 8)

    draw.ellipse(box((180, 180), 116), outline=BACKGROUND, width=round(12 * scale))
    draw.ellipse(box((180, 180), 116), outline=(89, 190, 0), width=round(6 * scale))
    for start, end in ((202, 253), (278, 329), (22, 77), (102, 154)):
        arc(78, start, end, BACKGROUND, 12)
    arc(78, 202, 253, GREEN, 6)
    arc(78, 278, 329, GREEN, 6)
    arc(78, 22, 77, GREEN, 6)
    arc(78, 102, 154, GREEN, 6)

    # Crosshairs sit above the rings; the bullseye is drawn last to stay crisp.
    line([(180, 18), (180, 342)], BACKGROUND, 18)
    line([(18, 180), (342, 180)], BACKGROUND, 15)
    line([(180, 18), (180, 342)], BRACKET, 10)
    line([(18, 180), (342, 180)], GREEN, 7)

    for centre in ((102, 136), (238, 82), (242, 240)):
        circle(centre, 16, BACKGROUND)
        circle(centre, 12, GREEN)

    draw.ellipse(box((180, 180), 42), fill=BACKGROUND, outline=BRACKET, width=round(10 * scale))
    circle((180, 180), 12, BRACKET)

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
    """Render the horizontal radar-and-wordmark social card."""

    canvas = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    mark_size = 320
    gap = 40
    tracking = 5
    font = ImageFont.truetype(
        str(Path(__file__).parent / "fonts" / "Orbitron-Variable.ttf"),
        72,
    )
    font.set_variation_by_axes([700])

    def text_width(text):
        return sum(draw.textlength(character, font=font) for character in text) + tracking * max(0, len(text) - 1)

    soccer_width = text_width("SOCCER")
    radar_width = text_width("RADAR")
    text_gap = 28
    lockup_width = mark_size + gap + soccer_width + text_gap + radar_width
    lockup_x = round((width - lockup_width) / 2)
    mark_y = (height - mark_size) // 2
    canvas.paste(render(mark_size), (lockup_x, mark_y))

    text_y = (height - font.getbbox("SOCCER")[3]) // 2 - font.getbbox("SOCCER")[1]

    def draw_word(text, start_x, color):
        for character in text:
            draw.text(
                (round(start_x), text_y),
                character,
                font=font,
                fill=color,
                stroke_width=2,
                stroke_fill=BACKGROUND,
            )
            start_x += draw.textlength(character, font=font) + tracking

    text_x = lockup_x + mark_size + gap
    draw_word("SOCCER", text_x, BRACKET)
    draw_word("RADAR", text_x + soccer_width + text_gap, GREEN)
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
