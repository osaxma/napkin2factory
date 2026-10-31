"""The icon and wordmark on generated pages are the brand package's, byte for byte (B-0050)."""

from __future__ import annotations

import base64
from pathlib import Path

from napkin2factory.report import brand

REPO = Path(__file__).resolve().parents[2]


def test_report_icon_matches_brand_package() -> None:
    # brand/build.py writes both; a hand edit to either shows up here.
    assert brand.ICON.read_bytes() == (REPO / "brand/svg/n2f-icon-32.svg").read_bytes()
    wordmark = REPO / "brand/svg/n2f-wordmark-on-light.svg"
    assert brand.WORDMARK.read_bytes() == wordmark.read_bytes()


def test_icon_is_embedded_not_linked() -> None:
    uri = brand.icon_data_uri()
    prefix = "data:image/svg+xml;base64,"
    assert uri.startswith(prefix)
    assert base64.b64decode(uri[len(prefix) :]) == brand.ICON.read_bytes()
    assert uri in brand.favicon_link()
    assert uri in brand.footer_mark()


def test_wordmark_is_outlines_embedded_not_linked() -> None:
    svg = brand.WORDMARK.read_text()
    # outlined glyphs only: no text elements, no font references, nothing fetched
    assert "<path" in svg
    for word in ("<text", "font-family", "@font-face", "href="):
        assert word not in svg
    tag = brand.footer_wordmark()
    assert brand.wordmark_data_uri() in tag and 'alt="napkin2factory"' in tag
