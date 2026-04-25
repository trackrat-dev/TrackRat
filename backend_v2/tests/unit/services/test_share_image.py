"""Tests for the share-link OG image renderer.

Asserts structural properties (PNG output, dimensions, robustness to
varied input) rather than pixel content, since visual regressions are
better caught by eyeballing the rendered output during review.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from trackrat.services.share_image import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    render_share_image,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(BytesIO(png_bytes))


def test_render_returns_png_at_expected_dimensions() -> None:
    png = render_share_image("NJT 3957 to Hoboken", "Arriving 5:42 PM")

    assert png.startswith(PNG_MAGIC), "output is not a PNG"

    img = _decode(png)
    assert img.format == "PNG"
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_render_handles_all_status_variants() -> None:
    """The three status strings the route layer can produce must all render."""
    for headline, status in [
        ("NJT 3957 to Hoboken", "Arriving 5:42 PM"),
        ("AMTRAK 178 to Boston Back Bay", "Cancelled"),
        ("MNR 901 to Grand Central", "Scheduled 8:15 AM"),
    ]:
        png = render_share_image(headline, status)
        assert _decode(png).size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_render_handles_long_headline_via_autofit() -> None:
    """Headlines that would overflow at 64pt should auto-shrink, not crash."""
    headline = "SUBWAY 7-Express to Flushing-Main St"
    png = render_share_image(headline, "Arriving 5:42 PM")
    assert _decode(png).size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_render_handles_empty_strings() -> None:
    """Defensive: empty inputs must not crash the renderer."""
    png = render_share_image("", "")
    assert _decode(png).size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_render_handles_unicode() -> None:
    """Station names occasionally contain accents (e.g. Montréal)."""
    png = render_share_image("VIA 67 to Montréal Central", "Arriving 6:12 PM")
    assert _decode(png).size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_render_is_deterministic_for_same_input() -> None:
    """Same inputs produce same bytes — important for HTTP caching."""
    a = render_share_image("NJT 3957 to Hoboken", "Arriving 5:42 PM")
    b = render_share_image("NJT 3957 to Hoboken", "Arriving 5:42 PM")
    assert a == b
