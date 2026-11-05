"""The report's parts-and-cost section names the cost bands' region and date (gate I, S-227)."""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.loader import load_product
from napkin2factory.report.builder import _cost_basis_line, _cost_notes, cost_region_note

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def test_the_total_names_the_region_and_dates_of_the_bands() -> None:
    """A product declaring ``region: US`` gets "US cost bands, as of ..." and no warning."""
    product = load_product(EXAMPLES / "table")
    line = _cost_basis_line(product)
    assert line == "Estimated from the US cost bands, as of 2026-10 to 2026-11."


def test_a_product_without_a_region_says_the_us_bands_were_read() -> None:
    """No region declared is never silent."""
    product = load_product(EXAMPLES / "kiln")
    assert "no region declared" in _cost_basis_line(product)


def test_prices_taken_from_the_middle_of_a_band_are_numbered_and_explained_once() -> None:
    """The test stand's eight identical 77.50 prices share one note that names the band."""
    product = load_product(EXAMPLES / "test-stand")
    lines = [{"uri": p.uri} for p in product.parts.values()]
    notes = _cost_notes(product, lines)
    mid = [n for n in notes if n.startswith("mid-point of the cots-controls band")]
    assert len(mid) == 1 and "US, 2026-10" in mid[0]
    numbered = {ln["cost_note_no"] for ln in lines}
    assert notes.index(mid[0]) + 1 in numbered


def test_check_says_once_that_the_us_bands_were_read_for_want_of_a_region() -> None:
    """S-236: the agent-facing sentence exists only while no region is declared."""
    note = cost_region_note(load_product(EXAMPLES / "kiln"))
    assert note is not None and "US cost bands" in note and "region:" in note
    assert cost_region_note(load_product(EXAMPLES / "table")) is None
