"""Render OG-preview PNGs for /share/train/{id} links.

This module is intentionally domain-free: it takes pre-formatted strings
and returns PNG bytes. Translating a train into the headline/status text
is the route layer's job.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Less-wide than the standard 1200x630 OG size — iMessage crops landscape
# previews toward square anyway, so a narrower canvas wastes less space on
# the sides and looks more balanced when rendered.
CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 540

# Layout — picked so an Apple Messages preview (cropped to roughly square)
# still shows the icon and headline together.
ICON_SIZE = 280
ICON_TOP = 30
TEXT_TOP_GAP = 16
TEXT_LINE_GAP = 12
HEADLINE_MAX_PT = 64
HEADLINE_MIN_PT = 36
STATUS_PT = 44
TEXT_HORIZONTAL_PADDING = 40

# Cream background blends into the icon's native backing; dark text for contrast.
BG_COLOR = (248, 246, 234)  # #f8f6ea
HEADLINE_COLOR = (26, 26, 26)
STATUS_COLOR = (26, 26, 26, 153)  # ~60% opacity

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "share"
_ICON_PATH = _ASSET_DIR / "trackrat-icon.png"
_FONT_BOLD = _ASSET_DIR / "Inter-Bold.ttf"
_FONT_REGULAR = _ASSET_DIR / "Inter-Regular.ttf"


def render_share_image(headline: str, status: str) -> bytes:
    """Render a 1200x630 share-preview PNG.

    Args:
        headline: First text line (e.g. ``"NJT 3957 to Hoboken"``).
        status: Second text line (e.g. ``"Arriving 5:42 PM"``).

    Returns:
        PNG bytes.
    """
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(canvas, "RGBA")

    icon = Image.open(_ICON_PATH).convert("RGBA")
    icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    canvas.paste(icon, ((CANVAS_WIDTH - ICON_SIZE) // 2, ICON_TOP), icon)

    text_max_width = CANVAS_WIDTH - 2 * TEXT_HORIZONTAL_PADDING
    headline_font = _fit_font(
        headline, _FONT_BOLD, text_max_width, HEADLINE_MAX_PT, HEADLINE_MIN_PT
    )
    status_font = ImageFont.truetype(str(_FONT_REGULAR), STATUS_PT)

    headline_y = ICON_TOP + ICON_SIZE + TEXT_TOP_GAP
    _draw_centered(draw, headline, headline_font, headline_y, HEADLINE_COLOR)

    headline_h = _measure_height(headline_font, headline)
    status_y = headline_y + headline_h + TEXT_LINE_GAP
    _draw_centered(draw, status, status_font, status_y, STATUS_COLOR)

    buf = BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fit_font(
    text: str, font_path: Path, max_width: int, max_pt: int, min_pt: int
) -> ImageFont.FreeTypeFont:
    """Return the largest font (in 4pt steps) whose rendered text fits ``max_width``.

    Falls back to ``min_pt`` if even that overflows; the caller accepts the
    overflow rather than truncating, on the theory that a slightly-wide
    preview is more useful than an ellipsis.
    """
    for pt in range(max_pt, min_pt - 1, -4):
        font = ImageFont.truetype(str(font_path), pt)
        left, _, right, _ = font.getbbox(text)
        if right - left <= max_width:
            return font
    return ImageFont.truetype(str(font_path), min_pt)


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    y: int,
    fill: tuple[int, ...],
) -> None:
    left, _, right, _ = font.getbbox(text)
    x = (CANVAS_WIDTH - (right - left)) // 2 - left
    draw.text((x, y), text, font=font, fill=fill)


def _measure_height(font: ImageFont.FreeTypeFont, text: str) -> int:
    _, top, _, bottom = font.getbbox(text)
    return int(bottom - top)
